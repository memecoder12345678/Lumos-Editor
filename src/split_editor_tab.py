from PyQt5.QtCore import QEvent, Qt
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .editor_tab import MiniMap


class SplitEditorTab(QWidget):
    def __init__(self, left_editor_tab, right_editor_tab, parent=None, mode=None):
        super().__init__(parent)
        self.left_editor_tab = left_editor_tab
        self.right_editor_tab = right_editor_tab
        self.mode = mode

        if hasattr(self.left_editor_tab, "editor"):
            self.active_editor = self.left_editor_tab
        elif hasattr(self.right_editor_tab, "editor"):
            self.active_editor = self.right_editor_tab
        else:
            self.active_editor = None

        self.tabname = "Split View"

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("border: none; margin: 0px; padding: 0px;")

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.left_widget = self._create_pane(self.left_editor_tab, is_disk_side=False)
        self.right_widget = self._create_pane(self.right_editor_tab, is_disk_side=True)

        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.right_widget)

        self.left_widget.setMinimumWidth(250)
        self.right_widget.setMinimumWidth(250)

        main_layout.addWidget(splitter)

        try:
            self.left_editor_tab.editor.installEventFilter(self)
        except Exception:
            pass
        try:
            self.right_editor_tab.editor.installEventFilter(self)
        except Exception:
            pass

        self._update_active_visuals()

    def _create_pane(self, editor_tab, is_disk_side):
        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(1, 1, 1, 1)
        vlayout.setSpacing(0)

        display_name = editor_tab.tabname
        if self.mode is not None:
            display_name += " (On Disk)" if is_disk_side else " (In-Memory)"

        title_label = QLabel(display_name)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label.setFixedHeight(26)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setStyleSheet(
            "QLabel { background-color: #252526; color: #d4d4d4; padding: 4px 8px; border-bottom: 2px solid #252526; }"
        )
        vlayout.addWidget(title_label)

        if hasattr(editor_tab, "editor"):
            editor = editor_tab.editor
            minimap = MiniMap(editor)
            editor._split_minimap = minimap

            for w in (editor, minimap):
                if w is None:
                    continue
                old_parent = w.parentWidget()
                if old_parent is not None and old_parent is not container:
                    old_layout = old_parent.layout()
                    if old_layout is not None:
                        old_layout.removeWidget(w)
                    w.setParent(container)

            editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            editor.show()

            minimap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
            default_w = minimap.width() or 120
            minimap.setFixedWidth(default_w)

            editor_layout = QHBoxLayout()
            editor_layout.setContentsMargins(0, 0, 0, 0)
            editor_layout.setSpacing(0)
            editor_layout.addWidget(editor, 5)
            editor_layout.addWidget(minimap, 1)

            vlayout.addLayout(editor_layout, 1)
            vlayout.setStretch(0, 0)
            vlayout.setStretch(1, 1)

            container.title_label = title_label
            container.editor_widget = editor
            container.minimap = minimap
            container.setLayout(vlayout)

            try:
                minimap._request_update()
            except Exception:
                pass

        else:
            widget = editor_tab if isinstance(editor_tab, QWidget) else QWidget()
            old_parent = widget.parentWidget()
            if old_parent is not None and old_parent is not container:
                old_layout = old_parent.layout()
                if old_layout is not None:
                    old_layout.removeWidget(widget)
                widget.setParent(container)

            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            widget.show()

            vlayout.addWidget(widget, 1)
            vlayout.setStretch(0, 0)
            vlayout.setStretch(1, 1)

            container.title_label = title_label
            container.editor_widget = widget
            container.minimap = None
            container.setLayout(vlayout)

        return container
    
    def check_view_mode(self, editor_tab):
            if self.mode is None:
                return None
            
            if editor_tab == self.right_editor_tab:
                return "disk"
            elif editor_tab == self.left_editor_tab:
                return "memory"
            return None

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            if (
                hasattr(self.left_editor_tab, "editor")
                and obj is self.left_editor_tab.editor
            ):
                self._set_active_editor(self.left_editor_tab)
            elif (
                hasattr(self.right_editor_tab, "editor")
                and obj is self.right_editor_tab.editor
            ):
                self._set_active_editor(self.right_editor_tab)
        return super().eventFilter(obj, event)

    def _set_active_editor(self, editor_tab):
        if self.active_editor != editor_tab:
            self.active_editor = editor_tab
            self._update_active_visuals()

    def _update_active_visuals(self):
        active = "border-bottom: 2px solid #0098ff;"
        inactive = "border-bottom: 2px solid #252526;"
        base = "background-color: #252526; color: #d4d4d4; padding: 4px 8px;"
        if self.active_editor is None:
            self.left_widget.title_label.setStyleSheet(base + inactive)
            self.right_widget.title_label.setStyleSheet(base + inactive)
        elif self.active_editor == self.left_editor_tab:
            self.left_widget.title_label.setStyleSheet(base + active)
            self.right_widget.title_label.setStyleSheet(base + inactive)
        else:
            self.right_widget.title_label.setStyleSheet(base + active)
            self.left_widget.title_label.setStyleSheet(base + inactive)

    def get_active_editor_tab(self):
        return self.active_editor

    def get_child_editors(self):
        return [self.left_editor_tab, self.right_editor_tab]
