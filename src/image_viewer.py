import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtGui import QMovie
import os


class ImageViewer(QWidget):
    def __init__(self, filepath):
        super().__init__()
        self.is_modified = None
        self.filepath = os.path.abspath(filepath)
        self.editor = None
        self.tabname = (
            os.path.splitext(os.path.basename(filepath))[0][:17] + "..."
            if len(os.path.splitext(os.path.basename(filepath))[0]) > 16
            else os.path.basename(filepath)
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label, alignment=Qt.AlignCenter)
        self.scale_factor = 1.0
        self.original_size = None
        self.movie = None
        self.load_image(filepath)

    def load_image(self, filepath):
        if filepath.lower().endswith(".gif"):
            self.movie = QMovie(filepath)
            if self.movie.isValid():
                self.label.setMovie(self.movie)
                self.movie.start()
                self.original_size = self.movie.currentPixmap().size()
                return
            else:
                QMessageBox.warning(self, "Error", "Could not load GIF.")
                self.close()
                return

        self.original_pixmap = QPixmap(filepath)
        if self.original_pixmap.isNull():
            QMessageBox.warning(self, "Error", "Could not load image.")
            self.close()
            return

        self.original_size = self.original_pixmap.size()

        if self.original_size.width() > 2000 or self.original_size.height() > 2000:
            self.scale_factor = min(
                2000 / self.original_size.width(), 2000 / self.original_size.height()
            )

        self.update_image()

    def update_image(self):
        if self.movie:
            available_size = self.size() * 0.9
            current_size = self.original_size * self.scale_factor

            if (
                current_size.width() > available_size.width()
                or current_size.height() > available_size.height()
            ):
                width_ratio = available_size.width() / self.original_size.width()
                height_ratio = available_size.height() / self.original_size.height()
                self.scale_factor = min(width_ratio, height_ratio)
                current_size = self.original_size * self.scale_factor
            scaled_size = QSize(int(current_size.width()), int(current_size.height()))
            self.movie.setScaledSize(scaled_size)
            self.label.setFixedSize(scaled_size)
            return

        if not self.original_pixmap.isNull():
            available_size = self.size() * 0.9
            current_pixmap_size = self.original_pixmap.size() * self.scale_factor
            if (
                current_pixmap_size.width() > available_size.width()
                or current_pixmap_size.height() > available_size.height()
            ):
                width_ratio = available_size.width() / self.original_size.width()
                height_ratio = available_size.height() / self.original_size.height()
                self.scale_factor = min(width_ratio, height_ratio)

            final_scale = self.scale_factor
            new_size = self.original_size * final_scale
            scaled_pixmap = self.original_pixmap.scaled(
                int(new_size.width()),
                int(new_size.height()),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.label.setPixmap(scaled_pixmap)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_image()

    def wheelEvent(self, event: QWheelEvent):
        if self.movie or not self.original_pixmap.isNull():
            delta = event.angleDelta().y()
            factor = 1.1 if delta > 0 else 0.9
            new_factor = self.scale_factor * factor

            if 0.1 <= new_factor <= 5.0:
                self.scale_factor = new_factor
                self.update_image()
