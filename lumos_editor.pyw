import sys
import os
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from src.editor_tab import EditorTab
from src.ai_chat import AIChat
from src.file_tree import FileTreeDelegate, FileTreeView
from src.welcome_screen import WelcomeScreen
import src.terminal as terminal
from src.media_viewer import ImageViewer, AudioViewer, VideoViewer
from src.source_control import SourceControlTab
from src.plugin_manager import PluginManager, PluginDialog, ConfigManager
from src.find_replace import FindReplaceDialog

from PyQt5.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)
from PyQt5.QtCore import Qt


class MainWindow(QMainWindow):
    def __init__(self):

        super().__init__()
        self.config_manager = ConfigManager()

        self.config_manager.set("dir", ".")
        self.setWindowTitle("Lumos Editor")
        QDir.addSearchPath(
            "icons",
            os.path.join(os.path.dirname(__file__), f".{os.sep}src{os.sep}icons"),
        )
        self.setWindowIcon(QIcon("icons:/lumos-icon.ico"))
        self.plugin_manager = PluginManager(self, self.config_manager)
        self.resize(1300, 900)
        self.wrap_mode = self.config_manager.get("wrap_mode", False)
        self.status_bar = QStatusBar()
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
        self.setStatusBar(self.status_bar)

        self.status_position = QLabel()
        self.status_file = QLabel()
        self.status_folder = QLabel()
        self.status_bar.addPermanentWidget(self.status_position)
        self.status_bar.addPermanentWidget(self.status_file)
        self.status_bar.addPermanentWidget(self.status_folder)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QHBoxLayout(central_widget)
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
                color: #808080;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
        """
        )

        header_layout.addWidget(header_label)
        header_layout.addStretch()

        self.toggle_tree = QPushButton()
        self.toggle_tree.setIcon(QIcon("icons:/close.ico"))
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
                image: url(icons:/close.ico);
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
                image: url(icons:/chevron-right.ico);
                width: 16px;
                height: 16px;
            }
            QTabBar QToolButton::left-arrow {
                image: url(icons:/chevron-left.ico);
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
        self.resizeEvent = self.on_resize

        self.fs_model = QFileSystemModel()
        self.fs_model.setRootPath("")
        self.current_project_dir = None

        self.fs_watcher = QFileSystemWatcher()
        self.fs_watcher.directoryChanged.connect(self.on_directory_changed)
        self.fs_watcher.fileChanged.connect(self.on_file_changed)

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
                image: url(icons:/chevron-right.ico);
                padding: 2px;
            }
            QTreeView::branch:open:has-children:!has-siblings,
            QTreeView::branch:open:has-children:has-siblings {
                image: url(icons:/chevron-down.ico);
                padding: 2px;
            }
            QTreeView::branch:selected {
                background: #323232;
            }
        """
        )

        self.setStyleSheet(
            """
            QMainWindow {
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


        self.preview_action = QAction("Toggle Preview", self)
        self.preview_action.setShortcut(QKeySequence("Ctrl+P"))
        self.preview_action.triggered.connect(self.toggle_preview)

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
        file_menu.addAction(
            "Close Folder", self.close_folder, QKeySequence("Ctrl+Shift+K")
        )
        file_menu.addAction("Save", self.save_file, QKeySequence.Save)
        file_menu.addAction(
            "Save As...", self.save_file_as, QKeySequence("Ctrl+Shift+S")
        )
        file_menu.addSeparator()
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
        edit_menu.addAction("Toggle Wrap Mode", self.toggle_wrap_mode, QKeySequence("Ctrl+W"))

        view_menu = menubar.addMenu("View")
        self.menus["View"] = view_menu
        view_menu.addAction("Toggle Explorer Panel", self.toggle_file_tree, QKeySequence("Ctrl+B"))
        view_menu.addSeparator()
        self.preview_action = view_menu.addAction("Toggle Markdown Preview", self.toggle_preview, QKeySequence("Ctrl+P"))
        self.view_menu = view_menu

        tools_menu = menubar.addMenu("Tools")
        self.menus["Tools"] = tools_menu
        terminal_action = QAction("Open Terminal", self)
        terminal_action.setShortcut(QKeySequence("Ctrl+Shift+`"))
        terminal_action.triggered.connect(lambda: terminal.terminal(self.config_manager))
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
        QMessageBox.information(
            self,
            "Wrap Mode",
            f"Wrap mode has been {'enabled' if self.wrap_mode else 'disabled'}. Please restart the editor for changes to apply.",
        )

    def open_plugin_manager_dialog(self):
        dialog = PluginDialog(self.plugin_manager, self.config_manager, self)

        if dialog.exec_() == QDialog.Accepted:
            QMessageBox.information(
                self,
                "Settings Saved",
                "Plugin settings have been saved. Please restart the editor for changes to apply.",
            )

    def on_toggle_plugins(self, checked):
        self.config_manager.set("plugins_enabled", checked)

        if checked:
            self.plugin_manager.reload_plugins()
            QMessageBox.information(
                self,
                "Plugins Enabled",
                "Plugins have been enabled. Please restart the editor for the changes to take full effect.",
            )
        else:
            self.plugin_manager.unload_plugins()
            QMessageBox.information(
                self,
                "Plugins Disabled",
                "Plugins have been disabled. Please restart the editor for the changes to take full effect.",
            )

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
            self.setWindowTitle(f"Lumos Editor - {os.path.basename(folder)}")

            self.fs_watcher.addPath(folder)

            self.folder_section.show()
            self.left_container.show()
            self.splitter.setSizes([self.tree_width, self.width() - self.tree_width])
            self.show_status_message(f"Folder - {folder}")

    def on_directory_changed(self, path):
        self.fs_model.setRootPath(self.current_project_dir)

        if path not in self.fs_watcher.directories():
            self.fs_watcher.addPath(path)

    def close_tabs_for_deleted_file(self, path):
        tabs_to_remove = []
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, EditorTab):
                tab.stop_analysis_loop()
            if hasattr(tab, "filepath") and tab.filepath == path:
                tabs_to_remove.append(i)
        for i in reversed(tabs_to_remove):
            self.tabs.removeTab(i)

    def on_file_changed(self, path):
        if not os.path.exists(path):
            self.close_tabs_for_deleted_file(path)

            if path in self.fs_watcher.files():
                self.fs_watcher.removePath(path)
            return

        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if hasattr(tab, "filepath") and tab.filepath == path:
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                    if not tab.is_modified:
                        tab.editor.setText(content)
                except:
                    pass
                break

        if os.path.exists(path) and path not in self.fs_watcher.files():
            self.fs_watcher.addPath(path)

    def update_folder_title(self):
        folder_name = os.path.basename(self.current_project_dir)
        self.folder_label.setText(folder_name.upper())
        self.setWindowTitle(f"Lumos Editor - {folder_name}")

    def select_all(self):
        if editor := self.get_current_editor():
            editor.selectAll()

    def get_current_editor(self):
        current = self.tabs.currentWidget()
        return current.editor if current and hasattr(current, "editor") else None

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
        tab = EditorTab(main_window=self, plugin_manager=self.plugin_manager, wrap_mode=self.wrap_mode)
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
                ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico",
                ".webp", ".tiff", ".tif", ".svg", ".psd", ".raw",
                ".heif", ".heic",
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
            try:
                if hasattr(self, 'plugin_manager') and self.plugin_manager:
                    self.plugin_manager.trigger_hook(
                        'file_opened', filepath=abs_path, tab=tab, main_window=self
                    )
            except Exception:
                pass
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file: {str(e)}")

    def save_file(self):
        current = self.tabs.currentWidget()
        if not current or not hasattr(current, "editor") or not current.editor:
            return
        if isinstance(current, WelcomeScreen | ImageViewer | AudioViewer | VideoViewer | AIChat | SourceControlTab):
            return
        if not current.filepath:
            self.save_file_as()
        else:
            content = current.editor.text().encode("utf-8")
            try:
                with open(current.filepath, "r") as f:
                    existing_content = f.read()
                if existing_content != self.cache.get(current.filepath, ""):
                    QMessageBox.warning(
                        self,
                        "Warning",
                        "The file has been modified outside of the editor. Please reload it before saving.",
                    )
                    return
                with open(current.filepath, "wb") as f:
                    f.write(content)
                current.save()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not save file: {str(e)}")

    def save_file_as(self):
        current = self.tabs.currentWidget()
        if not current or not hasattr(current, "editor") or not current.editor:
            return
        if isinstance(current, WelcomeScreen | ImageViewer | AudioViewer | VideoViewer | AIChat | SourceControlTab):
            return
        fname, _ = QFileDialog.getSaveFileName(self, "Save File", "", "All Files (*.*)")
        if fname:
            current.filepath = fname
            name = os.path.basename(fname)
            current.tabname = name
            self.tabs.setTabText(self.tabs.currentIndex(), name)
            self.save_file()
        else:
            return

    def close_tab(self, index):
        tab = self.tabs.widget(index)

        if isinstance(tab, EditorTab):
            tab.stop_analysis_loop()

        if hasattr(tab, "is_modified") and tab.is_modified:
            reply = QMessageBox.question(
                self,
                "Save Changes",
                "This file has unsaved changes. Save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if reply == QMessageBox.Save:
                self.save_file()
                if self.tabs.widget(index).is_modified:
                    return False
            elif reply == QMessageBox.Cancel:
                return False
            elif reply == QMessageBox.Discard:
                pass

        try:
            if hasattr(tab, 'filepath') and tab.filepath and hasattr(self, 'plugin_manager'):
                self.plugin_manager.trigger_hook('file_closed', filepath=tab.filepath, tab=tab, main_window=self)
        except Exception:
            pass

        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.welcome_screen = WelcomeScreen()
            self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)
        return True

    def close_file_tab(self, filepath):
        abs_path = os.path.abspath(filepath)
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if (
                hasattr(tab, "filepath")
                and tab.filepath
                and os.path.abspath(tab.filepath) == abs_path
            ):
                try:
                    if hasattr(tab, 'filepath') and tab.filepath and hasattr(self, 'plugin_manager'):
                        self.plugin_manager.trigger_hook('file_closed', filepath=tab.filepath, tab=tab, main_window=self)
                except Exception:
                    pass

                self.tabs.removeTab(i)
                break

        if self.tabs.count() == 0:
            self.welcome_screen = WelcomeScreen()
            self.tabs.addTab(self.welcome_screen, self.welcome_screen.tabname)

    def closeEvent(self, event):
        for i in reversed(range(self.tabs.count())):
            if not self.close_tab(i):
                event.ignore()
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
        if self.active_tab_widget and isinstance(self.active_tab_widget, EditorTab):
            self.active_tab_widget.stop_analysis_loop()

        if index == -1:
            if hasattr(self, 'view_menu'):
                self.view_menu.menuAction().setVisible(False)
            self.active_tab_widget = None
            return

        current_widget = self.tabs.widget(index)
        if current_widget is None:
            self.active_tab_widget = None
            return

        if isinstance(current_widget, EditorTab):
            current_widget.start_analysis_loop()
        
        self.active_tab_widget = current_widget
        
        is_markdown = getattr(current_widget, "is_markdown", False)
        
        if hasattr(self, 'view_menu'):
            self.view_menu.menuAction().setVisible(is_markdown)

        tab = current_widget
        if isinstance(tab, WelcomeScreen):
            self.show_status_message("Welcome")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif isinstance(tab, ImageViewer):
            self.show_status_message("Image Viewer")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif isinstance(tab, AudioViewer):
            self.show_status_message("Audio Viewer")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif isinstance(tab, VideoViewer):
            self.show_status_message("Video Viewer")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif isinstance(tab, SourceControlTab):
            self.show_status_message("Source Control")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif isinstance(tab, AIChat):
            self.show_status_message("AI Chat")
            self.status_position.clear()
            self.status_file.clear()
            self.status_folder.clear()
        elif hasattr(tab, "editor") and tab.editor:
            line, col = tab.editor.getCursorPosition()
            self.show_status_message("Ready")
            self.status_position.setText(f"Ln {line + 1}, Col {col + 1}")
            if tab.filepath:
                self.status_file.setText(f"File - {tab.filepath}")
            else:
                self.status_file.setText("File - Untitled")
            self.status_folder.clear()

    def toggle_preview(self):
        current = self.tabs.currentWidget()
        if hasattr(current, "is_markdown") and current.is_markdown:
            current.toggle_markdown_preview()

    def close_folder(self):
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

        self.setWindowTitle("Lumos Editor")
        self.show_status_message("Folder closed")
        self.status_folder.clear()
        self.config_manager.set("dir", ".")

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
            return
        for i in range(self.tabs.count()):
            if isinstance(self.tabs.widget(i), SourceControlTab):
                self.tabs.setCurrentIndex(i)
                return
                
        source_control_tab = SourceControlTab(self)
        self.tabs.addTab(source_control_tab, "Source Control")
        self.tabs.setCurrentWidget(source_control_tab)


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
