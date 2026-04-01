import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import tkinter as tk
from config import DATA_FILE
from data_manager import DataManager
from ui.app import MainApp

if __name__ == "__main__":
    root = tk.Tk()
    root.title("바른자세")
    root.geometry("1280x820")
    root.minsize(1100, 720)

    data_manager = DataManager(DATA_FILE)
    MainApp(root, data_manager)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.lift()
    root.focus_force()
    root.mainloop()