import os
import shutil
import subprocess
import sys


def terminal(config_manager):
    dir_now = config_manager.get("dir") or os.getcwd()

    dir_now = os.path.abspath(dir_now)

    if sys.platform == "win32":
        cmd = (
            f'start cmd /k "cd /d "{dir_now}" && title Terminal && powershell -noexit"'
        )
        os.system(cmd)

    elif sys.platform.startswith("linux"):
        terminals = [
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "xterm",
            "kitty",
            "alacritty",
        ]
        terminal_bin = None

        for t in terminals:
            if shutil.which(t):
                terminal_bin = t
                break

        if terminal_bin:
            subprocess.Popen([terminal_bin], cwd=dir_now)
        else:
            return (
                "No supported terminal emulator found. Please install one of the following: "
                + ", ".join(terminals)
            )

    elif sys.platform == "darwin":
        subprocess.Popen(["open", "-a", "Terminal", dir_now])
