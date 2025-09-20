import os


def terminal(config_manager):
    dir_now = config_manager.get("dir")
    os.system(
        f'start cmd /k "cd /d "{dir_now}" && title Terminal && powershell -noexit && exit"'
    )
