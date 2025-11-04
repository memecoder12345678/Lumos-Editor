import ast
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *


class CodeAnalyzerVisitor(ast.NodeVisitor):
    def __init__(self):
        self.called_functions = set()
        self.imported_modules = set()

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            self.called_functions.add(node.func.id)
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.imported_modules.add(alias.name.split(".")[0])
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module:
            self.imported_modules.add(node.module.split(".")[0])
        self.generic_visit(node)


class PermissionsDialog(QDialog):
    def __init__(self, plugin_name, risky_funcs, risky_modules, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Security Check")
        self.setMinimumWidth(500)

        self.layout = QVBoxLayout(self)

        title_label = QLabel(f"<b>Security Warning for Plugin: '{plugin_name}'</b>")
        self.layout.addWidget(title_label)

        if risky_funcs:
            func_label = QLabel(
                "This plugin wants to use the following built-in functions:"
            )
            self.layout.addWidget(func_label)
            func_list = QTextEdit()
            func_list.setReadOnly(True)
            func_list.setText("\n".join(sorted(list(risky_funcs))))
            func_list.setFixedHeight(80)
            self.layout.addWidget(func_list)

        if risky_modules:
            mod_label = QLabel(
                "This plugin wants to import the following external modules:"
            )
            self.layout.addWidget(mod_label)
            mod_list = QTextEdit()
            mod_list.setReadOnly(True)
            mod_list.setText("\n".join(sorted(list(risky_modules))))
            mod_list.setFixedHeight(80)
            self.layout.addWidget(mod_list)

        warning_label = QLabel(
            "<b>Do you trust this plugin to grant these permissions?</b>"
        )
        self.layout.addWidget(warning_label)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.button(QDialogButtonBox.Ok).setText("Trust and Run")
        button_box.button(QDialogButtonBox.Cancel).setText("Deny")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.layout.addWidget(button_box)
