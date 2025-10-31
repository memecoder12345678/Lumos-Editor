import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


class FileTreeDelegate(QStyledItemDelegate):
    def __init__(self, tree_view, plugin_manager=None, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.tree_view = tree_view
        self.py_icon = QIcon("icons:/python-icon.ico")
        self.default_icon = QIcon("icons:/default-icon.ico")
        self.folder_closed_icon = QIcon("icons:/folder-closed.ico")
        self.folder_open_icon = QIcon("icons:/folder-open.ico")
        self.image_icon = QIcon("icons:/image-icon.ico")
        self.audio_icon = QIcon("icons:/audio-icon.ico")
        self.video_icon = QIcon("icons:/video-icon.ico")
        self.json_icon = QIcon("icons:/json-icon.ico")
        self.md_icon = QIcon("icons:/markdown-icon.ico")
        self.lumos_icon = QIcon("icons:/lumos-icon.ico")

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        path = index.model().filePath(index)
        option.text = os.path.basename(option.text)

        if os.path.isdir(path):
            if self.tree_view.isExpanded(index):
                option.icon = self.folder_open_icon
            else:
                option.icon = self.folder_closed_icon
            return

        file_ext = os.path.splitext(path)[1].lower()

        if self.plugin_manager:
            plugin_icon = self.plugin_manager.get_icon_for_file(path)
            if plugin_icon:
                option.icon = plugin_icon
                return

        image_extensions = [
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".webp",
            ".tiff",
            ".tif",
            ".svg",
            ".psd",
            ".raw",
            ".heif",
            ".heic",
        ]

        video_extensions = [".mp4", ".avi", ".mkv", ".mov", ".flv", ".wmv", ".m4v"]
        audio_extensions = [".mp3", ".wav", ".ogg", ".m4a"]

        if file_ext in [".py", ".pyw"]:
            option.icon = self.py_icon
        elif file_ext == ".json":
            option.icon = self.json_icon
        elif file_ext in image_extensions:
            option.icon = self.image_icon
        elif file_ext in video_extensions:
            option.icon = self.video_icon
        elif file_ext in audio_extensions:
            option.icon = self.audio_icon
        elif file_ext == ".md":
            option.icon = self.md_icon
        elif file_ext == ".lumosplugin":
            option.icon = self.lumos_icon
        else:
            option.icon = self.default_icon


class FileTreeView(QTreeView):
    def __init__(self, parent=None, plugin_manager=None):
        super().__init__(parent)
        self.main_window = parent

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)

        self.setItemDelegate(FileTreeDelegate(self, plugin_manager))

        self.expanded.connect(self.update_icon)
        self.collapsed.connect(self.update_icon)

    def update_icon(self, index):
        self.viewport().update()

    def dropEvent(self, event):
        if event.source():
            source_index = self.currentIndex()
            target_index = self.indexAt(event.pos())

            if not source_index.isValid():
                return

            source_path = os.path.abspath(self.model().filePath(source_index))

            if target_index.isValid():
                target_path = self.model().filePath(target_index)
                if os.path.isfile(target_path):
                    target_path = os.path.dirname(target_path)
            else:
                target_path = self.model().rootPath() or os.path.dirname(source_path)

            new_path = os.path.join(target_path, os.path.basename(source_path))

            if os.path.abspath(new_path) == source_path:
                event.ignore()
                return

            if os.path.exists(new_path):
                reply = QMessageBox.question(
                    self,
                    "Confirm Move",
                    f"'{os.path.basename(new_path)}' already exists. Do you want to replace it?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    event.ignore()
                    return

            try:
                self.main_window.close_file_tab(source_path)
                if os.path.exists(new_path):
                    self.main_window.close_file_tab(new_path)

                import shutil

                if os.path.isdir(source_path):
                    if os.path.exists(new_path):
                        shutil.rmtree(new_path)
                    shutil.move(source_path, new_path)
                else:
                    shutil.move(source_path, new_path)

            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not move item: {str(e)}")
                return

        event.accept()
