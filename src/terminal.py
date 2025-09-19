import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


def terminal():
    with open("dir.txt", "r", encoding="utf-8") as f:
        dir_now = f.read().strip()
    if os.name == "nt":
        os.system(
            f'start cmd /k "cd /d "{dir_now}" && title Terminal && powershell -noexit && exit"'
        )
    else:
        app = QApplication([])
        QMessageBox.warning(None, "Error", "Terminal only supports on Windows")
