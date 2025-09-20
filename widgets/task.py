import threading
from typing import Protocol, runtime_checkable

import wx


@runtime_checkable
class TaskJob(Protocol):
    progress = -1
    total = -1
    message = None
    cancel_event = None
    lock = None

    def __init__(self):
        self.progress = -1
        self.total = -1
        self.message = None
        self.cancel_event = threading.Event()
        self.lock = threading.Lock()

    def set_progress(self, progress=-1, total=-1, message=None):
        with self.lock:
            self.progress = progress
            self.total = total
            self.message = message

    def run(self):
        """
        Запускает задачу в работу. Метод должен вернуть результат работы.
        При желании можно менять прогресс используя self.set_progress(progress, total, message)
        Также в задаче можно использовать self.cancel_event.is_set() для проерки не была ли отменена
        задача пользователем
        """
        ...


class Task(wx.Dialog):
    def __init__(self, title, message, job: TaskJob, parent=None, can_abort=True, show_time=True):
        if not isinstance(job, TaskJob):
            raise RuntimeError("invalid task job.")
        super().__init__(parent, title=title)
        self.was_cancelled = False
        sz = wx.BoxSizer(wx.VERTICAL)
        sz_in = wx.BoxSizer(wx.VERTICAL)
        self.message = wx.StaticText(self, label=message)
        sz_in.Add(self.message, 0, wx.EXPAND)
        self.gauge = wx.Gauge(self, size=wx.Size(300, -1))
        sz_in.Add(self.gauge, 0, wx.EXPAND)
        sz.Add(sz_in, 1, wx.EXPAND | wx.ALL, border=10)
        line = wx.StaticLine(self)
        sz.Add(line, 0, wx.EXPAND)
        btn_sz = wx.StdDialogButtonSizer()
        self.cancel = wx.Button(self, label="Отменить")
        self.cancel.Bind(wx.EVT_BUTTON, self.on_cancel)
        btn_sz.Add(self.cancel, 0)
        sz.Add(btn_sz, 0, wx.ALIGN_RIGHT | wx.ALL, border=10)
        self.SetSizer(sz)
        self.timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_alarm)
        self.job = job

        self.status = "alive"
        self._e = None
        self._ret = None
        self._on_resolve = lambda *args, **kwds: ...

        def on_reject(e):
            raise e

        self._on_reject = on_reject
        self._is_cancel = False

        self.Layout()
        self.Fit()
        self.Bind(wx.EVT_CLOSE, self.on_cancel)

    def on_cancel(self, event):
        self.was_cancelled = True
        event.Skip()

    def Update(self, progress, message=None):
        self.gauge.SetValue(progress)
        if message is not None:
            self.message.SetLabelText(message)

    def SetRange(self, range):
        self.gauge.SetRange(range)

    def Pulse(self):
        self.gauge.Pulse()

    def WasCancelled(self):
        return self.was_cancelled

    def is_cancel(self):
        return self._is_cancel

    def on_alarm(self, event):
        with self.job.lock:
            if self.status == "alive":
                if self.job.message is not None:
                    self.Update(self.gauge.GetValue(), self.job.message)
                if self.job.progress == -1:
                    self.Pulse()
                else:
                    self.SetRange(self.job.total)
                    self.Update(self.job.progress)
                if self.WasCancelled():
                    self.job.cancel_event.set()
                    self._is_cancel = True
                return

        self.timer.Stop()
        self.SetRange(1)
        self.Update(1)
        if self.status == "resolve":
            self._on_resolve(self._ret)
        elif self.status == "reject":
            self._on_reject(self._e)
        self.Close()

    def then(self, on_resolve, on_reject):
        self._on_resolve = on_resolve
        self._on_reject = on_reject

    def run(self):
        def task(job):
            ret = None
            try:
                ret = job.run()
            except Exception as e:
                with self.job.lock:
                    self.status = "reject"
                    self._e = e
            else:
                with self.job.lock:
                    self.status = "resolve"
                    self._ret = ret

        self.thread = threading.Thread(target=task, args=(self.job,))
        self.thread.start()
        self.timer.Start(100)
        self.ShowModal()