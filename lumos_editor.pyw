import os
import sys
from functools import partial

from PyQt5.QtCore import (
    QDir,
    QEvent,
    QFileSystemWatcher,
    QRectF,
    QSize,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QFont, QIcon, QKeySequence, QPainterPath, QRegion
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QAction,
    QActionGroup,
    QApplication,
    QDesktopWidget,
    QDialog,
    QFileDialog,
    QFileSystemModel,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStatusBar,
    QTabBar,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from src import (
    AIChat,
    AudioViewer,
    ConfigManager,
    EditorTab,
    FileTreeDelegate,
    FileTreeView,
    FindReplaceDialog,
    ImageViewer,
    PluginDialog,
    PluginManager,
    SourceControlTab,
    SplitEditorTab,
    VideoViewer,
    WelcomeScreen,
    terminal,
)

RADIUS = 8


class TitleBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(40)
        self.setObjectName("TitleBar")
        self.setStyleSheet("background: #252526;")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 8, 4)
        layout.setSpacing(8)

        self.icon_label = QLabel()
        icon = QIcon("resources:/lumos-icon.ico")
        pix = icon.pixmap(QSize(16, 16))
        self.icon_label.setPixmap(pix)
        self.icon_label.setStyleSheet("background: #252526;")
        self.icon_label.setFixedSize(18, 18)
        layout.addWidget(self.icon_label, 0, Qt.AlignVCenter)

        self.title = QLabel("Lumos Editor")
        self.title.setFont(QFont("Segoe UI", 10))
        self.title.setStyleSheet("color: #eee; background: #252526;")
        self.title.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        layout.addWidget(self.title, 0, Qt.AlignVCenter)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.menu_container = QWidget()
        self.menu_layout = QHBoxLayout(self.menu_container)
        self.menu_layout.setContentsMargins(0, 0, 0, 0)
        self.menu_layout.setSpacing(4)
        self.menu_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(self.menu_container, 1)

        btn_size = QSize(34, 28)

        self.min_btn = QToolButton()
        self.min_btn.setIcon(QIcon("resources:/minimize-icon.ico"))
        self.min_btn.setIconSize(QSize(16, 16))
        self.min_btn.setToolTip("Minimize")
        self.min_btn.setFixedSize(btn_size)
        self.min_btn.setObjectName("WindowButton")

        self.max_btn = QToolButton()
        self.max_btn.setIcon(QIcon("resources:/restore-icon.ico"))
        self.max_btn.setIconSize(QSize(16, 16))
        self.max_btn.setToolTip("Maximize")
        self.max_btn.setFixedSize(btn_size)
        self.max_btn.setObjectName("WindowButton")

        self.close_btn = QToolButton()
        self.close_btn.setIcon(QIcon("resources:/close-icon.ico"))
        self.close_btn.setIconSize(QSize(16, 16))
        self.close_btn.setToolTip("Close")
        self.close_btn.setFixedSize(btn_size)
        self.close_btn.setObjectName("WindowButton")

        for b in (self.min_btn, self.max_btn, self.close_btn):
            b.setFocusPolicy(Qt.NoFocus)

        layout.addWidget(self.min_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.max_btn, 0, Qt.AlignVCenter)
        layout.addWidget(self.close_btn, 0, Qt.AlignVCenter)

        self.min_btn.clicked.connect(self.on_min)
        self.max_btn.clicked.connect(self.on_max)
        self.close_btn.clicked.connect(self.on_close)

        self._drag_pos = None
        self._window_pos = None

        self.setCursor(Qt.ArrowCursor)

        self.setStyleSheet(
            """
        QWidget#TitleBar { background: #252526; }
        QToolButton#WindowButton {
            background: #252526;
            color: #cccccc;
            border: none;
            border-radius: 4px;
        }
        QToolButton#WindowButton:hover {
            background: rgba(255,255,255,0.04);
            color: #ffffff;
        }
        """
        )
        self.installEventFilter(self)

    def set_menu_bar(self, menubar):
        while self.menu_layout.count():
            item = self.menu_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
        menubar.installEventFilter(self)
        menubar.setParent(self.menu_container)
        menubar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        menubar.setStyleSheet(
            """
            QMenuBar {
                background: #252526;
                color: #dddddd;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 10px;
            }
            QMenuBar::item:selected {
                background: #333333;
            }
        """
        )

        self.menu_layout.addWidget(menubar)

        for child in menubar.findChildren(QToolButton):
            child.setStyleSheet(
                """
                QToolButton {
                    background: #252526;
                    border: none;
                    border-radius: 4px;
                }
                QToolButton:hover {
                    background: #333333;
                }
            """
            )
            child.setToolTip("Menu")

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseMove:
            if event.buttons() == Qt.LeftButton and self.underMouse():
                delta = event.globalPos() - self.drag_position
                self.window().move(delta)

        elif event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton and self.underMouse():
                self.drag_position = event.globalPos() - self.window().pos()

        elif event.type() == QEvent.MouseButtonDblClick:
            if event.button() == Qt.LeftButton and self.underMouse():
                self.on_max()

        return super().eventFilter(obj, event)

    def on_min(self):
        if self.parent:
            self.parent.showMinimized()

    def on_max(self):
        if not self.parent:
            return
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.max_btn.setToolTip("Maximize")
        else:
            self.parent.showMaximized()
            self.max_btn.setToolTip("Restore")

    def on_close(self):
        if self.parent:
            self.parent.close()


class MainWindow(QWidget):
    project_dir_changed = pyqtSignal(str)

    def __init__(self):

        super().__init__()
        self.config_manager = ConfigManager()
        self.config_manager.set("dir", ".")
        QDir.addSearchPath(
            "resources",
            os.path.join(os.path.dirname(__file__), f".{os.sep}resources"),
        )
        self.setWindowIcon(QIcon("resources:/lumos-icon.ico"))
        self.plugin_manager = PluginManager(self, self.config_manager)
        self.resize(1218, 730)
        self.setMinimumSize(812, 630)
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())
        self.wrap_mode = self.config_manager.get("wrap_mode", False)
        self.current_theme = self.config_manager.get("theme", "default-theme")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)

        self.normal_margins = (10, 10, 10, 10)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(*self.normal_margins)

        self.container = QWidget()
        self.container.setObjectName("container")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(0)
        self.main_layout.addWidget(self.container)

        self.titlebar = TitleBar(self)
        self.central_widget = QWidget()
        self.status_bar = QStatusBar()

        self.container_layout.addWidget(self.titlebar)
        self.container_layout.addWidget(self.central_widget, 1)
        self.container_layout.addWidget(self.status_bar)
        self.status_bar.setStyleSheet(
            """
            QStatusBar {
                background: #252526;
                color: #808080;
                font-size: 18px;
                border-top: 1px solid #1e1e1e;
                padding: 2px 4px;
            }
            QStatusBar QLabel {
                color: #808080;
                font-size: 16px; 
                text-align: right;
                padding-left: 4px;
            }
        """
        )

        self.status_position = QLabel()
        self.status_file = QLabel()
        self.status_folder = QLabel()
        self.status_bar.addPermanentWidget(self.status_position)
        self.status_bar.addPermanentWidget(self.status_file)
        self.status_bar.addPermanentWidget(self.status_folder)

        layout = QHBoxLayout(self.central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.left_container = QWidget()
        left_layout = QVBoxLayout(self.left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        explorer_header = QWidget()
        explorer_header.setFixedHeight(35)
        header_layout = QHBoxLayout(explorer_header)
        header_layout.setContentsMargins(10, 0, 4, 0)
        header_label = QLabel("EXPLORER")
        header_label.setStyleSheet(
            """
            QLabel {
                color: #d4d4d4;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
        """
        )

        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.toggle_tree = QPushButton()
        self.toggle_tree.setIcon(QIcon("resources:/close.ico"))
        self.toggle_tree.setFixedSize(24, 24)
        self.toggle_tree.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                padding: 4px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #323232;
            }
            QPushButton:pressed {
                background: #3a3a3a;
            }
        """
        )
        self.toggle_tree.clicked.connect(self.toggle_file_tree)
        header_layout.addWidget(self.toggle_tree)

        left_layout.addWidget(explorer_header)

        self.folder_section = QWidget()
        folder_layout = QHBoxLayout(self.folder_section)
        folder_layout.setContentsMargins(10, 4, 4, 4)

        folder_name = os.path.basename(os.path.dirname(os.path.abspath(__file__)))
        self.folder_label = QLabel(folder_name.upper())
        self.folder_label.setStyleSheet(
            """
            QLabel {
                color: #e0e0e0;
                font-size: 11px;
                font-weight: 500;
            }
        """
        )
        folder_layout.addWidget(self.folder_label)
        folder_layout.addStretch()

        left_layout.addWidget(self.folder_section)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        splitter.addWidget(self.left_container)

        tabs_container = QWidget()
        tabs_layout = QVBoxLayout(tabs_container)
        tabs_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(QTabBar())
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.setMovable(True)
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
            }
            QTabBar::tab {
                background: #252526;
                color: #d4d4d4;
                padding: 6px 12px;
                border: none;
                min-width: 100px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #1a1a1a;
                border-bottom: 2px solid #0098ff;
            }
            QTabBar::tab:hover {
                background: #323232;
            }
            QTabBar::tab:last {
                margin-right: 0px;
            }
            QTabBar::close-button {
                image: url(resources:/close.ico);
                margin: 2px;
            }
            QTabWidget {
                background: #1a1a1a;
                border: none;
            }
            QTabBar {
                background: #1a1a1a;
                border: none;
                alignment: left;
            }
            QTabBar::scroller { 
                width: 24px;
            }
            QTabBar QToolButton {
                background: #252526;
                border: none;
                margin: 0;
                padding: 0;
                border-radius: 0px;
            }
            QTabBar QToolButton::right-arrow {
                image: url(resources:/chevron-right.ico);
                width: 16px;
                height: 16px;
            }
            QTabBar QToolButton::left-arrow {
                image: url(resources:/chevron-left.ico);
                width: 16px;
                height: 16px;
            }
            QTabBar QToolButton:hover {
                background: #323232;
            }
            QTabBar::tab:first {
                margin-left: 0px;
            }
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
        """
        )

        tabs_layout.addWidget(self.tabs)

        splitter.addWidget(tabs_container)

        self.splitter = splitter
        self.tree_width = 230

        self.splitter.splitterMoved.connect(self.on_splitter_moved)

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath("")
        self.current_project_dir = None

        self.fs_watcher = QFileSystemWatcher()
        self.fs_watcher.directoryChanged.connect(self.on_directory_changed)

        self.left_container.hide()
        self.folder_section.hide()
        self.splitter.setSizes([0, self.width()])

        self.file_tree = FileTreeView(self, self.plugin_manager)

        self.fs_model.setReadOnly(False)
        self.file_tree.setFocusPolicy(Qt.NoFocus)
        self.file_tree.setModel(self.fs_model)
        self.file_tree.setRootIndex(self.fs_model.index(""))
        self.file_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        self.file_tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.file_tree.customContextMenuRequested.connect(self.show_context_menu)
        self.file_tree.setIndentation(12)
        self.file_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.file_tree.setDragEnabled(True)
        self.file_tree.setAcceptDrops(True)
        self.file_tree.setDropIndicatorShown(True)
        self.file_tree.setDragDropMode(QAbstractItemView.DragDrop)

        self.file_tree.setHeaderHidden(True)
        self.file_tree.setAnimated(False)
        self.file_tree.setUniformRowHeights(True)

        self.file_tree.setColumnHidden(1, True)
        self.file_tree.setColumnHidden(2, True)
        self.file_tree.setColumnHidden(3, True)

        self.file_tree.clicked.connect(self.on_file_tree_clicked)

        self.fs_model.setFilter(
            QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files | QDir.Drives
        )

        self.file_tree.setIconSize(QSize(16, 16))

        self.tree_delegate = FileTreeDelegate(self.file_tree, self.plugin_manager)
        self.file_tree.setItemDelegate(self.tree_delegate)

        left_layout.addWidget(self.file_tree)

        self.file_tree.setStyleSheet(
            """
            QTreeView {
                background-color: #252526;
                border: none;
                color: #d4d4d4;
                selection-background-color: transparent;
                padding-left: 5px;
            }
            QTreeView::item {
                padding: 4px;
                border-radius: 4px;
                margin: 1px 4px;
            }
            QTreeView::item:hover {
                background: #323232;
            }
            QTreeView::item:selected {
                background: #323232;
                color: #ffffff;
            }
            QTreeView::branch {
                background: transparent;
                border-image: none;
                padding-left: 2px;
            }
            QTreeView::branch:has-children:!has-siblings:closed,
            QTreeView::branch:closed:has-children:has-siblings {
                image: url(resources:/chevron-right.ico);
                padding: 2px;
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {
                image: url(resources:/chevron-down.ico);
                padding: 2px;
            }
            QTreeView::branch:selected {
                background: #323232;
            }
        """
        )
        self.setObjectName("MainWindow")
        self.setStyleSheet(
            """
            QWidget#MainWindow {
                background-color: #1a1a1a;
                color: #d4d4d4;
            }
            QToolTip {
                background-color: #252526;
                color: #d4d4d4;
                border-radius: 4px;
                padding: 4px;
            }
            QMenuBar {
                background-color: #252526;
                color: #d4d4d4;
                border: none;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
            }
            QMenuBar::item:selected {
                background-color: #323232;
            }
            QMenuBar::item:pressed {
                background-color: #3a3a3a;
            }
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #3a3a3a;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 20px;
                border-radius: 0px;
            }
            QMenu::item:selected {
                background-color: #323232;
            }
            QMenu::separator {
                height: 1px;
                background: #3a3a3a;
                margin: 4px 0px;
            }
            QScrollBar {
                border: none;
                margin: 0px;
                padding: 0px;
            }
            QScrollBar:vertical {
                background: #1a1a1a;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background: #404040;
                min-height: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4a4a4a;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background: #1a1a1a;
                height: 12px;
            }
            QScrollBar::handle:horizontal {
                background: #404040;
                min-width: 20px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4a4a4a;
            }
        """
        )
        self.recent_files = []
        self.load_recent_files()
        self.create_menu_bar()

        self.welcome_screen = WelcomeScreen()
        self.active_tab_widget = self.welcome_screen
        self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)

        self.clipboard_path = None
        self.clipboard_operation = None

        self.check_timer = QTimer()
        self.check_timer.timeout.connect(self.check_path_exists)
        self.check_timer.start(500)

        self.find_replace_dialog = None

        self.cache = {}

    def menuBar(self):
        if not hasattr(self, "_menubar"):
            self._menubar = QMenuBar(self)
        return self._menubar

    def resizeEvent(self, event):
        self.update_mask()
        super().resizeEvent(event)
        self.on_resize(event)

    def update_mask(self):
        path = QPainterPath()
        if self.isMaximized():
            self.main_layout.setContentsMargins(0, 0, 0, 0)
            rect = QRectF(self.rect())
        else:
            rect = QRectF(self.rect()).adjusted(10, 10, -10, -10)
            path.addRoundedRect(rect, float(RADIUS), float(RADIUS))
            self.main_layout.setContentsMargins(*self.normal_margins)
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

    def get_available_themes(self):
        themes_dir = os.path.join(os.path.dirname(__file__), "themes")
        themes = {}
        if not os.path.exists(themes_dir):
            return themes

        for theme_name in os.listdir(themes_dir):
            theme_path = os.path.join(themes_dir, theme_name)
            if os.path.isdir(theme_path) and os.path.exists(
                os.path.join(theme_path, "theme.json")
            ):
                themes[theme_name] = theme_name
        return themes

    def change_theme(self, theme_name):
        if self.current_theme != theme_name:
            self.config_manager.set("theme", theme_name)
            self.request_restart()

    def load_recent_files(self):
        self.recent_files = self.config_manager.get("recent_files", [])

    def open_in_split_view(self, filepath, mode=None):
        current_tab = self.tabs.currentWidget()
        current_index = self.tabs.currentIndex()
        if not isinstance(
            current_tab,
            EditorTab
            | AIChat
            | ImageViewer
            | VideoViewer
            | AudioViewer
            | SourceControlTab,
        ) or isinstance(current_tab, SplitEditorTab):
            QMessageBox.information(
                self,
                "Cannot split view",
                "Split view can only be opened from a regular editor tab.",
            )
            return
        right_editor_tab = EditorTab(
            filepath=filepath,
            main_window=self,
            wrap_mode=self.wrap_mode,
            plugin_manager=self.plugin_manager,
        )
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if mode == None:
                self.cache[os.path.abspath(filepath)] = content
            right_editor_tab.editor.setText(content)
            right_editor_tab.save()
        except Exception:
            QMessageBox.warning(
                self, "Error", f"Cannot read file: {os.path.basename(filepath)}"
            )

            return
        split_view = SplitEditorTab(current_tab, right_editor_tab, mode=mode)
        self.tabs.removeTab(current_index)
        self.tabs.insertTab(
            current_index,
            split_view,
            f"{current_tab.tabname} | {right_editor_tab.tabname}",
        )
        self.tabs.setCurrentIndex(current_index)

    def save_recent_files(self):
        self.config_manager.set("recent_files", self.recent_files)

    def add_to_recent_files(self, file_path):
        abs_path = os.path.abspath(file_path)
        if abs_path in self.recent_files:
            self.recent_files.remove(abs_path)
        self.recent_files.insert(0, abs_path)
        self.recent_files = self.recent_files[:10]

    def update_recent_files_menu(self):
        self.recent_files_menu.clear()
        if not self.recent_files:
            action = QAction("No Recent Files", self)
            action.setEnabled(False)
            self.recent_files_menu.addAction(action)
        else:
            for file_path in self.recent_files:
                action = QAction(os.path.basename(file_path), self)
                action.setData(file_path)
                action.triggered.connect(partial(self.open_specific_file, file_path))
                self.recent_files_menu.addAction(action)

    def show_status_message(self, msg, timeout=2000):
        self.status_bar.showMessage(msg, timeout)

    def file_tree_(self):
        if not self.current_project_dir:
            self.open_folder()
            if not self.current_project_dir:
                return
            self.left_container.show()
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])
        else:
            if not self.left_container.isVisible():
                self.left_container.show()
                total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
                self.splitter.setSizes([self.tree_width, total - self.tree_width])

    def toggle_file_tree(self):
        if not self.current_project_dir:
            self.file_tree_()
            return
        if self.left_container.isVisible():
            self.tree_width = self.splitter.sizes()[0]
            self.left_container.hide()
            self.splitter.setSizes([0, self.width()])
        else:
            self.left_container.show()
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])

    def on_splitter_moved(self, _, __):
        if self.left_container.isVisible():
            self.tree_width = self.splitter.sizes()[0]

    def on_resize(self, event):
        if self.left_container.isVisible():
            total = self.splitter.sizes()[0] + self.splitter.sizes()[1]
            self.splitter.setSizes([self.tree_width, total - self.tree_width])
        super().resizeEvent(event)

    def create_menu_bar(self):
        menubar = self.menuBar()
        self.titlebar.set_menu_bar(menubar)
        menubar.setStyleSheet(
            """
            QMenuBar {
                background-color: #252526;
                border: none;
                padding: 2px;
                min-height: 28px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 4px 8px;
                margin: 0;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: #323232;
            }
            QMenuBar::item:pressed {
                background: #3a3a3a;
            }
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #323232;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 20px;
            }
            QMenu::item:selected {
                background-color: #323232;
            }
            QMenu::separator {
                height: 1px;
                background: #323232;
                margin: 4px 0px;
            }
        """
        )

        self.menus = {}

        file_menu = menubar.addMenu("File")
        self.menus["File"] = file_menu
        file_menu.addAction("New...", self.new_file, QKeySequence.New)

        file_menu.addAction("Open...", self.open_file, QKeySequence.Open)
        file_menu.addAction("Open Folder...", self.open_folder, QKeySequence("Ctrl+K"))
        self.recent_files_menu = file_menu.addMenu("Recent Files")
        self.recent_files_menu.aboutToShow.connect(self.update_recent_files_menu)
        file_menu.addSeparator()
        file_menu.addAction(
            "Close Folder", self.close_folder, QKeySequence("Ctrl+Shift+K")
        )
        file_menu.addAction("Save", self.save_file, QKeySequence.Save)
        file_menu.addAction(
            "Save As...", self.save_file_as, QKeySequence("Ctrl+Shift+S")
        )
        file_menu.addSeparator()
        file_menu.addAction("Restart", self.request_restart, QKeySequence("Ctrl+R"))
        file_menu.addAction("Exit", self.close, QKeySequence("Ctrl+Q"))

        edit_menu = menubar.addMenu("Edit")
        self.menus["Edit"] = edit_menu
        edit_menu.addAction("Undo", self.undo, QKeySequence.Undo)
        edit_menu.addAction("Redo", self.redo, QKeySequence.Redo)
        edit_menu.addSeparator()
        edit_menu.addAction("Cut", self.cut, QKeySequence.Cut)
        edit_menu.addAction("Copy", self.copy, QKeySequence.Copy)
        edit_menu.addAction("Paste", self.paste, QKeySequence.Paste)
        edit_menu.addSeparator()
        edit_menu.addAction("Select All", self.select_all, QKeySequence.SelectAll)
        edit_menu.addSeparator()
        edit_menu.addAction("Find", self.show_find_dialog, QKeySequence("Ctrl+F"))
        edit_menu.addAction("Replace", self.show_replace_dialog, QKeySequence("Ctrl+H"))
        edit_menu.addSeparator()
        edit_menu.addAction(
            "Toggle Wrap Mode", self.toggle_wrap_mode, QKeySequence("Ctrl+W")
        )

        view_menu = menubar.addMenu("View")
        self.menus["View"] = view_menu
        view_menu.addAction(
            "Toggle Explorer Panel", self.toggle_file_tree, QKeySequence("Ctrl+B")
        )
        view_menu.addSeparator()
        self.preview_action = view_menu.addAction(
            "Toggle Markdown Preview", self.toggle_preview, QKeySequence("Ctrl+P")
        )
        self.view_menu = view_menu

        themes_menu = menubar.addMenu("Themes")
        self.menus["Themes"] = themes_menu

        theme_group = QActionGroup(self)
        theme_group.setExclusive(True)

        available_themes = self.get_available_themes()

        if not available_themes:
            no_themes_action = QAction("No themes found", self)
            no_themes_action.setEnabled(False)
            themes_menu.addAction(no_themes_action)
        else:
            for theme_name in sorted(available_themes.keys()):
                action_text = theme_name.replace("-", " ").title()
                action = QAction(action_text, self, checkable=True)

                if theme_name == self.current_theme:
                    action.setChecked(True)

                action.triggered.connect(partial(self.change_theme, theme_name))

                theme_group.addAction(action)
                themes_menu.addAction(action)

        tools_menu = menubar.addMenu("Tools")
        self.menus["Tools"] = tools_menu
        terminal_action = QAction("Open Terminal", self)
        terminal_action.setShortcut(QKeySequence("Ctrl+Shift+`"))
        terminal_action.triggered.connect(
            lambda: terminal.terminal(self.config_manager)
        )
        tools_menu.addAction(terminal_action)

        ai_chat_action = QAction("Open AI Chat", self)
        ai_chat_action.setShortcut(QKeySequence("Ctrl+Shift+A"))
        ai_chat_action.triggered.connect(self.show_ai_chat)
        tools_menu.addAction(ai_chat_action)

        source_control_action = QAction("Open Source Control", self)
        source_control_action.setShortcut(QKeySequence("Ctrl+Shift+G"))
        source_control_action.triggered.connect(self.show_source_control)
        tools_menu.addAction(source_control_action)

        plugins_menu = menubar.addMenu("Plugins")
        self.menus["Plugins"] = plugins_menu

        self.toggle_plugins_action = QAction("Enable Plugins", self, checkable=True)
        is_enabled = self.config_manager.get("plugins_enabled", True)
        self.toggle_plugins_action.setShortcut(QKeySequence("Ctrl+Shift+B"))
        self.toggle_plugins_action.setChecked(is_enabled)
        self.toggle_plugins_action.triggered.connect(self.on_toggle_plugins)
        plugins_menu.addAction(self.toggle_plugins_action)

        plugins_menu.addSeparator()

        manage_plugins_action = QAction("Manage Individual Plugins...", self)
        manage_plugins_action.setShortcut(QKeySequence("Ctrl+Shift+M"))
        manage_plugins_action.triggered.connect(self.open_plugin_manager_dialog)
        plugins_menu.addAction(manage_plugins_action)

        try:
            self.plugin_manager.apply_menu_actions(self.menus)
        except Exception:
            pass

    def show_ai_chat(self):
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), AIChat):
                self.tabs.setCurrentIndex(i)
                return

        ai_chat_tab = AIChat(self)
        self.tabs.addTab(ai_chat_tab, "AI Chat")
        self.tabs.setCurrentWidget(ai_chat_tab)

    def toggle_wrap_mode(self):
        self.wrap_mode = not self.wrap_mode
        self.config_manager.set("wrap_mode", self.wrap_mode)
        self.request_restart()

    def open_plugin_manager_dialog(self):
        dialog = PluginDialog(self.plugin_manager, self.config_manager, self)

        if dialog.exec_() == QDialog.Accepted:
            self.request_restart()

    def on_toggle_plugins(self, checked):
        self.config_manager.set("plugins_enabled", checked)

        if checked:
            self.plugin_manager.reload_plugins()
            self.request_restart()
        else:
            self.plugin_manager.unload_plugins()
            self.request_restart()

    def open_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self,
            "Open Folder",
            (
                os.path.dirname(os.path.abspath(__file__))
                if not self.current_project_dir
                else self.current_project_dir
            ),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )

        if folder:
            self.close_folder()
            self.config_manager.set("dir", os.path.abspath(folder))
            if self.fs_watcher.directories():
                self.fs_watcher.removePaths(self.fs_watcher.directories())
            if self.fs_watcher.files():
                self.fs_watcher.removePaths(self.fs_watcher.files())

            self.current_project_dir = folder
            self.fs_model.setRootPath(folder)
            root_index = self.fs_model.index(folder)
            self.file_tree.setRootIndex(root_index)
            self.folder_label.setText(os.path.basename(folder).upper())
            self.titlebar.title.setText(f"Lumos Editor - {os.path.basename(folder)}")

            self.fs_watcher.addPath(folder)

            self.folder_section.show()
            self.left_container.show()
            self.splitter.setSizes([self.tree_width, self.width() - self.tree_width])
            self.show_status_message(f"Folder - {folder}")

            self.project_dir_changed.emit(folder)

            try:
                self.plugin_manager.trigger_hook("folder_opened", folder_path=folder)
            except Exception:
                pass

    def on_directory_changed(self, path):
        self.fs_model.setRootPath(self.current_project_dir)

        if path not in self.fs_watcher.directories():
            self.fs_watcher.addPath(path)

    def update_folder_title(self):
        folder_name = os.path.basename(self.current_project_dir)
        self.folder_label.setText(folder_name.upper())
        self.titlebar.title.setText(f"Lumos Editor - {folder_name}")

    def select_all(self):
        if editor := self.get_current_editor():
            editor.selectAll()

    def get_current_editor(self):
        current_tab = self.tabs.currentWidget()
        if isinstance(current_tab, SplitEditorTab):
            active_child_tab = current_tab.get_active_editor_tab()
            return active_child_tab.editor if active_child_tab else None
        elif hasattr(current_tab, "editor"):
            return current_tab.editor
        return None

    def undo(self):
        if editor := self.get_current_editor():
            editor.undo()

    def redo(self):
        if editor := self.get_current_editor():
            editor.redo()

    def cut(self):
        if editor := self.get_current_editor():
            editor.cut()

    def copy(self):
        if editor := self.get_current_editor():
            editor.copy()

    def paste(self):
        if editor := self.get_current_editor():
            editor.paste()

    def new_file(self):
        tab = EditorTab(
            main_window=self,
            plugin_manager=self.plugin_manager,
            wrap_mode=self.wrap_mode,
        )
        index = self.tabs.addTab(tab, "Untitled")
        self.tabs.setCurrentIndex(index)
        tab.editor.setFocus()

    def open_file(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Open File", "", "All Files (*.*)")
        if fname:
            self.open_specific_file(fname)

    def on_file_tree_clicked(self, index):
        path = self.fs_model.filePath(index)
        if os.path.isfile(path):
            self.open_specific_file(path)
        else:
            self.show_status_message(f"Folder - {path}")

    def open_specific_file(self, path):
        if not path or not os.path.exists(path):
            QMessageBox.warning(self, "Error", f"File not found:\n{path}")
            if path in self.recent_files:
                self.recent_files.remove(path)
            return
        abs_path = os.path.abspath(path)
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if (
                hasattr(tab, "filepath")
                and tab.filepath
                and os.path.abspath(tab.filepath) == abs_path
            ):
                self.tabs.setCurrentIndex(i)
                return

        try:
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

            file_ext = os.path.splitext(path)[1].lower()

            if file_ext in image_extensions:
                tab = ImageViewer(filepath=abs_path)
            elif file_ext in video_extensions:
                tab = VideoViewer(filepath=abs_path)
            elif file_ext in audio_extensions:
                tab = AudioViewer(filepath=abs_path)
            else:
                tab = EditorTab(
                    filepath=abs_path,
                    main_window=self,
                    wrap_mode=self.wrap_mode,
                    plugin_manager=self.plugin_manager,
                )
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    self.cache[abs_path] = content
                    tab.editor.setText(content)
                    tab.save()
                except (UnicodeDecodeError, IOError):
                    QMessageBox.warning(
                        self,
                        "Warning",
                        f"Could not read file as text: {os.path.basename(path)}",
                    )
                    return

            index = self.tabs.addTab(tab, tab.tabname)
            self.tabs.setCurrentIndex(index)
            if not isinstance(tab, (ImageViewer, AudioViewer, VideoViewer)):
                self.add_to_recent_files(abs_path)
            try:
                if hasattr(self, "plugin_manager") and self.plugin_manager:
                    self.plugin_manager.trigger_hook(
                        "file_opened", filepath=abs_path, tab=tab
                    )
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")

    def save_file(self):

        current = self.tabs.currentWidget()

        if isinstance(
            current,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                AIChat,
                SourceControlTab,
            ),
        ):
            return False

        if isinstance(current, SplitEditorTab):
            target_tab = current.get_active_editor_tab()
            editor = getattr(target_tab, "editor", None)
        else:
            target_tab = current
            editor = getattr(current, "editor", None)

        if editor is None:
            editor = self.get_current_editor()

        if not getattr(target_tab, "filepath", None):
            self.save_file_as()
            if not getattr(target_tab, "filepath", None):
                return False
            self.close_tab(self.tabs.currentIndex())

        path = target_tab.filepath
        content_to_save = editor.text()

        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    content_on_disk = f.read()
            else:
                content_on_disk = None

            if (
                path in self.cache
                and content_on_disk is not None
                and content_on_disk != self.cache.get(path, "")
            ):
                reply = QMessageBox.question(
                    self,
                    "File Conflict Detected",
                    f"This file '{os.path.basename(path)}' has been modified by another program.\n\n"
                    "Do you want to compare the two files or overwrite the file on disk with your changes?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
                )

                if reply == QMessageBox.Cancel:
                    return False
                if reply == QMessageBox.Yes:
                    self.open_in_split_view(path, False)
                    return False

            with open(path, "w", encoding="utf-8") as f:
                f.write(content_to_save)

            self.cache[path] = content_to_save
            target_tab.save()

            self.show_status_message(f"File saved: {path}")
            return True

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not save file: {str(e)}")
            return False

    def save_file_as(self):
        current_tab_widget = self.tabs.currentWidget()

        if isinstance(
            current_tab_widget,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                AIChat,
                SourceControlTab,
            ),
        ):
            return

        target_tab = None
        if isinstance(current_tab_widget, SplitEditorTab):
            target_tab = current_tab_widget.get_active_editor_tab()
        elif isinstance(current_tab_widget, EditorTab):
            target_tab = current_tab_widget

        if not target_tab or not hasattr(target_tab, "editor"):
            return

        fname, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*.*)")

        if fname:
            target_tab.filepath = fname
            name = os.path.basename(fname)
            target_tab.tabname = name

            new_tab_text = ""
            if isinstance(current_tab_widget, SplitEditorTab):
                new_tab_text = f"{current_tab_widget.left_editor_tab.tabname} | {current_tab_widget.right_editor_tab.tabname}"
            else:
                new_tab_text = name

            self.tabs.setTabText(self.tabs.currentIndex(), new_tab_text)

            if self.save_file():
                self.add_to_recent_files(fname)
        else:
            return

    def close_tab(self, index):
        tab_to_close = self.tabs.widget(index)

        tabs_to_check = []
        if isinstance(tab_to_close, SplitEditorTab):
            tabs_to_check.extend(tab_to_close.get_child_editors())
        else:
            tabs_to_check.append(tab_to_close)

        for tab in tabs_to_check:
            if isinstance(tab, EditorTab):
                tab.stop_analysis_loop()
            if hasattr(tab, "is_modified") and tab.is_modified:
                self.tabs.setCurrentIndex(index)
                if isinstance(tab_to_close, SplitEditorTab):
                    tab_to_close._set_active_editor(tab)
                reply = QMessageBox.question(
                    self,
                    "Save Changes",
                    f"This file '{os.path.basename(tab.filepath)}' has unsaved changes. Save before closing?",
                    QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                )
                if reply == QMessageBox.Save:
                    self.save_file()
                    if tab.is_modified:
                        return False
                elif reply == QMessageBox.Cancel:
                    return False

            if (
                hasattr(tab, "filepath")
                and tab.filepath
                and hasattr(self, "plugin_manager")
            ):
                try:
                    self.plugin_manager.trigger_hook(
                        "file_closed",
                        filepath=tab.filepath,
                        tab=tab,
                    )
                except Exception:
                    pass

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.welcome_screen = WelcomeScreen()
            self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)
        return True

    def close_file_tab(self, filepath):
        abs_path = os.path.abspath(filepath)
        tabs_to_remove_indices = set()

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            should_close = False

            if isinstance(tab, SplitEditorTab):
                left_fp = tab.left_editor_tab.filepath
                right_fp = tab.right_editor_tab.filepath

                if (left_fp and os.path.abspath(left_fp) == abs_path) or (
                    right_fp and os.path.abspath(right_fp) == abs_path
                ):

                    should_close = True
                    try:
                        if left_fp and hasattr(self, "plugin_manager"):
                            self.plugin_manager.trigger_hook(
                                "file_closed",
                                filepath=left_fp,
                                tab=tab.left_editor_tab,
                            )
                        if right_fp and hasattr(self, "plugin_manager"):
                            self.plugin_manager.trigger_hook(
                                "file_closed",
                                filepath=right_fp,
                                tab=tab.right_editor_tab,
                            )
                    except Exception:
                        pass

            elif (
                hasattr(tab, "filepath")
                and tab.filepath
                and os.path.abspath(tab.filepath) == abs_path
            ):
                should_close = True
                try:
                    if hasattr(self, "plugin_manager"):
                        self.plugin_manager.trigger_hook(
                            "file_closed",
                            filepath=tab.filepath,
                            tab=tab,
                        )
                except Exception:
                    pass

            if should_close:
                tabs_to_remove_indices.add(i)

        for i in sorted(list(tabs_to_remove_indices), reverse=True):
            self.tabs.removeTab(i)

        if self.tabs.count() == 0:
            self.welcome_screen = WelcomeScreen()
            self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)

    def request_restart(self):
        QApplication.instance().setProperty("restart_requested", True)
        self.close()

    def closeEvent(self, event):
        is_restarting = QApplication.instance().property("restart_requested")
        self.save_recent_files()

        for i in reversed(range(self.tabs.count())):
            if not self.close_tab(i):
                event.ignore()
                if is_restarting:
                    QApplication.instance().setProperty("restart_requested", False)
                return
        event.accept()

    def show_context_menu(self, position):
        index = self.file_tree.indexAt(position)
        context_menu = QMenu()
        context_menu.setStyleSheet(
            """
            QMenu {
                background-color: #252526;
                color: #d4d4d4;
                border: 1px solid #323232;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 24px 6px 20px;
            }
            QMenu::item:selected {
                background-color: #323232;
            }
            QMenu::separator {
                height: 1px;
                background: #323232;
                margin: 4px 0px;
            }
        """
        )

        if index.isValid():
            path = self.fs_model.filePath(index)
            is_dir = os.path.isdir(path)

            if not is_dir:
                context_menu.addSeparator()
                open_side_action = context_menu.addAction("Split View")
                open_side_action.triggered.connect(
                    lambda: self.open_in_split_view(path)
                )

            if is_dir:
                new_file_action = context_menu.addAction("New File")
                new_file_action.triggered.connect(lambda: self.create_new_file(index))
                new_folder_action = context_menu.addAction("New Folder")
                new_folder_action.triggered.connect(
                    lambda: self.create_new_folder(index)
                )
                context_menu.addSeparator()

            copy_action = context_menu.addAction("Copy")
            copy_action.triggered.connect(lambda: self.copy_item(index))
            cut_action = context_menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.cut_item(index))

            if self.clipboard_path:
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: self.paste_item(index))

            context_menu.addSeparator()
            delete_action = context_menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self.delete_item(index))
            rename_action = context_menu.addAction("Rename")
            rename_action.triggered.connect(lambda: self.rename_item(index))
        else:
            new_file_action = context_menu.addAction("New File")
            new_file_action.triggered.connect(lambda: self.create_new_file(index))
            new_folder_action = context_menu.addAction("New Folder")
            new_folder_action.triggered.connect(lambda: self.create_new_folder(index))
            if self.clipboard_path:
                context_menu.addSeparator()
                paste_action = context_menu.addAction("Paste")
                paste_action.triggered.connect(lambda: self.paste_item(index))

        context_menu.exec_(self.file_tree.viewport().mapToGlobal(position))

    def check_path_exists(self):
        if self.current_project_dir and not os.path.exists(self.current_project_dir):
            QMessageBox.warning(
                self,
                "Directory Error",
                "This working directory no longer exists.\nPlease reopen a valid folder.",
            )
            self.current_project_dir = None
            self.left_container.hide()
            self.folder_section.hide()
            self.splitter.setSizes([0, self.width()])
            return False

        tabs_to_close = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "filepath") and tab.filepath:
                if not os.path.exists(tab.filepath):
                    QMessageBox.warning(
                        self,
                        "File Error",
                        f"This file '{os.path.basename(tab.filepath)}' no longer exists.",
                    )
                    tabs_to_close.append(i)

        for i in reversed(tabs_to_close):
            self.tabs.removeTab(i)

        return True

    def create_new_file(self, index):
        if not self.check_path_exists():
            return

        if index.isValid():
            path = self.fs_model.filePath(index)
            if not os.path.isdir(path):
                path = os.path.dirname(path)
        else:
            path = self.current_project_dir

        self.show_status_message(f"Folder - {path}")

        file_name, ok = QInputDialog.getText(
            self, "New File", "Enter file name:", QLineEdit.Normal, ""
        )

        if ok and file_name:
            file_path = os.path.join(path, file_name)

            if os.path.exists(file_path):
                QMessageBox.warning(self, "Error", "File already exists!")
                return

            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("")

                self.open_specific_file(file_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create file: {str(e)}")

    def create_new_folder(self, index):
        if not self.check_path_exists():
            return

        if index.isValid():
            path = self.fs_model.filePath(index)
            if not os.path.isdir(path):
                path = os.path.dirname(path)
        else:
            path = self.current_project_dir

        self.show_status_message(f"Folder - {path}")

        folder_name, ok = QInputDialog.getText(
            self, "New Folder", "Enter folder name:", QLineEdit.Normal, ""
        )
        if ok and folder_name:
            folder_path = os.path.join(path, folder_name)
            try:
                os.makedirs(folder_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create folder: {str(e)}")

    def copy_item(self, index):
        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        self.clipboard_path = path
        self.clipboard_operation = "copy"

    def cut_item(self, index):
        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        self.close_file_tab(path)
        self.clipboard_path = path
        self.clipboard_operation = "cut"

    def paste_item(self, index):
        if not self.check_path_exists():
            return

        if not self.clipboard_path:
            return

        target_path = self.current_project_dir
        if index.isValid():
            path = self.fs_model.filePath(index)
            target_path = path if os.path.isdir(path) else os.path.dirname(path)

        self.show_status_message(f"Folder - {target_path}")

        try:
            filename = os.path.basename(self.clipboard_path)
            new_path = os.path.join(target_path, filename)

            if os.path.exists(new_path):
                self.close_file_tab(new_path)
                reply = QMessageBox.question(
                    self,
                    "File exists",
                    "File already exists. Replace it?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.No:
                    return

            import shutil

            if self.clipboard_operation == "copy":
                if os.path.isdir(self.clipboard_path):
                    if os.path.exists(new_path):
                        shutil.rmtree(new_path)
                    shutil.copytree(self.clipboard_path, new_path)
                else:
                    shutil.copy2(self.clipboard_path, new_path)
            else:
                self.close_file_tab(self.clipboard_path)
                if os.path.exists(new_path):
                    if os.path.isdir(new_path):
                        shutil.rmtree(new_path)
                    else:
                        os.remove(new_path)
                shutil.move(self.clipboard_path, new_path)
                self.clipboard_path = None
                self.clipboard_operation = None

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Operation failed: {str(e)}")

    def delete_item(self, index):
        if not self.check_path_exists():
            return

        path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(path)}")
        try:
            reply = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete '{os.path.basename(path)}'?",
                QMessageBox.Yes | QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                self.close_file_tab(path)
                import shutil

                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not delete: {str(e)}")

    def rename_item(self, index):
        if not self.check_path_exists():
            return

        old_path = self.fs_model.filePath(index)
        self.show_status_message(f"Folder - {os.path.dirname(old_path)}")
        old_name = os.path.basename(old_path)

        new_name, ok = QInputDialog.getText(
            self, "Rename", "Enter new name:", QLineEdit.Normal, old_name
        )

        if ok and new_name and new_name != old_name:
            try:
                new_path = os.path.join(os.path.dirname(old_path), new_name)
                self.close_file_tab(old_path)
                os.rename(old_path, new_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not rename: {str(e)}")

    def on_tab_changed(self, index):
        if self.active_tab_widget:
            if isinstance(self.active_tab_widget, EditorTab):
                self.active_tab_widget.stop_analysis_loop()
            elif isinstance(self.active_tab_widget, SplitEditorTab):
                self.active_tab_widget.left_editor_tab.stop_analysis_loop()
                self.active_tab_widget.right_editor_tab.stop_analysis_loop()

        if index == -1 or (current_widget := self.tabs.widget(index)) is None:
            self.active_tab_widget = None
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
            return

        self.active_tab_widget = current_widget
        tab = current_widget

        if isinstance(tab, SplitEditorTab):
            active_editor_tab = tab.get_active_editor_tab()
            if active_editor_tab:
                active_editor_tab.start_analysis_loop()
                line, col = active_editor_tab.editor.getCursorPosition()
                self.show_status_message("Ready")
                self.status_position.setText(f"Ln {line + 1}, Col {col + 1}")
                if active_editor_tab.filepath:
                    self.status_file.setText(
                        f"File - {os.path.basename(active_editor_tab.filepath)}"
                    )
                else:
                    self.status_file.setText("File - Untitled")
                self.status_folder.clear()

        elif isinstance(tab, EditorTab):
            tab.start_analysis_loop()
            line, col = tab.editor.getCursorPosition()
            self.show_status_message("Ready")
            self.status_position.setText(f"Ln {line + 1}, Col {col + 1}")
            if tab.filepath:
                self.status_file.setText(f"File - {os.path.basename(tab.filepath)}")
            else:
                self.status_file.setText("File - Untitled")
            self.status_folder.clear()

        elif isinstance(
            tab,
            (
                WelcomeScreen,
                ImageViewer,
                AudioViewer,
                VideoViewer,
                SourceControlTab,
                AIChat,
            ),
        ):
            status_map = {
                "WelcomeScreen": "Welcome",
                "ImageViewer": "Image Viewer",
                "AudioViewer": "Audio Viewer",
                "VideoViewer": "Video Viewer",
                "SourceControlTab": "Source Control",
                "AIChat": "AI Chat",
            }
            status_message = status_map.get(type(tab).__name__, "Ready")
            self.show_status_message(status_message)
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()

    def toggle_preview(self):
        current_tab = self.tabs.currentWidget()
        target_editor = None

        if isinstance(current_tab, SplitEditorTab):
            QMessageBox.warning(
                self,
                "Warning",
                "Toggle Markdown preview is disabled due to split structure incompatibility, which may cause the editor to freeze.",
            )

        elif isinstance(current_tab, EditorTab):
            target_editor = current_tab

        if (
            target_editor
            and hasattr(target_editor, "is_markdown")
            and target_editor.is_markdown
        ):
            target_editor.toggle_markdown_preview()

    def close_folder(self):
        if self.current_project_dir:
            closed_folder_path = self.current_project_dir

            try:
                self.plugin_manager.trigger_hook(
                    "folder_closed", folder_path=closed_folder_path
                )
            except Exception:
                pass

            if self.fs_watcher.directories():
                self.fs_watcher.removePaths(self.fs_watcher.directories())
            if self.fs_watcher.files():
                self.fs_watcher.removePaths(self.fs_watcher.files())

            self.current_project_dir = None

            self.fs_model.setRootPath("")
            self.file_tree.setRootIndex(self.fs_model.index(""))
            self.left_container.hide()
            self.folder_section.hide()
            self.splitter.setSizes([0, self.width()])

            self.titlebar.title.setText("Lumos Editor")
            self.show_status_message("Folder closed")
            self.status_folder.clear()
            self.config_manager.set("dir", ".")
            self.project_dir_changed.emit("")

    def show_find_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        if not self.find_replace_dialog or self.find_replace_dialog.editor != editor:
            self.find_replace_dialog = FindReplaceDialog(self, editor)
        self.find_replace_dialog.replace_input.hide()
        self.find_replace_dialog.replace_label.hide()
        self.find_replace_dialog.replace_btn.hide()
        self.find_replace_dialog.replace_all_btn.hide()
        self.find_replace_dialog.show()
        self.find_replace_dialog.find_input.setFocus()

    def show_replace_dialog(self):
        editor = self.get_current_editor()
        if not editor:
            return
        if not self.find_replace_dialog or self.find_replace_dialog.editor != editor:
            self.find_replace_dialog = FindReplaceDialog(self, editor)
        self.find_replace_dialog.replace_input.show()
        self.find_replace_dialog.replace_label.show()
        self.find_replace_dialog.replace_btn.show()
        self.find_replace_dialog.replace_all_btn.show()
        self.find_replace_dialog.show()
        self.find_replace_dialog.replace_input.setFocus()

    def show_source_control(self):
        if not self.current_project_dir:
            QMessageBox.information(
                self,
                "Source Control",
                "Please open a folder first to use Source Control.",
            )
            return
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SourceControlTab):
                self.tabs.setCurrentIndex(i)
                return

        source_control_tab = SourceControlTab(self)
        self.project_dir_changed.connect(source_control_tab.on_project_changed)
        self.tabs.addTab(source_control_tab, "Source Control")
        self.tabs.setCurrentWidget(source_control_tab)


def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    QApplication.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    QApplication.setAttribute(Qt.AA_ForceRasterWidgets)
    QApplication.setAttribute(Qt.AA_CompressHighFrequencyEvents)

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication([])
    app.setStyle("Fusion")

    app.setProperty("restart_requested", True)
    while app.property("restart_requested"):
        app.setProperty("restart_requested", False)
        window = MainWindow()
        window.show()

        exit_code = app.exec_()

        if not app.property("restart_requested"):
            sys.exit(exit_code)


if __name__ == "__main__":
    main()
