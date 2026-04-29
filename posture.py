import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import threading
import tkinter as tk
from config import DATA_FILE
from data_manager import DataManager
from settings_manager import AppSettings
from ui.app import MainApp

def _early_preload():
    from analyzer import PostureAnalyzer
    _early_preload.result = PostureAnalyzer()

_early_preload.result = None
threading.Thread(target=_early_preload, daemon=True).start()

if __name__ == "__main__":
    root = tk.Tk()
    root.title("바른자세")
    root.geometry("1280x820")
    root.minsize(1100, 720)

    data_manager = DataManager(DATA_FILE)
    app_settings = AppSettings()
    MainApp(root, data_manager, app_settings, preloaded_analyzer=_early_preload.result)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.lift()
    root.focus_force()
root.mainloop()