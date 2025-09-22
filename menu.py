import sys
import wx
import os
import subprocess

class MainMenu(wx.MenuBar):
    def __init__(self):
        super().__init__()
        m = wx.Menu()
        self.Append(m, "&Файл")
        m = wx.Menu()
        mm = wx.Menu()
        i = mm.Append(wx.ID_ANY, "Кировский рудник")
        m.Bind(wx.EVT_MENU, self.on_blacklist_kirovsky, i)
        i = mm.Append(wx.ID_ANY, "Рассвумчоррский рудник")
        m.Bind(wx.EVT_MENU, self.on_blacklist_rassvumchorrsky, i)
        m.AppendSubMenu(mm, "Черные списки")
        mm = wx.Menu()
        i = mm.Append(wx.ID_ANY, "Столбец X")
        m.Bind(wx.EVT_MENU, self.on_column_x, i)
        i = mm.Append(wx.ID_ANY, "Столбец Y")
        m.Bind(wx.EVT_MENU, self.on_column_y, i)
        i = mm.Append(wx.ID_ANY, "Столбец Z")
        m.Bind(wx.EVT_MENU, self.on_column_z, i)
        i = mm.Append(wx.ID_ANY, "Столбец Значение")
        m.Bind(wx.EVT_MENU, self.on_column_value, i)
        i = mm.Append(wx.ID_ANY, "Столбец Комментарий")
        m.Bind(wx.EVT_MENU, self.on_column_comment, i)
        i = mm.Append(wx.ID_ANY, "Столбец Тип события")
        m.Bind(wx.EVT_MENU, self.on_column_event_type, i)
        i = mm.Append(wx.ID_ANY, "Столбец Исходный файл")
        m.Bind(wx.EVT_MENU, self.on_column_source_file, i)
        i = mm.Append(wx.ID_ANY, "Столбец Время события")
        m.Bind(wx.EVT_MENU, self.on_column_event_time, i)
        m.AppendSubMenu(mm, "Столбцы")
        i = m.Append(wx.ID_ANY, "Порядок столбцов")
        m.Bind(wx.EVT_MENU, lambda event: self.open("dict/order.txt"), i)
        self.Append(m, "&Словари")
        m = wx.Menu()
        self.Append(m, "&Помощь")

    def open(self, filename):
        if getattr(sys, 'frozen', False):  # если упаковано в exe
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
        os.path.isabs(filename) or (filename := os.path.join(exe_dir, filename)) # type: ignore
        try:
            open(filename, "a").close()
        except Exception as e:
            print(f"Error opening file: {e}")
        if sys.platform.startswith("linux"):
            subprocess.run(["xdg-open", filename])
        else:
            os.startfile(filename)

    def on_column_x(self, event):
        self.open("dict/cols/x.txt")

    def on_column_y(self, event):
        self.open("dict/cols/y.txt")

    def on_column_z(self, event):
        self.open("dict/cols/z.txt")

    def on_column_value(self, event):
        self.open("dict/cols/value.txt")

    def on_column_comment(self, event):
        self.open("dict/cols/comment.txt")

    def on_column_event_type(self, event):
        self.open("dict/cols/type_id.txt")

    def on_column_source_file(self, event):
        self.open("dict/cols/source_filename.txt")

    def on_column_event_time(self, event):
        self.open("dict/cols/time.txt")

    def on_blacklist_kirovsky(self, event):
        self.open("dict/blacklist/kir.txt")

    def on_blacklist_rassvumchorrsky(self, event):
        self.open("dict/blacklist/ras.txt")