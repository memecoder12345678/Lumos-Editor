import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


class FileTreeDelegate(QStyledItemDelegate):
    def __init__(self, tree_view, parent=None):
        super().__init__(parent)
        self.tree_view = tree_view
        self.py_icon = QIcon("icons:/python-icon.ico")
        self.default_icon = QIcon("icons:/default-icon.ico")
        self.folder_closed_icon = QIcon("icons:/folder-closed.png")
        self.folder_open_icon = QIcon("icons:/folder-open.png")
        self.image_icon = QIcon("icons:/image-icon.ico")
        self.json_icon = QIcon("icons:/json-icon.ico")
        self.md_icon = QIcon("icons:/markdown-icon.png")

    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)
        path = index.model().filePath(index)
        option.text = os.path.basename(option.text)
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

        file_ext = os.path.splitext(path)[1].lower()
        if os.path.isdir(path):
            if self.tree_view.isExpanded(index):
                option.icon = self.folder_open_icon
            else:
                option.icon = self.folder_closed_icon
        elif file_ext == ".py":
            option.icon = self.py_icon
        elif file_ext == ".pyw":
            option.icon = self.py_icon
        elif file_ext == ".json":
            option.icon = self.json_icon
        elif file_ext in image_extensions:
            option.icon = self.image_icon
        elif file_ext == ".md":
            option.icon = self.md_icon
        else:
            option.icon = self.default_icon


class FileTreeView(QTreeView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)
        self.setItemDelegate(FileTreeDelegate(self))
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

            new_path = os.path.abspath(target_path)
            if os.path.exists(new_path) and new_path != source_path:
                reply = QMessageBox.question(
                    self,
                    "File exists",
                    "File already exists. Replace it?",
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

                shutil.move(source_path, new_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not move file: {str(e)}")
                return

        event.accept()
