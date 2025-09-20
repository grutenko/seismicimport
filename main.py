import wx

from main_window import MainWindow

if __name__ == "__main__":
    app = wx.App(0)
    f = MainWindow()
    app.SetTopWindow(f)
    f.Show()
    app.MainLoop()