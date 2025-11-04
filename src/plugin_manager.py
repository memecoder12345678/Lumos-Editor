import os
import zipfile
import json
import sys
from .security import CodeAnalyzerVisitor, PermissionsDialog
from .lexer import BaseLexer
from .API import LumosAPI
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
import ast


class PluginInfo:
    def __init__(self, manifest, zip_path):
        self.manifest = manifest
        self.zip_path = zip_path
        self.lexer_class = None
        self.icon = None


class PluginManager:
    def __init__(self, parent, config_manager, plugins_dir="plugins"):
        self.parent_widget = parent
        self.config_manager = config_manager
        self.plugins_dir = plugins_dir

        self.extension_map = {}
        self.discovered_plugins = {}

        self.hooks = {}

        self.menu_actions = []

        self.plugins_loaded = False

        self.FUNCTIONS_REQUIRING_PERMISSION = {
            "eval",
            "exec",
            "compile",
            "open",
            "exit",
            "quit",
            "getattr",
            "setattr",
            "delattr",
            "globals",
            "locals",
            "input",
        }

        self.SAFE_MODULES = {
            "json",
            "math",
            "random",
            "re",
            "datetime",
            "collections",
            "itertools",
            "functools",
            "typing",
            "argparse",
        }

        self.ALLOWED_FRAMEWORK_MODULES = {"PyQt5", "Qsci"}

        if not os.path.exists(self.plugins_dir):
            os.makedirs(self.plugins_dir)

        self._scan_for_plugins()

        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def _scan_for_plugins(self):
        self.discovered_plugins.clear()
        for filename in os.listdir(self.plugins_dir):
            if filename.endswith(".lumosplugin"):
                plugin_path = os.path.join(self.plugins_dir, filename)
                try:
                    with zipfile.ZipFile(plugin_path, "r") as zf:
                        if "manifest.json" not in zf.namelist():
                            QMessageBox.warning(
                                self.parent_widget,
                                "Plugin Load Error",
                                "manifest.json not found in the plugin archive.",
                            )
                        manifest_data = zf.read("manifest.json").decode("utf-8")
                        manifest = json.loads(manifest_data)
                        self.discovered_plugins[filename] = manifest
                except Exception as e:
                    error_message = f"Failed to scan plugin '{filename}':\n\n{e}"
                    QMessageBox.warning(
                        self.parent_widget, "Plugin Scan Error", error_message
                    )

    def _trigger_security_lockdown(self, plugin_name, function_name):
        title = "CRITICAL SECURITY ALERT"
        msg = (
            f"The plugin <b>'{plugin_name}'</b> has attempted to call the dangerous function "
            f"<b>{function_name}</b> in a hidden way &mdash; this behavior indicates a potentially malicious plugin.\n\n"
            "<b>For your safety, please do the following immediately:</b>\n"
            "\u2022 Save all your current work.\n"
            "\u2022 Close this application as soon as possible.\n"
            f"\u2022 Remove the plugin '<b>{plugin_name}</b>' from the plugins folder.\n"
            "\u2022 Perform a full virus scan on your system using a trusted antivirus program.\n\n"
            "Do <b>NOT</b> reopen the application until you have removed the plugin and ensured your system is clean."
        )

        QMessageBox.critical(self.parent_widget, title, msg)
        self.config_manager.set("plugins_enabled", False)
        self.config_manager.set_plugin_enabled(plugin_name, False)
        self.unload_plugins()

    def _create_hook(self, plugin_name, original_func_name):
        def security_hook(*args, **kwargs):
            self._trigger_security_lockdown(plugin_name, original_func_name)

        return security_hook

    def load_enabled_plugins(self):
        if self.plugins_loaded:
            return

        self.extension_map.clear()
        _real_import = __import__

        for filename, manifest in self.discovered_plugins.items():
            if not self.config_manager.is_plugin_enabled(filename):
                continue

            plugin_path = os.path.join(self.plugins_dir, filename)
            plugin_info = PluginInfo(manifest, plugin_path)

            ptype = manifest.get("pluginType", None)
            if isinstance(ptype, str):
                ptypes = [ptype.lower()]
            elif isinstance(ptype, list):
                ptypes = [str(x).lower() for x in ptype]
            else:
                if manifest.get("fileExtensions"):
                    ptypes = ["language"]
                else:
                    ptypes = ["hook"]

            plugin_info.plugin_type = ptypes

            if "language" in ptypes or "both" in ptypes:
                for ext in manifest.get("fileExtensions", []):
                    self.extension_map[ext.lower()] = plugin_info

            if "hook" in ptypes or "both" in ptypes or manifest.get("mainFile"):
                try:
                    with zipfile.ZipFile(plugin_path, "r") as zf:
                        main_file = manifest.get("mainFile") or "plugin.py"
                        if main_file in zf.namelist():
                            code = zf.read(main_file).decode("utf-8")

                            try:
                                tree = ast.parse(code)
                                analyzer = CodeAnalyzerVisitor()
                                analyzer.visit(tree)
                            except SyntaxError as e:
                                QMessageBox.warning(
                                    self.parent_widget,
                                    "Plugin Syntax Error",
                                    f"Syntax error in plugin '{filename}':\n\n{e}",
                                )
                                continue
                            funcs_to_check = analyzer.called_functions.intersection(
                                self.FUNCTIONS_REQUIRING_PERMISSION
                            )

                            modules_to_check = {
                                mod
                                for mod in analyzer.imported_modules
                                if mod not in self.SAFE_MODULES
                                and mod not in self.ALLOWED_FRAMEWORK_MODULES
                            }

                            if "importlib" in modules_to_check:
                                title = "CRITICAL SECURITY ALERT"
                                msg = (
                                    f"The plugin <b>'{filename}'</b> attempts to import the "
                                    f"dangerous module <b>importlib</b>, which can be used to "
                                    "bypass security restrictions. For your safety,"
                                    " this plugin will not be loaded."
                                )
                                QMessageBox.critical(self.parent_widget, title, msg)
                                run_plugin = False
                                self.config_manager.set_plugin_enabled(filename, False)

                            run_plugin = True
                            if funcs_to_check or modules_to_check:
                                dialog = PermissionsDialog(
                                    filename,
                                    funcs_to_check,
                                    modules_to_check,
                                    self.parent_widget,
                                )
                                if dialog.exec_() != QDialog.Accepted:
                                    run_plugin = False
                                else:
                                    self.SAFE_MODULES.update(modules_to_check)
                                    self.FUNCTIONS_REQUIRING_PERMISSION.difference_update(
                                        funcs_to_check
                                    )

                            if not run_plugin:
                                QMessageBox.warning(
                                    self.parent_widget,
                                    "Plugin Load Canceled",
                                    f"Loading of '{filename}' was canceled by the user.",
                                )
                                continue

                            try:
                                plugin_globals = {
                                    "__builtins__": __import__(
                                        "builtins"
                                    ).__dict__.copy()
                                }

                                for func_name in self.FUNCTIONS_REQUIRING_PERMISSION:
                                    if func_name not in funcs_to_check:
                                        hook = self._create_hook(filename, func_name)
                                        plugin_globals["__builtins__"][func_name] = hook

                                def _get_project_dir():
                                    try:
                                        return getattr(
                                            self.parent_widget,
                                            "current_project_dir",
                                            None,
                                        )
                                    except Exception:
                                        return None

                                def _abs_in_project(target):
                                    proj = _get_project_dir()
                                    if not proj:
                                        return False
                                    try:
                                        return os.path.abspath(target).startswith(
                                            os.path.abspath(proj) + os.sep
                                        )
                                    except Exception:
                                        return False

                                def create_project_file(relpath, content=""):
                                    proj = _get_project_dir()
                                    if not proj:
                                        raise RuntimeError("No project open")
                                    target = (
                                        os.path.join(proj, relpath)
                                        if not os.path.isabs(relpath)
                                        else relpath
                                    )
                                    if not _abs_in_project(target):
                                        raise RuntimeError(
                                            "Target path must be inside the current project"
                                        )
                                    d = os.path.dirname(target)
                                    os.makedirs(d, exist_ok=True)
                                    with open(target, "w", encoding="utf-8") as f:
                                        f.write(content)
                                    return target

                                def write_project_file(relpath, content):
                                    return create_project_file(relpath, content)

                                def read_project_file(relpath):
                                    proj = _get_project_dir()
                                    if not proj:
                                        raise RuntimeError("No project open")
                                    target = (
                                        os.path.join(proj, relpath)
                                        if not os.path.isabs(relpath)
                                        else relpath
                                    )
                                    if not _abs_in_project(target):
                                        raise RuntimeError(
                                            "Target path must be inside the current project"
                                        )
                                    with open(target, "r", encoding="utf-8") as f:
                                        return f.read()

                                def delete_project_file(relpath):
                                    proj = _get_project_dir()
                                    if not proj:
                                        raise RuntimeError("No project open")
                                    target = (
                                        os.path.join(proj, relpath)
                                        if not os.path.isabs(relpath)
                                        else relpath
                                    )
                                    if not _abs_in_project(target):
                                        raise RuntimeError(
                                            "Target path must be inside the current project"
                                        )
                                    if os.path.isdir(target):
                                        import shutil

                                        shutil.rmtree(target)
                                    else:
                                        os.remove(target)
                                    return True

                                def show_message(title, message):
                                    QMessageBox.information(
                                        self.parent_widget, title, message
                                    )

                                def show_warning(title, message):
                                    QMessageBox.warning(
                                        self.parent_widget, title, message
                                    )

                                def show_error(title, message):
                                    QMessageBox.critical(
                                        self.parent_widget, title, message
                                    )

                                def ask_yn_question(title, question):
                                    reply = QMessageBox.question(
                                        self.parent_widget,
                                        title,
                                        question,
                                        QMessageBox.Yes | QMessageBox.No,
                                    )
                                    return reply == QMessageBox.Yes

                                def ask_text_input(title, label, default=""):
                                    text, ok = QInputDialog.getText(
                                        self.parent_widget,
                                        title,
                                        label,
                                        text=default,
                                    )
                                    if ok:
                                        return text
                                    return None

                                def _custom_import(
                                    name,
                                    globals=None,
                                    locals=None,
                                    fromlist=(),
                                    level=0,
                                ):
                                    module_root = name.split(".")[0]
                                    if (
                                        module_root not in self.SAFE_MODULES
                                        and module_root
                                        not in self.ALLOWED_FRAMEWORK_MODULES
                                    ):
                                        self._trigger_security_lockdown(
                                            filename, "__import__"
                                        )
                                    return _real_import(
                                        name, globals, locals, fromlist, level
                                    )

                                lumos_api = LumosAPI(
                                    config_manager=self.config_manager,
                                    plugin_manager=self,
                                    create_project_file=create_project_file,
                                    write_project_file=write_project_file,
                                    read_project_file=read_project_file,
                                    delete_project_file=delete_project_file,
                                    get_project_dir=_get_project_dir,
                                    show_message=show_message,
                                    show_warning=show_warning,
                                    show_error=show_error,
                                    ask_yn_question=ask_yn_question,
                                    ask_text_input=ask_text_input,
                                )
                                plugin_globals["__builtins__"][
                                    "__import__"
                                ] = _custom_import
                                plugin_globals["lumos"] = lumos_api

                                exec(code, plugin_globals)
                                sys.path.pop(0)

                            except Exception as e:
                                QMessageBox.warning(
                                    self.parent_widget,
                                    "Plugin Execution Error",
                                    f"Error executing '{filename}':\n\n{e}",
                                )

                except Exception as e:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Plugin Load Error",
                        f"Failed to process '{filename}':\n\n{e}",
                    )

        self.plugins_loaded = True

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
                    f"Error in plugin hook '{event_name}':\n\n{e}",
                )

    def add_menu_action(
        self, menu_name, text, callback, shortcut=None, checkable=False
    ):
        action = QAction(text, self.parent_widget)
        if shortcut:
            try:
                action.setShortcut(QKeySequence(shortcut))
            except Exception:
                pass
        action.setCheckable(bool(checkable))
        action.triggered.connect(callback)
        self.menu_actions.append((menu_name, action))
        return action

    def apply_menu_actions(self, menus_dict):
        for menu_name, action in list(self.menu_actions):
            menu = menus_dict.get(menu_name)
            if menu and isinstance(menu, QMenu):
                menu.addAction(action)

    def unload_plugins(self):
        self.extension_map.clear()
        self.plugins_loaded = False

    def reload_plugins(self):
        self.unload_plugins()
        self._scan_for_plugins()
        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def _load_lexer_from_plugin(self, plugin_info):
        if plugin_info.lexer_class:
            return plugin_info.lexer_class

        try:
            with zipfile.ZipFile(plugin_info.zip_path, "r") as zf:
                manifest = plugin_info.manifest
                filename = os.path.basename(plugin_info.zip_path)
                lexer_code = zf.read(manifest["lexerFile"]).decode("utf-8")

                try:
                    tree = ast.parse(lexer_code)
                    analyzer = CodeAnalyzerVisitor()
                    analyzer.visit(tree)
                except SyntaxError as e:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Plugin Syntax Error",
                        f"Syntax error in plugin '{filename}':\n\n{e}",
                    )
                    return None
                funcs_to_check = analyzer.called_functions.intersection(
                    self.FUNCTIONS_REQUIRING_PERMISSION
                )
                modules_to_check = {
                    mod
                    for mod in analyzer.imported_modules
                    if mod not in self.SAFE_MODULES
                    and mod not in self.ALLOWED_FRAMEWORK_MODULES
                }
                run_plugin = True
                if funcs_to_check or modules_to_check:
                    dialog = PermissionsDialog(
                        filename,
                        funcs_to_check,
                        modules_to_check,
                        self.parent_widget,
                    )
                    if dialog.exec_() != QDialog.Accepted:
                        run_plugin = False
                    else:
                        self.SAFE_MODULES.update(modules_to_check)
                        self.FUNCTIONS_REQUIRING_PERMISSION.difference_update(
                            funcs_to_check
                        )
                if not run_plugin:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Plugin Load Canceled",
                        f"Loading of '{filename}' was canceled by the user.",
                    )
                    return None

                _real_import = __import__

                def _custom_import(
                    name, globals=None, locals=None, fromlist=(), level=0
                ):
                    module_root = name.split(".")[0]
                    if (
                        module_root not in self.SAFE_MODULES
                        and module_root not in self.ALLOWED_FRAMEWORK_MODULES
                    ):
                        self._trigger_security_lockdown(manifest["name"], "__import__")
                    return _real_import(name, globals, locals, fromlist, level)

                lexer_globals = {
                    "__builtins__": __import__("builtins").__dict__.copy(),
                }

                for func_name in self.FUNCTIONS_REQUIRING_PERMISSION:
                    if func_name not in funcs_to_check:
                        hook = self._create_hook(filename, func_name)
                        lexer_globals["__builtins__"][func_name] = hook

                lexer_globals["__builtins__"]["__import__"] = _custom_import
                lexer_globals["BaseLexer"] = BaseLexer
                exec(lexer_code, lexer_globals)
                sys.path.pop(0)

                plugin_info.lexer_class = lexer_globals.get(manifest["lexerClass"])
                return plugin_info.lexer_class
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Could not load lexer for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def _load_icon_from_plugin(self, plugin_info):
        if plugin_info.icon:
            return plugin_info.icon

        try:
            with zipfile.ZipFile(plugin_info.zip_path, "r") as zf:
                manifest = plugin_info.manifest
                icon_data = zf.read(manifest["iconFile"])
                pixmap = QPixmap()
                pixmap.loadFromData(icon_data)
                plugin_info.icon = QIcon(pixmap)
                return plugin_info.icon
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Could not load icon for {plugin_info.manifest['name']}:\n\n{e}",
            )
            return None

    def get_lexer_for_file(self, filepath):
        if not self.plugins_loaded:
            return None

        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)

        if not plugin_info:
            return None

        return self._load_lexer_from_plugin(plugin_info)

    def get_icon_for_file(self, filepath):
        if not self.plugins_loaded:
            return None

        file_ext = os.path.splitext(filepath)[1].lower()
        plugin_info = self.extension_map.get(file_ext)

        if not plugin_info:
            return None

        return self._load_icon_from_plugin(plugin_info)


class PluginDialog(QDialog):
    def __init__(self, plugin_manager, config_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.config_manager = config_manager

        self.setWindowTitle("Manage Plugins")
        self.setMinimumWidth(400)

        self.layout = QVBoxLayout(self)

        self.info_label = QLabel(
            "Check the plugins you want to enable. Changes will apply after restarting."
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
            item = QListWidgetItem(self.plugin_list_widget)
            item.setText(f"{manifest['name']} ({filename})")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)

            is_enabled = self.config_manager.is_plugin_enabled(filename)
            item.setCheckState(Qt.Checked if is_enabled else Qt.Unchecked)

            item.setData(Qt.UserRole, filename)

    def accept(self):
        for i in range(self.plugin_list_widget.count()):
            item = self.plugin_list_widget.item(i)
            filename = item.data(Qt.UserRole)
            is_enabled = item.checkState() == Qt.Checked
            self.config_manager.set_plugin_enabled(filename, is_enabled)

        super().accept()


class ConfigManager:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.settings = self._load_settings()

    def _load_settings(self):
        defaults = {
            "plugins_enabled": True,
            "individual_plugins": {},
            "dir": ".",
            "wrap_mode": False,
        }
        if not os.path.exists(self.config_file):
            return defaults

        try:
            with open(self.config_file, "r") as f:
                settings = json.load(f)
                for key, value in defaults.items():
                    settings.setdefault(key, value)
                return settings
        except (json.JSONDecodeError, IOError):
            return defaults

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = value
        self._save_settings()

    def _save_settings(self):
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.settings, f, indent=4)
        except IOError as e:
            print(f"Error saving config file: {e}")

    def is_plugin_enabled(self, plugin_filename):
        return self.settings["individual_plugins"].get(plugin_filename, True)

    def set_plugin_enabled(self, plugin_filename, is_enabled):
        self.settings["individual_plugins"][plugin_filename] = is_enabled
        self._save_settings()
