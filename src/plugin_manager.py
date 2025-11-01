import os
import zipfile
import json
import importlib.util
import sys
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence


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

    def load_enabled_plugins(self):
        if self.plugins_loaded:
            return

        self.extension_map.clear()

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

            if "hook" in ptypes or "both" in ptypes or manifest.get("main"):
                try:
                    with zipfile.ZipFile(plugin_path, "r") as zf:
                        main_file = manifest.get("main") or "plugin.py"
                        if main_file in zf.namelist():
                            try:
                                code = zf.read(main_file).decode("utf-8")
                                module_name = f"lumos.plugin.{os.path.splitext(filename)[0]}"
                                spec = importlib.util.spec_from_loader(module_name, loader=None)
                                module = importlib.util.module_from_spec(spec)

                                def _get_project_dir():
                                    try:
                                        return getattr(self.parent_widget, "current_project_dir", None)
                                    except Exception:
                                        return None

                                def _abs_in_project(target):
                                    proj = _get_project_dir()
                                    if not proj:
                                        return False
                                    try:
                                        return os.path.abspath(target).startswith(os.path.abspath(proj) + os.sep)
                                    except Exception:
                                        return False

                                def create_project_file(relpath, content=""):
                                    proj = _get_project_dir()
                                    if not proj:
                                        raise RuntimeError("No project open")
                                    target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
                                    if not _abs_in_project(target):
                                        raise RuntimeError("Target path must be inside the current project")
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
                                    target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
                                    if not _abs_in_project(target):
                                        raise RuntimeError("Target path must be inside the current project")
                                    with open(target, "r", encoding="utf-8") as f:
                                        return f.read()

                                def delete_project_file(relpath):
                                    proj = _get_project_dir()
                                    if not proj:
                                        raise RuntimeError("No project open")
                                    target = os.path.join(proj, relpath) if not os.path.isabs(relpath) else relpath
                                    if not _abs_in_project(target):
                                        raise RuntimeError("Target path must be inside the current project")
                                    if os.path.isdir(target):
                                        import shutil
                                        shutil.rmtree(target)
                                    else:
                                        os.remove(target)
                                    return True

                                def show_message(title, message):
                                    QMessageBox.information(self.parent_widget, title, message)

                                def show_warning(title, message):
                                    QMessageBox.warning(self.parent_widget, title, message)

                                module.__dict__["plugin_manager"] = self
                                module.__dict__["config_manager"] = self.config_manager
                                module.__dict__["parent_widget"] = self.parent_widget
                                module.__dict__["create_project_file"] = create_project_file
                                module.__dict__["write_project_file"] = write_project_file
                                module.__dict__["read_project_file"] = read_project_file
                                module.__dict__["delete_project_file"] = delete_project_file
                                module.__dict__["get_project_dir"] = _get_project_dir
                                module.__dict__["show_message"] = show_message
                                module.__dict__["show_warning"] = show_warning

                                sys.path.insert(0, os.path.abspath("src"))
                                exec(code, module.__dict__)
                                sys.path.pop(0)
                            except Exception as e:
                                QMessageBox.warning(
                                    self.parent_widget,
                                    "Plugin Load Error",
                                    f"Error executing plugin main for {filename}:\n\n{e}",
                                )
                except Exception:
                    pass

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

    def add_menu_action(self, menu_name, text, callback, shortcut=None, checkable=False):
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
                lexer_code = zf.read(manifest["lexerFile"]).decode("utf-8")

                module_name = (
                    f"lumos.plugins.{manifest['languageName'].replace(' ', '_')}"
                )
                spec = importlib.util.spec_from_loader(module_name, loader=None)
                module = importlib.util.module_from_spec(spec)

                sys.path.insert(0, os.path.abspath("src"))
                exec(lexer_code, module.__dict__)
                sys.path.pop(0)

                plugin_info.lexer_class = getattr(module, manifest["lexerClass"])
                return plugin_info.lexer_class
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Plugin Load Error",
                f"Could not load lexer for {plugin_info.manifest['languageName']}:\n\n{e}",
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
                f"Could not load icon for {plugin_info.manifest['languageName']}:\n\n{e}",
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
            item.setText(f"{manifest['languageName']} ({filename})")
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
