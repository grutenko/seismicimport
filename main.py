import os
import sys
import wx

from main_window import MainWindow

if __name__ == "__main__":
    app = wx.App(0)
    f = MainWindow()
    app.SetTopWindow(f)
    f.Show()
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class FileChangeHandler(FileSystemEventHandler):
        def on_modified(self, event):
            print("File modified:", event.src_path)
            f.render_grid()

    event_handler = FileChangeHandler()
    observer = Observer()
    if getattr(sys, 'frozen', False):  # если упаковано в exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    dirname = os.path.join(exe_dir, "dict")
    observer.schedule(event_handler, dirname, recursive=True)  # следим за текущей папкой
    observer.start()
    app.MainLoop()