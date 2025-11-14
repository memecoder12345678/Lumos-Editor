import json
import os
import zipfile
from functools import partial

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import *

from .API import LumosAPI
from .config_manager import ConfigManager
from .lexer import BaseLexer
from .split_editor_tab import SplitEditorTab


class PluginInfo:
    def __init__(self, manifest, zip_path):
        self.manifest = manifest
        self.zip_path = zip_path
        self.lexer_class = None
        self.icon = None


class PluginWorker(QThread):
    showMessageRequested = pyqtSignal(str, str)
    showWarningRequested = pyqtSignal(str, str)
    showErrorRequested = pyqtSignal(str, str)

    askYNQuestionRequested = pyqtSignal(str, str, object)
    askTextInputRequested = pyqtSignal(str, str, str, object)

    addMenuActionRequested = pyqtSignal(str, str, object, object, bool)
    registerHookRequested = pyqtSignal(str, object)

    invokeCallback = pyqtSignal(object, object)

    def __init__(self, plugin_code, plugin_globals, parent=None):
        super().__init__(parent)
        self.plugin_code = plugin_code
        self.plugin_globals = plugin_globals

    def run(self):
        try:
            self.invokeCallback.connect(self._execute_callback)
            exec(self.plugin_code, self.plugin_globals)
        except Exception as e:
            error_msg = f"Plugin crashed with an unhandled exception:\n\n{e}"
            self.showErrorRequested.emit("Plugin Execution Error", error_msg)

    def _execute_callback(self, callback, *args):
        try:
            if callback:
                callback(*args)
        except Exception as e:
            error_msg = f"Error in plugin callback:\n\n{e}"
            self.showErrorRequested.emit("Plugin Callback Error", error_msg)


class PluginManager(QObject):
    def __init__(self, parent, config_manager, plugins_dir="plugins"):
        super().__init__(parent)
        self.parent_widget = parent
        self.config_manager = config_manager
        self.plugins_dir = plugins_dir

        self.extension_map = {}
        self.discovered_plugins = {}
        self.hooks = {}
        self.menu_actions = []
        self.plugins_loaded = False
        self.active_workers = []

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)

        self._scan_for_plugins()

        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def _is_valid_plugin_file(self, plugin_path):
        try:
            with open(plugin_path, "rb") as f:
                return f.read(4) == b"PK\x03\x04"
        except:
            return False

    def _read_plugin_content(self, plugin_path):
        try:
            with zipfile.ZipFile(plugin_path, "r") as zf:
                manifest = self.discovered_plugins.get(
                    os.path.basename(plugin_path), {}
                )
                main_file = manifest.get("mainFile") or "plugin.py"
                return (
                    zf.read(main_file).decode("utf-8")
                    if main_file in zf.namelist()
                    else None
                )
        except Exception as e:
            print(f"Error reading plugin content: {e}")
            return None

    def _scan_for_plugins(self):
        self.discovered_plugins.clear()
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".lmp"):
                plugin_path = os.path.join(self.plugins_dir, filename)
                try:
                    with zipfile.ZipFile(plugin_path, "r") as zf:
                        if "manifest.json" not in zf.namelist():
                            QMessageBox.warning(
                                self.parent_widget,
                                "Plugin Load Error",
                                "manifest.json not found.",
                            )
                        manifest_data = zf.read("manifest.json").decode("utf-8")
                        self.discovered_plugins[filename] = json.loads(manifest_data)
                except Exception as e:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Plugin Scan Error",
                        f"Failed to scan '{filename}':\n\n{e}",
                    )

    def _get_active_editor_tab(self):
        current_widget = self.parent_widget.tabs.currentWidget()
        if isinstance(current_widget, SplitEditorTab):
            return current_widget.get_active_editor_tab()
        return current_widget if hasattr(current_widget, "editor") else None

    def _get_current_file(self):
        active_tab = self._get_active_editor_tab()
        return (
            active_tab.filepath
            if active_tab and hasattr(active_tab, "filepath")
            else None
        )

    def _is_file(self):
        active_tab = self._get_active_editor_tab()
        return bool(
            active_tab and hasattr(active_tab, "filepath") and active_tab.filepath
        )

    def load_enabled_plugins(self):
        if self.plugins_loaded:
            return
        self.unload_plugins()

        for filename, manifest in self.discovered_plugins.items():
            if not self.config_manager.is_plugin_enabled(filename):
                continue

            plugin_path = os.path.join(self.plugins_dir, filename)
            if not self._is_valid_plugin_file(plugin_path):
                continue

            plugin_info = PluginInfo(manifest, plugin_path)
            ptype = manifest.get("pluginType", "hook")
            ptypes = (
                [ptype.lower()]
                if isinstance(ptype, str)
                else [str(x).lower() for x in ptype]
            )

            if "language" in ptypes or "both" in ptypes:
                for ext in manifest.get("fileExtensions", []):
                    self.extension_map[ext.lower()] = plugin_info

            if "hook" in ptypes or "both" in ptypes or manifest.get("mainFile"):
                plugin_content = self._read_plugin_content(plugin_path)
                if not plugin_content:
                    continue

                worker = PluginWorker(None, None, self)

                def ask_yn_question_api(title, question, callback):
                    worker.askYNQuestionRequested.emit(
                        title,
                        question,
                        lambda result: worker.invokeCallback.emit(callback, result),
                    )

                def ask_text_input_api(title, label, default, callback):
                    worker.askTextInputRequested.emit(
                        title,
                        label,
                        default,
                        lambda result: worker.invokeCallback.emit(callback, result),
                    )

                api_functions = {
                    "show_message": partial(worker.showMessageRequested.emit),
                    "show_warning": partial(worker.showWarningRequested.emit),
                    "show_error": partial(worker.showErrorRequested.emit),
                    "add_menu_action": partial(worker.addMenuActionRequested.emit),
                    "register_hook": partial(worker.registerHookRequested.emit),
                    "ask_yn_question": ask_yn_question_api,
                    "ask_text_input": ask_text_input_api,
                    "get_project_dir": lambda: self.parent_widget.current_project_dir,
                    "get_current_file": self._get_current_file,
                    "is_file": self._is_file,
                    "create_project_file": self.parent_widget.plugin_manager.create_project_file,
                    "write_project_file": self.parent_widget.plugin_manager.write_project_file,
                    "read_project_file": self.parent_widget.plugin_manager.read_project_file,
                    "delete_project_file": self.parent_widget.plugin_manager.delete_project_file,
                }

                lumos_api = LumosAPI(api_functions)
                worker.plugin_code = plugin_content
                worker.plugin_globals = {
                    "__builtins__": __import__("builtins").__dict__.copy(),
                    "lumos": lumos_api,
                }

                worker.showMessageRequested.connect(self._handle_show_message)
                worker.showWarningRequested.connect(self._handle_show_warning)
                worker.showErrorRequested.connect(self._handle_show_error)
                worker.askYNQuestionRequested.connect(self._handle_ask_yn_question)
                worker.askTextInputRequested.connect(self._handle_ask_text_input)
                worker.addMenuActionRequested.connect(self.add_menu_action)
                worker.registerHookRequested.connect(self.register_hook)

                worker.start()
                self.active_workers.append(worker)

        self.plugins_loaded = True

    @pyqtSlot(str, object)
    def register_hook(self, event_name, func):
        self.hooks.setdefault(event_name, []).append(func)

    def trigger_hook(self, event_name, **kwargs):
        for fn in list(self.hooks.get(event_name, [])):
            try:
                fn(**kwargs)
            except Exception as e:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Hook Error",
                    f"Error in hook '{event_name}':\n\n{e}",
                )

    @pyqtSlot(str, str, object, object, bool)
    def add_menu_action(
        self, menu_name, text, callback, shortcut=None, checkable=False
    ):
        action = QAction(text, self.parent_widget)
        action.setData(shortcut)
        action.setCheckable(bool(checkable))
        action.triggered.connect(callback)
        self.menu_actions.append((menu_name, action))
        self.apply_menu_actions(self.parent_widget.menus)
        return action

    def apply_menu_actions(self, menus_dict):
        registered_shortcuts = set()
        for menu in menus_dict.values():
            if isinstance(menu, QMenu):
                for core_action in menu.actions():
                    if sc := core_action.shortcut().toString(QKeySequence.NativeText):
                        registered_shortcuts.add(sc.lower())

        for menu_name, action in self.menu_actions:
            menu = menus_dict.get(menu_name)
            if not menu or action in menu.actions():
                continue

            if requested_shortcut := action.data():
                shortcut_str = (
                    QKeySequence(requested_shortcut)
                    .toString(QKeySequence.NativeText)
                    .lower()
                )
                if shortcut_str in registered_shortcuts:
                    action.setShortcut("")
                else:
                    action.setShortcut(QKeySequence(requested_shortcut))
                    registered_shortcuts.add(shortcut_str)
            menu.addAction(action)

    def unload_plugins(self):
        for worker in self.active_workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(2000)
        self.active_workers.clear()
        self.extension_map.clear()
        self.hooks.clear()

        for menu_name, action in self.menu_actions:
            if menu_name in self.parent_widget.menus:
                self.parent_widget.menus[menu_name].removeAction(action)
            action.deleteLater()
        self.menu_actions.clear()
        self.plugins_loaded = False

    def reload_plugins(self):
        self.unload_plugins()
        self._scan_for_plugins()
        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()
        self.apply_menu_actions(self.parent_widget.menus)

    @pyqtSlot(str, str)
    def _handle_show_message(self, title, message):
        QMessageBox.information(self.parent_widget, title, message)

    @pyqtSlot(str, str)
    def _handle_show_warning(self, title, message):
        QMessageBox.warning(self.parent_widget, title, message)

    @pyqtSlot(str, str)
    def _handle_show_error(self, title, message):
        QMessageBox.critical(self.parent_widget, title, message)

    @pyqtSlot(str, str, object)
    def _handle_ask_yn_question(self, title, question, callback):
        reply = QMessageBox.question(
            self.parent_widget, title, question, QMessageBox.Yes | QMessageBox.No
        )
        if callback:
            callback(reply == QMessageBox.Yes)

    @pyqtSlot(str, str, str, object)
    def _handle_ask_text_input(self, title, label, default, callback):
        text, ok = QInputDialog.getText(self.parent_widget, title, label, text=default)
        if callback:
            callback(text if ok else None)

    def create_project_file(self, relpath, content=""):
        proj = self.parent_widget.current_project_dir
        if not proj:
            raise RuntimeError("No project open")
        target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
        if not os.path.abspath(target).startswith(os.path.abspath(proj) + os.sep):
            raise RuntimeError("Target path must be inside the current project")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            f.write(content)
        return target

    def write_project_file(self, relpath, content):
        return self.create_project_file(relpath, content)

    def read_project_file(self, relpath):
        proj = self.parent_widget.current_project_dir
        if not proj:
            raise RuntimeError("No project open")
        target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
        if not os.path.abspath(target).startswith(os.path.abspath(proj) + os.sep):
            raise RuntimeError("Target path must be inside the current project")
        with open(target, "r", encoding="utf-8") as f:
            return f.read()

    def delete_project_file(self, relpath):
        proj = self.parent_widget.current_project_dir
        if not proj:
            raise RuntimeError("No project open")
        target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
        if not os.path.abspath(target).startswith(os.path.abspath(proj) + os.sep):
            raise RuntimeError("Target path must be inside the current project")
        if os.path.isdir(target):
            import shutil

            shutil.rmtree(target)
        else:
            os.remove(target)
        return True

    def _load_lexer_from_plugin(self, plugin_info):
        if plugin_info.lexer_class:
            return plugin_info.lexer_class
        try:
            plugin_content = self._read_plugin_content(plugin_info.zip_path)
            if not plugin_content:
                return None
            lexer_globals = {
                "__builtins__": __import__("builtins").__dict__.copy(),
                "lumos": LumosAPI({"BaseLexer": BaseLexer}),
            }
            exec(plugin_content, lexer_globals)
            plugin_info.lexer_class = lexer_globals.get(
                plugin_info.manifest["lexerClass"]
            )
            return plugin_info.lexer_class
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Lexer Load Error",
                f"Could not load lexer for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def _load_icon_from_plugin(self, plugin_info):
        if plugin_info.icon:
            return plugin_info.icon
        try:
            with zipfile.ZipFile(plugin_info.zip_path, "r") as zf:
                pixmap = QPixmap()
                pixmap.loadFromData(zf.read(plugin_info.manifest["iconFile"]))
                plugin_info.icon = QIcon(pixmap)
                return plugin_info.icon
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Icon Load Error",
                f"Could not load icon for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def get_lexer_for_file(self, filepath):
        if not self.plugins_loaded:
            return None
        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)
        return self._load_lexer_from_plugin(plugin_info) if plugin_info else None

    def get_icon_for_file(self, filepath):
        if not self.plugins_loaded:
            return None
        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)
        return self._load_icon_from_plugin(plugin_info) if plugin_info else None


class PluginDialog(QDialog):
    def __init__(self, plugin_manager, config_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.config_manager = config_manager
        self.setWindowTitle("Manage Plugins")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)
        self.info_label = QLabel(
            "Check plugins to enable. Changes apply after restart."
        )
        self.layout.addWidget(self.info_label)
        self.plugin_list_widget = QListWidget()
        self.layout.addWidget(self.plugin_list_widget)
        self.populate_plugin_list()
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def populate_plugin_list(self):
        for filename, manifest in self.plugin_manager.discovered_plugins.items():
            item = QListWidgetItem(
                f"{manifest['name']} ({filename})", self.plugin_list_widget
            )
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(
                Qt.Checked
                if self.config_manager.is_plugin_enabled(filename)
                else Qt.Unchecked
            )
            item.setData(Qt.UserRole, filename)

    def accept(self):
        for i in range(self.plugin_list_widget.count()):
            item = self.plugin_list_widget.item(i)
            self.config_manager.set_plugin_enabled(
                item.data(Qt.UserRole), item.checkState() == Qt.Checked
            )
        super().accept()
