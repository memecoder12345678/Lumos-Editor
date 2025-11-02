import os

# Các biến sau đây được PluginManager tiêm vào môi trường thực thi:
# - plugin_manager
# - config_manager
# - parent_widget
# - get_project_dir
# - read_project_file
# - write_project_file
# - show_message
# - show_warning

def compile_aqua_script():
    """
    Một hàm "biên dịch" giả lập.
    Nó đọc file .aqua hiện tại, thay thế một vài từ khóa, và lưu thành file .js.
    """
    try:
        # Lấy tab đang hoạt động từ cửa sổ chính
        active_tab = parent_widget.tabs.currentWidget() # type: ignore

        # Kiểm tra xem có phải là một tab editor có file đang mở không
        if not hasattr(active_tab, 'filepath') or not active_tab.filepath:
            show_warning("Compiler Error", "Please open and save a file first.") # type: ignore
            return

        filepath = active_tab.filepath
        if not filepath.endswith(('.aqua', '.aqs')):
            show_warning("Compiler Error", "This is not an AquaScript file.") # type: ignore
            return

        project_dir = get_project_dir() # type: ignore
        if not project_dir:
            show_warning("Compiler Error", "Please open a folder to use the compiler.") # type: ignore
            return
            
        # Lấy đường dẫn tương đối để dùng với API
        relative_path = os.path.relpath(filepath, project_dir)
        
        # Đọc nội dung file
        aqua_code = read_project_file(relative_path) # type: ignore

        # "Biên dịch" đơn giản
        js_code = aqua_code.replace("set", "let")
        js_code = js_code.replace("func", "function")
        js_code = js_code.replace("string(", "String(")
        js_code = js_code.replace("number(", "Number(")
        js_code = js_code.replace("print(", "console.log(")

        js_code = f"// Compiled from {os.path.basename(filepath)}\n\n{js_code}"

        # Tạo file đầu ra
        output_filename = os.path.splitext(relative_path)[0] + ".js"
        write_project_file(output_filename, js_code) # type: ignore

        show_message("AquaScript Compiler", f"Successfully compiled to {output_filename}!") # type: ignore

    except Exception as e:
        show_warning("Compiler Error", f"An unexpected error occurred: {str(e)}") # type: ignore


# Đăng ký hành động vào menu "Tools"
# Shortcut là Ctrl+Alt+A (một ví dụ)
plugin_manager.add_menu_action("Tools", "Compile AquaScript", compile_aqua_script, shortcut="Ctrl+Alt+A") # type: ignore