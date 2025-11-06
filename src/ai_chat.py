import os
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QApplication,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QTextBrowser,
    QFrame,
    QMessageBox,
)
from PyQt5.QtCore import pyqtSignal, Qt, QThread, pyqtSlot, QSize
from PyQt5.QtGui import QIcon
import markdown
import google.genai as genai
from google.genai import types

MARKDOWN_CSS = """
    body { background-color: transparent; color: #d4d4d4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; font-size: 14px; }
    a { color: #58a6ff; text-decoration: none; }
    a:hover { text-decoration: underline; }
    h1, h2, h3, h4 { color: #e0e0e0; border-bottom: 1px solid #444; padding-bottom: 5px; margin-top: 15px; }
    h1 { font-size: 1.8em; } h2 { font-size: 1.5em; } h3 { font-size: 1.2em; }
    pre { background: #1e1e1e; padding: 12px; border-radius: 5px; border: 1px solid #444; overflow-x: auto; white-space: pre-wrap; word-break: break-all; }
    code { font-family: Consolas, 'Courier New', monospace; color: #9cdcfe; background-color: #1e1e1e; border-radius: 3px; padding: 2px 4px; }
    pre code { padding: 0; background-color: transparent; border: none; }
    table { border-collapse: collapse; width: 100%; background: #1e1e1e; margin: 1em 0; }
    th, td { border: 1px solid #404040; padding: 8px; text-align: left; }
    th { background-color: #252526; color: #0098ff; font-weight: bold; }
    blockquote { border-left: 4px solid #555; padding-left: 1em; color: #a0a0a0; margin: 1em 0; font-style: italic; }
    ul, ol { padding-left: 20px; } hr { border: 1px solid #444; margin: 1em 0; }
"""


class GeminiWorker(QThread):
    chunk_received = pyqtSignal(str)
    finished_streaming = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, client, contents, model, config):
        super().__init__()
        self.client = client
        self.contents = contents
        self.model = model
        self.config = config

    def run(self):
        try:
            full_response_text = ""
            stream = self.client.models.generate_content_stream(
                model=self.model,
                contents=self.contents,
                config=self.config,
            )
            for chunk in stream:
                if hasattr(chunk, "text"):
                    if chunk.text != None:
                        full_response_text += chunk.text
                        self.chunk_received.emit(full_response_text)
            self.finished_streaming.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


class AIMessageWidget(QWidget):
    insert_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.raw_text = ""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet(
            "background-color: #2d2d2d; border: 1px solid #3a3a3a; border-radius: 8px; padding: 10px; color: #d4d4d4;"
        )
        self.content_browser.setMinimumSize(QSize(400, 300))
        self.content_browser.setMaximumSize(QSize(400, 300))

        self.content_browser.document().setDefaultStyleSheet(MARKDOWN_CSS)
        main_layout.addWidget(self.content_browser)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.addStretch()

        copy_button = QPushButton(" Copy")
        copy_button.setIcon(QIcon("icons:/copy.ico"))

        button_style = "QPushButton { background-color: #3e3e3e; border: none; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; } QPushButton:hover { background-color: #4a4a4a; } QPushButton:pressed { background-color: #555; }"
        copy_button.setStyleSheet(button_style)
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)
        main_layout.addWidget(button_container)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.raw_text)

    def update_content(self, full_text):
        self.raw_text = full_text
        html_content = markdown.markdown(
            self.raw_text, extensions=["fenced_code", "codehilite", "tables"]
        )
        self.content_browser.setHtml(html_content)


class UserMessageWidget(QFrame):
    def __init__(self, text, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: #004d99; border-radius: 8px; color: #e0e0e0;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        message_label = QLabel(f"{text.replace('<', '&lt;').replace('>', '&gt;')}")
        message_label.setWordWrap(True)
        message_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        message_label.setStyleSheet(
            "background: transparent; border: none; padding: 0;"
        )
        layout.addWidget(message_label)


class AIChat(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_modified = None
        self.parent = parent
        self.contents = []

        self.model = None
        self.client = None
        self.current_ai_message_widget = None
        self.worker = None
        self.conversation_history = []
        self.current_file_path = None
        self.current_file_content = None
        self.setup_ui()
        self.setup_ai()

    def setup_ui(self):
        self.setStyleSheet("background-color: #252526;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.addStretch()
        self.clear_button = QPushButton("Clear Chat")
        self.clear_button.setStyleSheet(
            """
            QPushButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
        """
        )
        self.clear_button.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.clear_button)
        main_layout.addWidget(header_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea { border: none; background-color: #252526; }
            QScrollBar:vertical { background: #252526; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #4a4a4a; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """
        )
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(15)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area)
        context_container = QWidget()
        context_layout = QVBoxLayout(context_container)
        context_layout.setContentsMargins(1, 1, 1, 8)

        context_header = QWidget()
        context_header_layout = QHBoxLayout(context_header)
        context_header_layout.setContentsMargins(1, 1, 1, 5)

        context_label = QLabel("Context Files:")
        context_label.setStyleSheet("color: #d4d4d4;")
        context_header_layout.addWidget(context_label)

        self.add_context_button = QPushButton("Add Files")
        self.add_context_button.setStyleSheet(
            """
            QPushButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
        """
        )
        self.add_context_button.clicked.connect(self.add_context_files)
        context_header_layout.addWidget(self.add_context_button)

        self.clear_context_button = QPushButton("Clear Files")
        self.clear_context_button.setStyleSheet(
            """
            QPushButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
        """
        )
        self.clear_context_button.clicked.connect(self.clear_context_files)
        context_header_layout.addWidget(self.clear_context_button)
        context_header_layout.addStretch()
        context_layout.addWidget(context_header)

        self.context_files_list = QTextBrowser()

        self.context_files_list = QLabel("")
        self.context_files_list.setStyleSheet(
            """
            QLabel {
                color: #007acc;
                padding: 0 5px;
            }
        """
        )
        context_layout.addWidget(self.context_files_list)
        main_layout.addWidget(context_container)
        input_container = QWidget()
        input_container.setMaximumHeight(100)
        input_container.setMinimumHeight(48)
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 2, 0, 0)
        input_layout.setSpacing(4)
        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Ask AI to generate or modify code... (Enter for a new line, press the Send button to send)"
        )
        self.input_text.setStyleSheet(
            """
            QTextEdit { 
                color: #d4d4d4; 
                background-color: #1e1e1e; 
                border: 1px solid #3a3a3a; 
                padding: 4px 6px; 
                border-radius: 4px; 
                min-height: 20px;
                max-height: 100px; 
            }
            QTextEdit:focus { border: 1px solid #007acc; }
        """
        )
        self.input_text.setMinimumHeight(40)
        self.input_text.setMaximumHeight(100)
        input_layout.addWidget(self.input_text)

        self.send_button = QPushButton("")
        self.send_button.setIcon(QIcon("icons:/send.ico"))
        self.send_button.setFixedSize(28, 28)
        self.send_button.setIconSize(QSize(16, 16))
        self.send_button.setStyleSheet(
            """
            QPushButton { background-color: #007acc; border-radius: 4px; color: white; }
            QPushButton:hover { background-color: #008ae6; }
            QPushButton:pressed { background-color: #006bb3; }
            QPushButton:disabled { background-color: #555; }
        """
        )
        input_layout.addWidget(self.send_button)
        main_layout.addWidget(input_container)

        self.send_button.clicked.connect(self.send_message)

    def clear_chat(self):
        self.conversation_history = []
        self.contents = []
        while self.chat_layout.count():
            item = self.chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                layout_to_clear = item.layout()
                while layout_to_clear.count():
                    sub_item = layout_to_clear.takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().deleteLater()

    def add_user_message_widget(self, text):
        user_widget = UserMessageWidget(text)
        hbox = QHBoxLayout()
        hbox.addStretch()
        hbox.addWidget(user_widget, alignment=Qt.AlignRight, stretch=0)
        self.chat_layout.addLayout(hbox)
        self.scroll_to_bottom()

    def create_and_add_ai_message_widget(self):
        self.current_ai_message_widget = AIMessageWidget()
        self.current_ai_message_widget.insert_requested.connect(
            self.response_received.emit
        )
        hbox = QHBoxLayout()
        hbox.addWidget(
            self.current_ai_message_widget, alignment=Qt.AlignLeft, stretch=0
        )
        hbox.addStretch()
        self.chat_layout.addLayout(hbox)
        self.scroll_to_bottom()

    @pyqtSlot(str)
    def update_ai_message(self, full_text_so_far):
        if self.current_ai_message_widget:
            self.current_ai_message_widget.update_content(full_text_so_far)
            self.scroll_to_bottom()

    @pyqtSlot()
    def finalize_ai_message(self):
        if self.current_ai_message_widget:
            final_response_text = self.current_ai_message_widget.raw_text
            if final_response_text:
                user_message = (
                    self.conversation_history[-1] if self.conversation_history else None
                )
                if user_message and user_message.role == "user":
                    model_part = types.Part(text=final_response_text)
                    model_content = types.Content(role="model", parts=[model_part])
                    self.conversation_history.append(model_content)
        self.current_ai_message_widget = None
        self.send_button.setEnabled(True)
        self.input_text.setFocus()
        if self.worker:
            self.worker.quit()
            self.worker.wait()
            self.worker = None

    @pyqtSlot(str)
    def handle_ai_error(self, error_message):
        if self.current_ai_message_widget:
            for i in reversed(range(self.chat_layout.count())):
                item = self.chat_layout.itemAt(i)
                if item and item.layout() is not None:
                    layout = item.layout()
                    if (
                        layout.count() > 0
                        and layout.itemAt(0).widget() == self.current_ai_message_widget
                    ):
                        while layout.count():
                            item = layout.takeAt(0)
                            widget = item.widget()
                            if widget:
                                widget.deleteLater()
                        self.chat_layout.removeItem(item)
                        break

        msg_box = QMessageBox(None)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("AI Error")
        msg_box.setText(f"An error occurred:\n{error_message}")
        msg_box.setStyleSheet("")
        msg_box.setWindowIcon(QIcon("icons:/lumos-icon.ico"))
        msg_box.exec_()

        if self.conversation_history and self.conversation_history[-1].role == "user":
            self.conversation_history.pop()

        self.finalize_ai_message()

    def setup_ai(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            msg_box = QMessageBox(None)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Setup Error")
            msg_box.setText(
                "Environment variable GEMINI_API_KEY not found.\nPlease set the key to use the AI chat feature."
            )
            msg_box.setStyleSheet("")
            msg_box.setWindowIcon(QIcon("icons:/lumos-icon.ico"))
            msg_box.exec_()
            self.send_button.setEnabled(False)
            return

        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            msg_box = QMessageBox(None)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Connection Error")
            msg_box.setText(f"Failed to initialize the AI client:\n{e}")
            msg_box.setStyleSheet("")
            msg_box.setWindowIcon(QIcon("icons:/lumos-icon.ico"))
            msg_box.exec_()
            self.send_button.setEnabled(False)

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def add_context_files(self):
        from PyQt5.QtWidgets import QFileDialog
        import os

        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Context Files",
            "",
            "Text Files (*.txt *.py *.js *.html *.css *.json *.md);;All Files (*.*)",
        )
        if files:
            current_files = self.get_context_files()
            new_files = current_files + files
            display_names = [os.path.basename(f) for f in new_files]
            self.context_files_list.setText(", ".join(display_names))
            self.context_files_list.setProperty("fullPaths", new_files)

    def clear_context_files(self):
        self.context_files_list.setText("")
        self.context_files_list.setProperty("fullPaths", [])

    def get_context_files(self):
        return self.context_files_list.property("fullPaths") or []

    def send_message(self):
        user_message = self.input_text.toPlainText().strip()
        if (
            not user_message
            or not self.client
            or (self.worker and self.worker.isRunning())
        ):
            return
        context_content = []

        context_files = self.get_context_files()
        if context_files:
            for file_path in context_files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                        context_content.append(
                            f"Content of {file_path}:\n```\n{content}\n```"
                        )
                except Exception as e:
                    context_content.append(f"Error reading {file_path}: {str(e)}")

        self.add_user_message_widget(user_message)
        self.input_text.clear()
        self.send_button.setEnabled(False)
        self.create_and_add_ai_message_widget()

        system_instruction = (
            "You are LumosAI, the built-in intelligent assistant of the Lumos Code Editor."
            + "You provide professional software development guidance, coding help, and technical explanations to improve the user's workflow and productivity.\n"
            + "Context: handle design, debugging, optimization, explanation, and code review requests.\n"
            + "Language: reply in the user's language; keep tone concise, professional, and clear.\n"
            + 'Action: return runnable code when asked; summarize before explaining; add examples/tests when relevant; if user requests "code only", output only code.\n'
            + "Restrictions: no malicious or illegal code; keep answers concise; if information is missing or uncertain, search for accurate details; always follow safety rules."
            + (
                "\nThese are the context files the user has provided to you:\n"
                + "\n\n".join(context_content)
            )
            if len(context_content) > 0
            else ""
        )

        for message in self.conversation_history:
            self.contents.append(message)

        user_part = types.Part(text=user_message)
        current_user_content = types.Content(role="user", parts=[user_part])
        self.contents.append(current_user_content)

        model = "gemini-2.5-pro"

        tools = [types.Tool(google_search=types.GoogleSearch())]

        generate_content_config = types.GenerateContentConfig(
            system_instruction=types.Part.from_text(text=system_instruction),
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,
            ),
            tools=tools,
        )

        self.worker = GeminiWorker(
            self.client, self.contents, model, generate_content_config
        )
        self.worker.chunk_received.connect(self.update_ai_message)
        self.worker.finished_streaming.connect(self.finalize_ai_message)
        self.worker.error_occurred.connect(self.handle_ai_error)
        self.worker.start()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()
