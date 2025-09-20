import os
from PyQt5.QtWidgets import *


def terminal():
    with open("dir.txt", "r", encoding="utf-8") as f:
        dir_now = f.read().strip()
    os.system(
         f'start cmd /k "cd /d "{dir_now}" && title Terminal && powershell -noexit && exit"'
    )
