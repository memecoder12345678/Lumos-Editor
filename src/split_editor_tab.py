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
    def __init__(self, left_editor_tab, right_editor_tab, parent=None):
        super().__init__(parent)
        self.left_editor_tab = left_editor_tab
        self.right_editor_tab = right_editor_tab
        self.active_editor = self.left_editor_tab
        self.tabname = "Split View"

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.setStyleSheet("border: none; margin: 0px; padding: 0px;")

        splitter = QSplitter(Qt.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.left_widget = self._create_pane(self.left_editor_tab)
        self.right_widget = self._create_pane(self.right_editor_tab)

        splitter.addWidget(self.left_widget)
        splitter.addWidget(self.right_widget)

        self.left_widget.setMinimumWidth(250)
        self.right_widget.setMinimumWidth(250)

        main_layout.addWidget(splitter)

        self.left_editor_tab.editor.installEventFilter(self)
        self.right_editor_tab.editor.installEventFilter(self)

        self._update_active_visuals()

    def _create_pane(self, editor_tab):
        container = QWidget()
        vlayout = QVBoxLayout(container)
        vlayout.setContentsMargins(1, 1, 1, 1)
        vlayout.setSpacing(0)

        title_label = QLabel(editor_tab.tabname)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        title_label.setFixedHeight(26)
        title_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        title_label.setStyleSheet(
            "QLabel { background-color: #252526; color: #d4d4d4; padding: 4px 8px; border-bottom: 2px solid #252526; }"
        )
        vlayout.addWidget(title_label)

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
                    try:
                        old_layout.removeWidget(w)
                    except Exception:
                        pass
                w.setParent(container)

        editor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        editor.show()

        minimap.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        try:
            default_w = minimap.width() or 120
        except Exception:
            default_w = 120
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

        minimap._request_update()

        return container

    def eventFilter(self, obj, event):
        if event.type() == QEvent.FocusIn:
            if obj is self.left_editor_tab.editor:
                self._set_active_editor(self.left_editor_tab)
            elif obj is self.right_editor_tab.editor:
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
        if self.active_editor == self.left_editor_tab:
            self.left_widget.title_label.setStyleSheet(base + active)
            self.right_widget.title_label.setStyleSheet(base + inactive)
        else:
            self.right_widget.title_label.setStyleSheet(base + active)
            self.left_widget.title_label.setStyleSheet(base + inactive)

    def get_active_editor_tab(self):
        return self.active_editor

    def get_child_editors(self):
        return [self.left_editor_tab, self.right_editor_tab]
