import os
import sys
import wx
import time
import hashlib

from main_window import MainWindow

if __name__ == "__main__":
    app = wx.App(0)
    f = MainWindow()
    app.SetTopWindow(f)
    f.Show()
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent

    def sha256_file(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    class FileChangeHandler(FileSystemEventHandler):
        def __init__(self, dirname):
            super().__init__()
            self.last_time = 0
            self.file_hashes = {}
            self.dirname = dirname
            for root, _, files in os.walk(dirname):
                for file in files:
                    path = os.path.join(root, file)
                    self.file_hashes[path] = sha256_file(path)

        def on_modified(self, event):
            self.last_time = 0
            if event.is_directory:
                return
            print("File modified:", event.src_path)
            now = time.time()
            if now - self.last_time > 0.5:  # 0.5 секунды "тишины"
                print(f"Modified once: {event.src_path}")
            self.last_time = now

            path = event.src_path
            if not os.path.exists(path):
                return

            new_hash = sha256_file(path)
            old_hash = self.file_hashes.get(path)

            if new_hash != old_hash:
                self.file_hashes[path] = new_hash
                print(f"{path} реально изменился")
            else:
                print(f"{path} не изменился")
                return

            if (
                event.src_path.endswith("x.txt") # type: ignore
                or event.src_path.endswith("y.txt") # type: ignore
                or event.src_path.endswith("z.txt") # type: ignore
                or event.src_path.endswith("time.txt") # type: ignore
                or event.src_path.endswith("source_filename.txt") # type: ignore
                or event.src_path.endswith("type_id.txt") # type: ignore
                or event.src_path.endswith("value.txt") # type: ignore
                or event.src_path.endswith("comment.txt") # type: ignore
            ):
                print("Reloading grid columns...")
                f.suggest_columns()
            f.render_grid()

    if getattr(sys, "frozen", False):  # если упаковано в exe
        exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
    dirname = os.path.join(exe_dir, "dict")
    event_handler = FileChangeHandler(dirname)
    observer = Observer()
    observer.schedule(
        event_handler, dirname, recursive=True, event_filter=[FileModifiedEvent]
    )  # следим за текущей папкой
    observer.start()
    app.MainLoop()
