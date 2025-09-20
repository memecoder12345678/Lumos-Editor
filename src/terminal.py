import os
from PyQt5.QtWidgets import *


def terminal(parent):
    with open("dir.txt", "r", encoding="utf-8") as f:
        dir_now = f.read().strip()
    if os.name == "nt":
        os.system(
            f'start cmd /k "cd /d "{dir_now}" && title Terminal && powershell -noexit && exit"'
        )
    else:
        QMessageBox.warning(parent, "Error", "Terminal only supports on Windows")
