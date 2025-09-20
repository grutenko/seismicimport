import wx

class MainStatusBar(wx.StatusBar):
    def __init__(self, parent):
        super().__init__(parent)
        self.SetFieldsCount(4)