import wx
import pandas as pd
import fnmatch
from menu import MainMenu
from statusbar import MainStatusBar
from widgets.task import Task, TaskJob
import wx.lib.mixins.listctrl as listmix
import numpy as np
import traceback

import logging


class MemoryHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(self.format(record))

    def get_logs(self):
        return self.records


logger = logging.getLogger("runtime")
logger.setLevel(logging.DEBUG)

memory_handler = MemoryHandler()
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
memory_handler.setFormatter(formatter)
logger.addHandler(memory_handler)

# Считаем матрицу трансформации из системы АСКСМ в геодезическую
G1 = [29929.634, 40713.921, 349.0]
G2 = [30113.916, 40479.346, 379.0]
G3 = [29970.552, 40564.192, 225.0]
A1 = [3261.0, 1156.0, 97.0]
A2 = [2993.0, 1025.0, 127.0]
A3 = [3159.0, 1039.0, -27.0]
source = np.array([A1, A2, A3])
target = np.array([G1, G2, G3])


def calculate_transformation_matrix(source, target):
    """
    Вычисляет матрицу преобразования 4x4 между системами координат
    по трем парам точек.

    :param source: Исходные точки (3x3 numpy array)
    :param target: Целевые точки (3x3 numpy array)
    :return: Матрица преобразования 4x4
    """
    # Центрирование точек
    src_centroid = np.mean(source, axis=0)
    tgt_centroid = np.mean(target, axis=0)

    src_centered = source - src_centroid
    tgt_centered = target - tgt_centroid

    # Вычисление матрицы H
    H = np.dot(src_centered.T, tgt_centered)

    # SVD разложение
    U, _, Vt = np.linalg.svd(H)

    # Матрица вращения
    R = np.dot(Vt.T, U.T)

    # Коррекция отражений
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = np.dot(Vt.T, U.T)

    # Вектор трансляции
    t = tgt_centroid - np.dot(R, src_centroid)

    # Формирование матрицы 4x4
    matrix = np.eye(4)
    matrix[:3, :3] = R
    matrix[:3, 3] = t

    return matrix


ASKSM_GEOD = calculate_transformation_matrix(source, target)


def calc_asksm_to_geodesic(x, y, z):
    global ASKSM_GEOD
    x = float(x)
    y = float(y)
    z = float(z)
    gx, gy, gz = np.dot(ASKSM_GEOD, np.array([x, y, z, 1]))[:3]
    return gx, gy, gz


class VirtualListCtrl(wx.ListCtrl):
    def __init__(self, parent):
        super().__init__(parent, style=wx.LC_REPORT | wx.LC_VIRTUAL | wx.LC_SINGLE_SEL)
        self.transform_cache = {}
        self.df = None
        self.header = [""]
        self.SetItemCount(0)
        self.Bind(wx.EVT_KEY_DOWN, self.on_key)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.on_right_click)
        self.current_row = None
        self.current_col = None
        self.x_col = -1
        self.y_col = -1
        self.z_col = -1

    def on_key(self, event):
        if event.ControlDown() and event.GetKeyCode() == ord("C"):
            if self.current_row is not None and self.current_col is not None:
                value = self.GetItemText(self.current_row, self.current_col)
                self.copy_to_clipboard(value)
        else:
            event.Skip()

    def on_right_click(self, event):
        # выясняем, на какую ячейку кликнули
        x, y = event.GetPoint()
        row, flags = self.HitTest((x, y))
        if row != wx.NOT_FOUND:
            col = self.get_column_from_x(x)
            self.current_row = row
            self.current_col = col

            menu = wx.Menu()
            item = menu.Append(wx.ID_COPY, "Копировать ячейку")
            self.Bind(wx.EVT_MENU, self.on_copy, item)
            self.PopupMenu(menu)
            menu.Destroy()

    def on_copy(self, event):
        if self.current_row is not None and self.current_col is not None:
            value = self.GetItemText(self.current_row, self.current_col)
            self.copy_to_clipboard(value)

    def copy_to_clipboard(self, text):
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(text))
            wx.TheClipboard.Close()
            print(f"Copied: {text}")

    def get_column_from_x(self, x):
        """Определяем номер столбца по координате X"""
        total = 0
        for col in range(self.GetColumnCount()):
            total += self.GetColumnWidth(col)
            if x < total:
                return col
        return 0

    def update(self, df, header, x_col=-1, y_col=-1, z_col=-1):
        self.df = df
        self.header = header
        self.SetItemCount(len(df))
        self.DeleteAllColumns()
        self.transform_cache = {}
        for i, (code, name) in enumerate(header):
            self.InsertColumn(i, name)

        self.x_col = x_col
        self.y_col = y_col
        self.z_col = z_col
        if self.x_col == -1 or self.y_col == -1 or self.z_col == -1:
            print("X, Y, Z columns must be selected")
        self.Refresh()

    def OnGetItemText(self, item, col):
        return self.df.loc[item, self.header[col][0]]


class SaveExcelJob(TaskJob):
    def __init__(self, main_window, save_as):
        super().__init__()
        self.main_window = main_window
        self.save_as = save_as

    def run(self):
        try:
            p = self.main_window
            date_col = p.date_field.GetStrings()[p.date_field.GetSelection()]
            x_col = p.x_field.GetStrings()[p.x_field.GetSelection()]
            y_col = p.y_field.GetStrings()[p.y_field.GetSelection()]
            z_col = p.z_field.GetStrings()[p.z_field.GetSelection()]
            value_col = p.value_field.GetStrings()[p.value_field.GetSelection()]
            type_id_col = p.type_col_field.GetStrings()[p.type_col_field.GetSelection()]
            xls_list = p.excell_list_field.GetStrings()[
                p.excell_list_field.GetSelection()
            ]
            df = pd.read_excel(
                p.xls_path,
                dtype=str,
                na_filter=False,
                sheet_name=xls_list,
            )
            df = p.filter(df)
            df = df[[type_id_col, x_col, y_col, z_col, value_col, date_col]]
            df[value_col] = df[value_col].apply(lambda a: a.replace(".", ","))
            df = df.rename(columns={
                type_id_col: "TypeId",
                x_col: "X",
                y_col: "Y",
                z_col: "Z",
                value_col: "Energy",
                date_col: "LocTime",
            })
            df_str = df.map(
                lambda x: str(x).replace(".", ",") if isinstance(x, float) else x
            )
            df_str.to_excel(self.save_as, index=False)
        except Exception as e:
            tb = traceback.format_exc()
            wx.LogError(f"Exception caught:\n{e}\nTraceback:\n{tb}")
            raise e


class MainWindow(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Фильтр БД АСКСМ", size=wx.Size(550, 850))
        self.xls_path = None
        self.df_cache = None
        self.header = None
        self.menu = MainMenu()
        self.SetMenuBar(self.menu)
        sz = wx.BoxSizer(wx.VERTICAL)
        self.splitter = wx.SplitterWindow(self, style=wx.SP_LIVE_UPDATE)
        self.left = wx.ScrolledWindow(self.splitter)
        self.left.SetScrollbars(20, 20, 50, 50)
        l_sz = wx.BoxSizer(wx.VERTICAL)
        l_sz_in = wx.BoxSizer(wx.VERTICAL)
        label = wx.StaticText(self.left, label="Файл БД АСКСМ или аналог")
        font = label.GetFont()
        font.MakeBold()  # начиная с wxPython 4.1
        label.SetFont(font)
        l_sz_in.Add(label)
        self.file_field = wx.FilePickerCtrl(
            self.left, wildcard="Все файлы (*.*)|*.*|XLSX (*xlsx)|*.xlsx?"
        )
        l_sz_in.Add(self.file_field, 0, wx.BOTTOM, border=10)
        label = wx.StaticText(self.left, label="Лист Excell")
        font = label.GetFont()
        font.MakeBold()  # начиная с wxPython 4.1
        label.SetFont(font)
        l_sz_in.Add(label)
        self.excell_list_field = wx.Choice(self.left)
        l_sz_in.Add(self.excell_list_field, 0, wx.BOTTOM, border=10)
        label = wx.StaticText(self.left, label="Соответствия столбцов")
        font = label.GetFont()
        font.MakeBold()  # начиная с wxPython 4.1
        label.SetFont(font)
        l_sz_in.Add(label)
        l_sz_in_h = wx.FlexGridSizer(2, 4, 5, 5)
        label = wx.StaticText(self.left, label="X:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Y:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Z:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Значение:")
        l_sz_in_h.Add(label)
        self.x_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.x_field)
        self.y_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.y_field)
        self.z_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.z_field)
        self.value_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.value_field)
        l_sz_in.Add(l_sz_in_h, 0, wx.EXPAND | wx.BOTTOM, border=10)
        l_sz_in_h = wx.FlexGridSizer(2, 4, 5, 5)
        label = wx.StaticText(self.left, label="Дата:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Тип:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Комментарий:")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Исходный файл:")
        l_sz_in_h.Add(label)
        self.date_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.date_field)
        self.type_col_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.type_col_field)
        self.comment_field = wx.Choice(self.left)
        self.source_file_field = wx.Choice(self.left)
        l_sz_in_h.Add(self.comment_field)
        l_sz_in_h.Add(self.source_file_field)
        l_sz_in.Add(l_sz_in_h, 0, wx.EXPAND | wx.BOTTOM, border=10)
        label = wx.StaticText(self.left, label="Фильтр событий")
        font = label.GetFont()
        font.MakeBold()  # начиная с wxPython 4.1
        label.SetFont(font)
        l_sz_in.Add(label)
        l_sz_in_h = wx.FlexGridSizer(2, 2, 5, 5)
        label = wx.StaticText(self.left, label="Типы событий")
        l_sz_in_h.Add(label)
        label = wx.StaticText(self.left, label="Рудники")
        l_sz_in_h.Add(label)
        t_sz = wx.BoxSizer(wx.VERTICAL)
        t_sz_in = wx.BoxSizer(wx.HORIZONTAL)
        self.sel_all_types_button = wx.Button(self.left, label="Выбрать все")
        t_sz_in.Add(self.sel_all_types_button)
        self.clear_all_types_button = wx.Button(self.left, label="Снять")
        t_sz_in.Add(self.clear_all_types_button)
        t_sz.Add(t_sz_in)
        self.type_field = wx.CheckListBox(self.left)
        self.type_field.SetSize((-1, 70))
        for i in range(15):
            self.type_field.Append(str(i))
        t_sz.Add(self.type_field, 1, wx.EXPAND)
        l_sz_in_h.Add(t_sz)
        t_sz = wx.BoxSizer(wx.VERTICAL)
        t_sz_in = wx.BoxSizer(wx.HORIZONTAL)
        self.sel_all_fields_button = wx.Button(self.left, label="Выбрать все")
        t_sz_in.Add(self.sel_all_fields_button)
        self.clear_all_fields_button = wx.Button(self.left, label="Снять")
        t_sz_in.Add(self.clear_all_fields_button)
        t_sz.Add(t_sz_in)
        self.field_field = wx.CheckListBox(self.left)
        self.field_field.Append("Кировский")
        self.field_field.Append("Расвумчоррский")
        self.field_field.Check(0)
        t_sz.Add(self.field_field, 1, wx.EXPAND)
        l_sz_in_h.Add(t_sz)
        l_sz_in.Add(l_sz_in_h, 0, wx.EXPAND | wx.BOTTOM, border=10)
        l_sz.Add(l_sz_in, 1, wx.EXPAND | wx.ALL, border=10)
        self.left.SetSizer(l_sz)
        self.right = VirtualListCtrl(self.splitter)
        self.splitter.SetMinimumPaneSize(250)
        self.splitter.SetSashGravity(1)
        self.splitter.SplitHorizontally(self.left, self.right, 400)
        sz.Add(self.splitter, 1, wx.EXPAND)
        p = wx.Panel(self)
        p_sz = wx.BoxSizer(wx.VERTICAL)
        p.SetSizer(p_sz)
        btn_sz = wx.StdDialogButtonSizer()
        self.save_button = wx.Button(p, label="Сохранить")
        self.open_button = wx.Button(p, label="Открыть в Excell")
        btn_sz.Add(self.save_button, wx.RIGHT, border=10)
        btn_sz.Add(self.open_button)
        self.save_button.Disable()
        self.open_button.Disable()
        p_sz.Add(btn_sz, 0, wx.ALL | wx.ALIGN_RIGHT, border=5)
        sz.Add(p, 0, wx.EXPAND)
        self.SetSizer(sz)
        self.Layout()
        self.Show()

        self.bind_all()

    def bind_all(self):
        self.file_field.Bind(wx.EVT_FILEPICKER_CHANGED, self.on_file_picker_changed)
        self.sel_all_types_button.Bind(wx.EVT_BUTTON, self.on_select_all_types)
        self.clear_all_types_button.Bind(wx.EVT_BUTTON, self.on_clear_types)
        self.excell_list_field.Bind(wx.EVT_CHOICE, self.on_select_excell_list)
        self.x_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.y_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.z_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.value_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.type_col_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.comment_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.source_file_field.Bind(wx.EVT_CHOICE, self.render_grid)
        self.type_field.Bind(wx.EVT_CHECKLISTBOX, self.render_grid)
        self.field_field.Bind(wx.EVT_CHECKLISTBOX, self.render_grid)
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)

    def on_save(self, event):
        with wx.FileDialog(
            self,
            "Сохранить Excel",
            wildcard="Excel файлы (*.xlsx)|*.xlsx",
            style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
        ) as dlg:
            if dlg.ShowModal() == wx.ID_CANCEL:
                return  # пользователь отменил

            path = dlg.GetPath()
            # добавим расширение, если пользователь не указал
            if not path.lower().endswith(".xlsx"):
                path += ".xlsx"

            self.save_task = Task(
                "Сохранение файла",
                "идет сохранение файла...",
                SaveExcelJob(self, path),
                parent=self,
                can_abort=False,
            )
            self.save_task.then(self.on_resolve, self.on_reject)
            self.save_task.run()

    def on_resolve(self, result):
        ret = wx.MessageBox("Файл успешно сохранен. Открыть его в Excell?", "Сохранение завершено", wx.YES_NO | wx.ICON_QUESTION)
        if ret == wx.YES:
            import os
            os.startfile(self.save_task.job.save_as)

    def on_reject(self, error):
        ...

    def on_select_excell_list(self, event):
        xls = pd.ExcelFile(self.xls_path)
        sheets = xls.sheet_names
        self.header = pd.read_excel(
            xls, nrows=0, sheet_name=sheets[self.excell_list_field.GetSelection()]
        ).columns.tolist()
        self.header = list(map(lambda x: x.strip(), self.header))
        xls.close()
        self.x_field.Clear()
        for item in self.header:
            self.x_field.Append(item)
        self.y_field.Clear()
        for item in self.header:
            self.y_field.Append(item)
        self.z_field.Clear()
        for item in self.header:
            self.z_field.Append(item)
        self.value_field.Clear()
        for item in self.header:
            self.value_field.Append(item)
        self.type_col_field.Clear()
        for item in self.header:
            self.type_col_field.Append(item)
        self.comment_field.Clear()
        for item in self.header:
            self.comment_field.Append(item)
        self.source_file_field.Clear()
        for item in self.header:
            self.source_file_field.Append(item)
        self.date_field.Clear()
        for item in self.header:
            self.date_field.Append(item)

        self.df_cache = None
        self.suggest_columns()
        self.suggest_filter()
        self.render_grid()

    def on_select_all_types(self, event):
        self.type_field.SetCheckedItems(list(range(15)))
        self.render_grid()

    def on_clear_types(self, event):
        self.type_field.SetCheckedItems([])
        self.render_grid()

    def update_controls_state(self):
        self.save_button.Enable(self.xls_path is not None)
        self.open_button.Enable(self.xls_path is not None)

    def on_file_picker_changed(self, event):
        import os

        path = self.file_field.GetPath()
        if not os.path.exists(path):
            wx.MessageBox("Неверный файл: %s" % path)
            return

        info = wx.BusyInfo("Загрузка данных, пожалуйста подождите...", parent=self.left)
        wx.Yield()  # даём GUI обновиться

        self.xls_path = path
        xls = pd.ExcelFile(path)
        lis_ = xls.sheet_names
        xls.close()
        self.excell_list_field.Clear()
        for item in lis_:
            self.excell_list_field.Append(item)

        if len(lis_) > 0:
            self.excell_list_field.SetSelection(0)

        self.on_select_excell_list(event)
        self.update_controls_state()

        del info

    def suggest_columns(self):
        if self.xls_path is None:
            return

        import os
        import sys

        def get_main_script_path():
            if getattr(sys, "frozen", False):  # приложение собрано PyInstaller
                return os.path.dirname(os.path.abspath(sys.executable))
            else:
                return os.path.dirname(os.path.abspath(sys.argv[0]))

        def sugg(field, sugg_dict_file, fallback_sugg_dict, default_offset):
            try:
                with open(sugg_dict_file, "r", encoding="utf-8") as f:
                    sugg_dict = f.readlines()
                    sugg_dict = [line.strip() for line in sugg_dict]
            except (FileNotFoundError, PermissionError, IOError) as e:
                print("cannot load file %s, %s" % (sugg_dict_file, e))
                sugg_dict = fallback_sugg_dict
            for item in self.header:
                if item.strip() in sugg_dict:
                    try:
                        i = field.GetItems().index(item)
                        field.SetSelection(i)
                    except ValueError:
                        if len(field.GetItems()) > default_offset:
                            field.SetSelection(default_offset)
                        else:
                            field.SetSelection(len(field.GetItems()) - 1)
                    break

        sugg(self.x_field, "dict/cols/x.txt", ["EX", "X"], 0)
        sugg(self.y_field, "dict/cols/y.txt", ["EY", "Y"], 1)
        sugg(self.z_field, "dict/cols/z.txt", ["EZ", "Z"], 2)
        sugg(self.value_field, "dict/cols/value.txt", ["EEnergy", "Energy"], 3)
        sugg(self.date_field, "dict/cols/time.txt", ["ELocTime"], 4)
        sugg(
            self.type_col_field,
            "dict/cols/type_id.txt",
            ["ETypeId", "TypeId"],
            5,
        )
        sugg(
            self.comment_field,
            "dict/cols/comment.txt",
            ["EComment", "Comment"],
            6,
        )
        sugg(
            self.source_file_field,
            "dict/cols/source_filename.txt",
            ["ESourseFileName", "ESourceFileName", "SourceFileName"],
            7,
        )

    def suggest_filter(self):
        i = self.type_col_field.GetSelection()
        column = self.header[i]
        if self.df_cache is None:
            xls_list = self.excell_list_field.GetStrings()[
                self.excell_list_field.GetSelection()
            ]
            df = pd.read_excel(
                self.xls_path,
                dtype=str,
                na_filter=False,
                sheet_name=xls_list,
            )
            self.df_cache = df
        else:
            df = self.df_cache

        unique_values = df[column].unique()
        strings = self.type_field.GetStrings()
        for val in unique_values:
            if str(val) in strings:
                index = strings.index(str(val))
                self.type_field.Check(index, True)

    def append_row(self, values):
        index = self.right.GetItemCount()  # следующая строка
        self.right.InsertItem(index, str(values[0]))  # первая колонка
        for col, val in enumerate(values[1:], start=1):
            self.right.SetItem(index, col, str(val))  # остальные колонки

    def filter(self, df):
        x_col = self.x_field.GetStrings()[self.x_field.GetSelection()]
        y_col = self.y_field.GetStrings()[self.y_field.GetSelection()]
        z_col = self.z_field.GetStrings()[self.z_field.GetSelection()]
        value_col = self.value_field.GetStrings()[self.value_field.GetSelection()]
        type_id_col = self.type_col_field.GetStrings()[
            self.type_col_field.GetSelection()
        ]
        comment_col = self.comment_field.GetStrings()[self.comment_field.GetSelection()]
        type_id_col = self.type_col_field.GetStrings()[
            self.type_col_field.GetSelection()
        ]
        filename_col = self.source_file_field.GetStrings()[
            self.source_file_field.GetSelection()
        ]
        checked_indices = self.type_field.GetCheckedItems()
        selected_types = [self.type_field.GetString(i) for i in checked_indices]
        sort_by_field = True

        kir_comment_blacklist = []
        try:
            with open("dict/blacklist/kir.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
                lines = [line.strip() for line in lines if line and line.strip()]
                kir_comment_blacklist.extend(lines)
        except Exception:
            ...
        ras_comment_blacklist = []
        try:
            with open("dict/blacklist/ras.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
                lines = [line.strip() for line in lines if line and line.strip()]
                ras_comment_blacklist.extend(lines)
        except Exception:
            ...

        print(kir_comment_blacklist, ras_comment_blacklist)
        filename_mask = ()
        if self.field_field.IsChecked(0) and self.field_field.IsChecked(1):
            filename_mask = (".KIR", ".RAS")
        elif self.field_field.IsChecked(0):
            filename_mask = ".KIR"
        elif self.field_field.IsChecked(1):
            filename_mask = ".RAS"

        mask = (
            (df[x_col] != "")
            & (df[y_col] != "")
            & (df[z_col] != "")
            & (df[value_col] != "")
            & df[type_id_col].astype(str).isin(selected_types)
            & df[filename_col].str.endswith(filename_mask, na=False)
        )
        kir_mask = ~df[filename_col].str.endswith(".KIR", na=False) | ~df[
            comment_col
        ].str.strip().apply(
            lambda x: any(fnmatch.fnmatch(x, p) for p in kir_comment_blacklist)
        )
        ras_mask = ~df[filename_col].str.endswith(".RAS", na=False) | ~df[
            comment_col
        ].str.strip().apply(
            lambda x: any(fnmatch.fnmatch(x, p) for p in ras_comment_blacklist)
        )
        df = df[mask & kir_mask & ras_mask].copy()
        if sort_by_field:
            df.loc[:, "suffix"] = df[filename_col].str[-4:]
            df = df.sort_values(by=["suffix"])
            df = df.drop(columns=["suffix"])
        return df.reset_index(drop=True)

    def render_grid(self, event=None):
        if self.xls_path is None:
            return

        info = wx.BusyInfo("Загрузка данных, пожалуйста подождите...", parent=self.left)
        wx.Yield()  # даём GUI обновиться
        x_col = self.x_field.GetStrings()[self.x_field.GetSelection()]
        y_col = self.y_field.GetStrings()[self.y_field.GetSelection()]
        z_col = self.z_field.GetStrings()[self.z_field.GetSelection()]
        date_col = self.date_field.GetStrings()[self.date_field.GetSelection()]
        value_col = self.value_field.GetStrings()[self.value_field.GetSelection()]
        comment_col = self.comment_field.GetStrings()[self.comment_field.GetSelection()]
        type_id_col = self.type_col_field.GetStrings()[
            self.type_col_field.GetSelection()
        ]
        filename_col = self.source_file_field.GetStrings()[
            self.source_file_field.GetSelection()
        ]
        xls_list = self.excell_list_field.GetStrings()[
            self.excell_list_field.GetSelection()
        ]
        if self.df_cache is None:
            df = pd.read_excel(
                self.xls_path,
                dtype=str,
                na_filter=False,
                sheet_name=xls_list,
            )
            self.df_cache = df
        else:
            df = self.df_cache
        df = self.filter(df)
        header = [
            (type_id_col, "Тип"),
            (x_col, "X"),
            (y_col, "Y"),
            (z_col, "Z"),
            (value_col, "Энергия"),
            (date_col, "Время события"),
            (comment_col, "Комментарий"),
            (filename_col, "Исходный файл"),
        ]
        self.right.update(df, header, x_col=1, y_col=2, z_col=3)

        for col in range(self.right.GetColumnCount()):
            self.right.SetColumnWidth(col, wx.LIST_AUTOSIZE)

        del info
