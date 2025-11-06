import os
import zipfile
import json
import sys
import uuid
import hashlib
import struct
import tempfile
import shutil
import io
from datetime import datetime
from .security import CodeAnalyzerVisitor, PermissionsDialog
from .lexer import BaseLexer
from .API import LumosAPI
from .lexer import BaseLexer
from .API import LumosAPI
from .config_manager import ConfigManager
from PyQt5.QtWidgets import *
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QPixmap, QKeySequence
import ast


class DigitalSignatureManager:
    def __init__(self):
        self.signature_cache = {}
        
    def generate_signature(self, plugin_content_hash, permissions_data):
        """
        Tạo chữ ký số duy nhất
        """
        # Tạo UUID v4 ngẫu nhiên
        unique_id = uuid.uuid4().hex
        
        # Kết hợp với plugin content hash và permissions
        data_to_sign = f"{unique_id}:{plugin_content_hash}:{json.dumps(permissions_data, sort_keys=True)}"
        digital_signature = hashlib.sha256(data_to_sign.encode('utf-8')).hexdigest()
        
        return digital_signature, unique_id
    
    def verify_signature(self, stored_signature, plugin_content_hash, stored_uuid, permissions_data):
        """
        Xác minh chữ ký số
        """
        data_to_verify = f"{stored_uuid}:{plugin_content_hash}:{json.dumps(permissions_data, sort_keys=True)}"
        expected_signature = hashlib.sha256(data_to_verify.encode('utf-8')).hexdigest()
        return stored_signature == expected_signature
    
    def calculate_plugin_content_hash(self, plugin_path):
        """
        Tính hash của nội dung plugin (bỏ qua phần signature header)
        """
        try:
            with open(plugin_path, 'rb') as f:
                # Bỏ qua signature header nếu có
                content = self._skip_signature_header(f)
                return hashlib.sha256(content).hexdigest()
        except Exception as e:
            print(f"Error calculating plugin hash: {e}")
            return None
    
    def _skip_signature_header(self, file_obj):
        """
        Bỏ qua signature header và đọc phần nội dung thực của plugin
        """
        current_pos = file_obj.tell()
        
        try:
            # Đọc 4 byte đầu để kiểm tra magic number
            magic = file_obj.read(4)
            file_obj.seek(current_pos)  # Reset position
            
            if magic == b'LSPK':  # Lumos Plugin Signature Header
                # Đọc header
                header_size_bytes = file_obj.read(4)
                header_size = struct.unpack('<I', header_size_bytes)[0]
                
                # Bỏ qua toàn bộ header
                file_obj.seek(header_size, os.SEEK_CUR)
            
            # Đọc phần còn lại của file
            return file_obj.read()
            
        except Exception:
            file_obj.seek(current_pos)
            return file_obj.read()


class SignatureHeader:
    """Định dạng header cho chữ ký số"""
    
    MAGIC_NUMBER = b'LSPK'  # Lumos Plugin Signature
    VERSION = 1
    
    @staticmethod
    def create_header(signature_data):
        """Tạo signature header"""
        # Chuyển signature data thành JSON
        json_data = json.dumps(signature_data, indent=2).encode('utf-8')
        
        # Tạo header: magic(4) + version(1) + reserved(3) + data_length(4) + data
        header = struct.pack('<4sB3sI', 
                           SignatureHeader.MAGIC_NUMBER,
                           SignatureHeader.VERSION,
                           b'\x00\x00\x00',  # Reserved
                           len(json_data))
        
        return header + json_data
    
    @staticmethod
    def read_header(file_obj):
        """Đọc signature header từ file"""
        current_pos = file_obj.tell()
        
        try:
            # Đọc magic number
            magic = file_obj.read(4)
            if magic != SignatureHeader.MAGIC_NUMBER:
                file_obj.seek(current_pos)
                return None
            
            # Đọc version và reserved
            version, reserved, data_length = struct.unpack('<B3sI', file_obj.read(8))
            
            # Đọc signature data
            json_data = file_obj.read(data_length)
            signature_data = json.loads(json_data.decode('utf-8'))
            
            return signature_data, 4 + 8 + data_length  # total header size
            
        except Exception as e:
            file_obj.seek(current_pos)
            return None


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

        # Digital signature system
        self.signature_manager = DigitalSignatureManager()
        self.signature_cache = {}

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

    def _read_plugin_signature(self, plugin_path):
        """Đọc chữ ký số từ header của plugin file"""
        if plugin_path in self.signature_cache:
            return self.signature_cache[plugin_path]
            
        try:
            with open(plugin_path, 'rb') as f:
                result = SignatureHeader.read_header(f)
                if result:
                    signature_data, header_size = result
                    self.signature_cache[plugin_path] = signature_data
                    return signature_data
        except Exception as e:
            print(f"Error reading plugin signature: {e}")
        
        return None

    def _write_plugin_signature(self, plugin_path, signature_info):
        """Ghi chữ ký số vào header của plugin file"""
        try:
            # Tính hash hiện tại của plugin (bỏ qua signature header nếu có)
            current_content_hash = self.signature_manager.calculate_plugin_content_hash(plugin_path)
            if not current_content_hash:
                return False
            
            # Thêm metadata vào signature info
            signature_info['plugin_content_hash'] = current_content_hash
            signature_info['timestamp'] = datetime.now().isoformat()
            signature_info['plugin_name'] = os.path.basename(plugin_path)
            
            # Tạo temporary file
            temp_path = plugin_path + ".tmp"
            
            with open(plugin_path, 'rb') as original_file:
                # Bỏ qua signature header cũ nếu có
                content_without_header = self.signature_manager._skip_signature_header(original_file)
                
                # Ghi file mới với signature header
                with open(temp_path, 'wb') as temp_file:
                    # Ghi signature header
                    header_data = SignatureHeader.create_header(signature_info)
                    temp_file.write(header_data)
                    
                    # Ghi nội dung plugin (đã bỏ qua header cũ)
                    temp_file.write(content_without_header)
            
            # Thay thế file cũ
            os.remove(plugin_path)
            shutil.move(temp_path, plugin_path)
            
            # Cập nhật cache
            self.signature_cache[plugin_path] = signature_info
            return True
            
        except Exception as e:
            QMessageBox.warning(
                self.parent_widget,
                "Signature Save Error",
                f"Could not save digital signature to plugin:\n\n{e}"
            )
            return False

    def _check_plugin_authorization(self, plugin_path, funcs_to_check, modules_to_check):
        """
        Kiểm tra xem plugin đã được ủy quyền chưa bằng chữ ký số
        """
        signature_info = self._read_plugin_signature(plugin_path)
        if not signature_info:
            return False
            
        # Kiểm tra content hash để đảm bảo plugin không bị thay đổi
        current_content_hash = self.signature_manager.calculate_plugin_content_hash(plugin_path)
        if not current_content_hash:
            return False
            
        stored_content_hash = signature_info.get('plugin_content_hash')
        if stored_content_hash != current_content_hash:
            # Plugin đã bị thay đổi, cần xác nhận lại
            print(f"Plugin content changed: {plugin_path}")
            return False
        
        # Xác minh chữ ký số
        stored_signature = signature_info.get('digital_signature')
        stored_uuid = signature_info.get('uuid')
        permissions_data = {
            'allowed_functions': signature_info.get('allowed_functions', []),
            'allowed_modules': signature_info.get('allowed_modules', [])
        }
        
        if not stored_signature or not stored_uuid:
            return False
            
        is_valid = self.signature_manager.verify_signature(
            stored_signature, current_content_hash, stored_uuid, permissions_data
        )
        
        if not is_valid:
            return False
            
        # Kiểm tra thời hạn (tuỳ chọn)
        if "timestamp" in signature_info:
            from datetime import datetime, timedelta
            try:
                timestamp = datetime.fromisoformat(signature_info["timestamp"])
                # Ví dụ: signature có hiệu lực trong 90 ngày
                if datetime.now() - timestamp > timedelta(days=90):
                    print(f"Signature expired for: {plugin_path}")
                    return False
            except:
                pass
        
        # Kiểm tra xem signature có bao gồm các permissions hiện tại không
        allowed_funcs = set(signature_info.get('allowed_functions', []))
        allowed_modules = set(signature_info.get('allowed_modules', []))
        
        return (funcs_to_check.issubset(allowed_funcs) and 
                modules_to_check.issubset(allowed_modules))

    def _authorize_plugin(self, plugin_path, funcs_to_check, modules_to_check):
        """Tạo authorization signature cho plugin"""
        # Tính content hash của plugin (bỏ qua signature header nếu có)
        content_hash = self.signature_manager.calculate_plugin_content_hash(plugin_path)
        if not content_hash:
            return False
        
        # Tạo chữ ký số
        permissions_data = {
            'allowed_functions': list(funcs_to_check),
            'allowed_modules': list(modules_to_check)
        }
        
        digital_signature, unique_uuid = self.signature_manager.generate_signature(
            content_hash, permissions_data
        )
        
        # Tạo signature info
        signature_info = {
            'digital_signature': digital_signature,
            'uuid': unique_uuid,
            'plugin_content_hash': content_hash,
            'timestamp': datetime.now().isoformat(),
            'allowed_functions': list(funcs_to_check),
            'allowed_modules': list(modules_to_check),
            'plugin_name': os.path.basename(plugin_path),
            'version': 1
        }
        
        return self._write_plugin_signature(plugin_path, signature_info)

    def _is_valid_plugin_file(self, plugin_path):
        """Kiểm tra xem file plugin có hợp lệ không"""
        try:
            with open(plugin_path, 'rb') as f:
                # Kiểm tra magic number của zip file
                magic = f.read(4)
                return magic == b'PK\x03\x04'  # ZIP file signature
        except:
            return False

    def _read_plugin_content(self, plugin_path):
        """Đọc nội dung plugin (bỏ qua signature header)"""
        try:
            with open(plugin_path, 'rb') as f:
                content = self.signature_manager._skip_signature_header(f)
                
                # Giả sử plugin là zip file, tìm manifest
                with zipfile.ZipFile(io.BytesIO(content), 'r') as zf:
                    manifest = self.discovered_plugins.get(os.path.basename(plugin_path), {})
                    main_file = manifest.get("mainFile") or "plugin.py"
                    
                    if main_file in zf.namelist():
                        return zf.read(main_file).decode('utf-8')
                    else:
                        return None
                        
        except Exception as e:
            print(f"Error reading plugin content: {e}")
            return None

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

    def _get_current_file(self):
        try:
            current_editor = self.parent_widget.tabs.currentWidget()
            if current_editor and hasattr(current_editor, "filepath"):
                return current_editor.filepath
            return None
        except AttributeError:
            return None

    def _is_file(self):
        try:
            current_editor = self.parent_widget.tabs.currentWidget()
            if (
                current_editor
                and hasattr(current_editor, "filepath")
                and current_editor.filepath
            ):
                return True
            return False
        except AttributeError:
            return False

    def _request_plugin_authorization(self, filename, plugin_path, funcs_to_check, modules_to_check):
        """Xử lý việc xin authorization cho plugin"""
        run_plugin = True
        
        # Kiểm tra modules cực kỳ nguy hiểm
        if "importlib" in modules_to_check:
            self._show_critical_security_alert(filename, "importlib")
            return False
        elif "src" in modules_to_check:
            self._show_critical_security_alert(filename, "src") 
            return False

        # Hiện dialog xin authorization
        if funcs_to_check or modules_to_check:
            dialog = PermissionsDialog(
                filename,
                funcs_to_check,
                modules_to_check,
                self.parent_widget,
            )
            
            if dialog.exec_() == QDialog.Accepted:
                if dialog.remember_choice.isChecked():
                    # Tạo authorization signature
                    success = self._authorize_plugin(
                        plugin_path, funcs_to_check, modules_to_check
                    )
                    if success:
                        print(f"Digital signature created for {filename}")
                    else:
                        print(f"Failed to create digital signature for {filename}")
                
                self.SAFE_MODULES.update(modules_to_check)
                self.FUNCTIONS_REQUIRING_PERMISSION.difference_update(funcs_to_check)
            else:
                run_plugin = False
                self.config_manager.set_plugin_enabled(filename, False)
        
        return run_plugin

    def _show_critical_security_alert(self, filename, module_name):
        """Hiển thị cảnh báo bảo mật nghiêm trọng"""
        title = "CRITICAL SECURITY ALERT"
        msg = (
            f"The plugin <b>'{filename}'</b> attempts to import the "
            f"dangerous module <b>{module_name}</b>, which can be used to "
            "bypass security restrictions. For your safety,"
            " this plugin will not be loaded."
        )
        QMessageBox.critical(self.parent_widget, title, msg)
        self.config_manager.set_plugin_enabled(filename, False)

    def load_enabled_plugins(self):
        if self.plugins_loaded:
            return

        self.extension_map.clear()
        _real_import = __import__

        for filename, manifest in self.discovered_plugins.items():
            if not self.config_manager.is_plugin_enabled(filename):
                continue

            plugin_path = os.path.join(self.plugins_dir, filename)
            
            # Kiểm tra xem file có phải là plugin hợp lệ không
            if not self._is_valid_plugin_file(plugin_path):
                continue
                
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
                    # Đọc nội dung plugin (bỏ qua signature header)
                    plugin_content = self._read_plugin_content(plugin_path)
                    if not plugin_content:
                        continue

                    # Phân tích code
                    try:
                        tree = ast.parse(plugin_content)
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
                    run_plugin = True

                    if "importlib" in modules_to_check:
                        self._show_critical_security_alert(filename, "importlib")
                        run_plugin = False
                        self.config_manager.set_plugin_enabled(filename, False)
                    elif "src" in modules_to_check:
                        self._show_critical_security_alert(filename, "src")
                        run_plugin = False
                        self.config_manager.set_plugin_enabled(filename, False)

                    if run_plugin and (funcs_to_check or modules_to_check):
                        # KIỂM TRA AUTHORIZATION BẰNG CHỮ KÝ SỐ
                        if self._check_plugin_authorization(plugin_path, funcs_to_check, modules_to_check):
                            # Đã có authorization hợp lệ, tự động cho phép
                            self.SAFE_MODULES.update(modules_to_check)
                            self.FUNCTIONS_REQUIRING_PERMISSION.difference_update(funcs_to_check)
                            run_plugin = True
                            print(f"Plugin {filename} authorized via digital signature")
                        else:
                            # Cần xin authorization
                            run_plugin = self._request_plugin_authorization(
                                filename, plugin_path, funcs_to_check, modules_to_check
                            )

                    if not run_plugin:
                        QMessageBox.warning(
                            self.parent_widget,
                            "Plugin Load Canceled",
                            f"Loading of '{filename}' was canceled by the user.",
                        )
                        self.config_manager.set_plugin_enabled(filename, False)
                        continue

                    # Thực thi plugin
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
                            {
                                "config_manager": self.config_manager,
                                "plugin_manager": self,
                                "create_project_file": create_project_file,
                                "write_project_file": write_project_file,
                                "read_project_file": read_project_file,
                                "delete_project_file": delete_project_file,
                                "get_project_dir": _get_project_dir,
                                "show_message": show_message,
                                "show_warning": show_warning,
                                "show_error": show_error,
                                "ask_yn_question": ask_yn_question,
                                "ask_text_input": ask_text_input,
                                "get_current_file": self._get_current_file,
                                "is_file": self._is_file,
                            }
                        )

                        plugin_globals["__builtins__"][
                            "__import__"
                        ] = _custom_import
                        plugin_globals["lumos"] = lumos_api

                        exec(plugin_content, plugin_globals)
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

        action.setData(shortcut)

        action.setCheckable(bool(checkable))
        action.triggered.connect(callback)
        self.menu_actions.append((menu_name, action))
        return action

    def apply_menu_actions(self, menus_dict):
        registered_shortcuts = set()
        core_menu_names = set(menus_dict.keys())

        for menu in menus_dict.values():
            if isinstance(menu, QMenu):
                for core_action in menu.actions():
                    shortcut_str = core_action.shortcut().toString(
                        QKeySequence.NativeText
                    )
                    if shortcut_str:
                        registered_shortcuts.add(shortcut_str.lower())

        for menu_name, action in list(self.menu_actions):
            if menu_name not in core_menu_names:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Menu Warning",
                    f"The plugin action '{action.text()}' attempted to add itself to the non-existent menu '{menu_name}'.\n\n"
                    "To ensure stability, plugins can only add items to existing core menus (e.g., 'File', 'Edit'). "
                    "This action has been blocked.",
                )
                continue

            menu = menus_dict.get(menu_name)
            if not (menu and isinstance(menu, QMenu)):
                continue

            requested_shortcut = action.data()
            if requested_shortcut:
                try:
                    shortcut_str = (
                        QKeySequence(requested_shortcut)
                        .toString(QKeySequence.NativeText)
                        .lower()
                    )
                    if shortcut_str in registered_shortcuts:
                        QMessageBox.warning(
                            self.parent_widget,
                            "Plugin Shortcut Conflict",
                            f"The plugin action '{action.text()}' requested the shortcut '{requested_shortcut}', but this shortcut is already in use.\n\n"
                            "The menu item has been added without a shortcut to prevent conflicts.",
                        )
                    else:
                        action.setShortcut(QKeySequence(requested_shortcut))
                        registered_shortcuts.add(shortcut_str)
                except Exception:
                    QMessageBox.warning(
                        self.parent_widget,
                        "Invalid Plugin Shortcut",
                        f"The plugin action '{action.text()}' provided an invalid shortcut format: '{requested_shortcut}'.\n\n"
                        "This shortcut has been ignored.",
                    )

            menu.addAction(action)

    def unload_plugins(self):
        self.extension_map.clear()
        self.hooks.clear()
        for menu_name, action in self.menu_actions:
            try:
                action.deleteLater()
            except:
                pass
        self.menu_actions.clear()
        self.signature_cache.clear()
        self.plugins_loaded = False

    def reload_plugins(self):
        self.unload_plugins()
        self._scan_for_plugins()
        if self.config_manager.get("plugins_enabled", True):
            self.load_enabled_plugins()

    def revoke_plugin_authorization(self, plugin_path):
        """Thu hồi authorization của plugin bằng cách xóa signature header"""
        try:
            # Đọc nội dung plugin (bỏ qua signature header)
            with open(plugin_path, 'rb') as f:
                content_without_header = self.signature_manager._skip_signature_header(f)
            
            # Ghi lại file không có signature header
            temp_path = plugin_path + ".tmp"
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(content_without_header)
            
            # Thay thế file cũ
            os.remove(plugin_path)
            shutil.move(temp_path, plugin_path)
            
            # Xóa cache
            if plugin_path in self.signature_cache:
                del self.signature_cache[plugin_path]
                
            return True
            
        except Exception as e:
            print(f"Error revoking plugin authorization: {e}")
            return False

    def _load_lexer_from_plugin(self, plugin_info):
        if plugin_info.lexer_class:
            return plugin_info.lexer_class

        try:
            # Đọc nội dung plugin (bỏ qua signature header)
            plugin_content = self._read_plugin_content(plugin_info.zip_path)
            if not plugin_content:
                return None

            # Phân tích code lexer
            try:
                tree = ast.parse(plugin_content)
                analyzer = CodeAnalyzerVisitor()
                analyzer.visit(tree)
            except SyntaxError as e:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Syntax Error",
                    f"Syntax error in plugin '{os.path.basename(plugin_info.zip_path)}':\n\n{e}",
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
            if "importlib" in modules_to_check:
                title = "CRITICAL SECURITY ALERT"
                msg = (
                    f"The plugin <b>'{os.path.basename(plugin_info.zip_path)}'</b> attempts to import the "
                    f"dangerous module <b>importlib</b>, which can be used to "
                    "bypass security restrictions. For your safety,"
                    " this plugin will not be loaded."
                )
                QMessageBox.critical(self.parent_widget, title, msg)
                run_plugin = False
                self.config_manager.set_plugin_enabled(os.path.basename(plugin_info.zip_path), False)
            elif "src" in modules_to_check:
                title = "CRITICAL SECURITY ALERT"
                msg = (
                    f"The plugin <b>'{os.path.basename(plugin_info.zip_path)}'</b> attempts to import the "
                    f"dangerous module <b>src</b>, which can be used to "
                    "bypass security restrictions. For your safety,"
                    " this plugin will not be loaded."
                )
                QMessageBox.critical(self.parent_widget, title, msg)
                run_plugin = False
                self.config_manager.set_plugin_enabled(os.path.basename(plugin_info.zip_path), False)
            
            if run_plugin and (funcs_to_check or modules_to_check):
                # Sử dụng cùng logic authorization với chữ ký số
                if self._check_plugin_authorization(plugin_info.zip_path, funcs_to_check, modules_to_check):
                    self.SAFE_MODULES.update(modules_to_check)
                    self.FUNCTIONS_REQUIRING_PERMISSION.difference_update(funcs_to_check)
                    run_plugin = True
                else:
                    run_plugin = self._request_plugin_authorization(
                        os.path.basename(plugin_info.zip_path),
                        plugin_info.zip_path,
                        funcs_to_check,
                        modules_to_check
                    )

            if not run_plugin:
                QMessageBox.warning(
                    self.parent_widget,
                    "Plugin Load Canceled",
                    f"Loading of '{os.path.basename(plugin_info.zip_path)}' was canceled by the user.",
                )
                self.config_manager.set_plugin_enabled(os.path.basename(plugin_info.zip_path), False)
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
                    self._trigger_security_lockdown(plugin_info.manifest["name"], "__import__")
                return _real_import(name, globals, locals, fromlist, level)

            lexer_globals = {
                "__builtins__": __import__("builtins").__dict__.copy(),
            }

            for func_name in self.FUNCTIONS_REQUIRING_PERMISSION:
                if func_name not in funcs_to_check:
                    hook = self._create_hook(os.path.basename(plugin_info.zip_path), func_name)
                    lexer_globals["__builtins__"][func_name] = hook

            lexer_globals["__builtins__"]["__import__"] = _custom_import
            lexer_globals["lumos"] = LumosAPI({"BaseLexer": BaseLexer})
            exec(plugin_content, lexer_globals)
            sys.path.pop(0)

            plugin_info.lexer_class = lexer_globals.get(plugin_info.manifest["lexerClass"])
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