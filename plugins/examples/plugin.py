import os
import re

# The following variables are injected into the execution environment by the PluginManager:
# - plugin_manager
# - config_manager
# - parent_widget
# - get_project_dir
# - read_project_file
# - write_project_file
# - show_message
# - show_warning


def compile_lumos_script():
    try:
        active_tab = parent_widget.tabs.currentWidget()  # type: ignore

        if not hasattr(active_tab, "filepath") or not active_tab.filepath:
            show_warning("Compiler Error", "Please open and save a file first.")  # type: ignore
            return

        filepath = active_tab.filepath
        if not filepath.endswith((".lumos", ".lms")):
            show_warning("Compiler Error", "This is not an LumosScript file.")  # type: ignore
            return

        project_dir = get_project_dir()  # type: ignore
        if not project_dir:
            show_warning("Compiler Error", "Please open a folder to use the compiler.")  # type: ignore
            return

        relative_path = os.path.relpath(filepath, project_dir)

        lumos_code = read_project_file(relative_path)  # type: ignore

        js_code = re.sub(
            r'\bset\b(?![^"]*")(?=(?:[^"]*"[^"]*")*[^"]*$)', "let", lumos_code
        )
        js_code = re.sub(
            r'\bfunc\b(?![^"]*")(?=(?:[^"]*"[^"]*")*[^"]*$)', "function", js_code
        )
        js_code = re.sub(
            r'\bprint\((?![^"]*")(?=(?:[^"]*"[^"]*")*[^"]*$)', "console.log(", js_code
        )

        js_code = f"// Compiled from {os.path.basename(filepath)}\n\n{js_code}"

        output_filename = os.path.splitext(relative_path)[0] + ".js"
        write_project_file(output_filename, js_code)  # type: ignore

        show_message("LumosScript Compiler", f"Successfully compiled to {output_filename}!")  # type: ignore

    except Exception as e:
        show_warning("Compiler Error", f"An unexpected error occurred: {str(e)}")  # type: ignore


plugin_manager.add_menu_action("Tools", "Compile LumosScript", compile_lumos_script, shortcut="Ctrl+Alt+A")  # type: ignore
