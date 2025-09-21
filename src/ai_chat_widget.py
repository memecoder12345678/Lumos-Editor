import os
import sys
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLineEdit,
                             QPushButton, QApplication, QHBoxLayout,
                             QLabel, QScrollArea, QTextBrowser, QFrame, QMessageBox)
from PyQt5.QtCore import pyqtSignal, Qt, QThread, pyqtSlot, QSize
from PyQt5.QtGui import QIcon
import markdown

try:
    import google.genai as genai
    from google.genai import types
except ImportError:
    genai = None

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
        self.content_browser.setStyleSheet("background-color: #2d2d2d; border: 1px solid #3a3a3a; border-radius: 8px; padding: 10px; color: #d4d4d4;")
        self.content_browser.document().setDefaultStyleSheet(MARKDOWN_CSS)
        main_layout.addWidget(self.content_browser)
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.addStretch()

        copy_button = QPushButton(" Copy")
        copy_button.setIcon(QIcon("icons:/copy.ico"))
        insert_button = QPushButton(" Insert")
        insert_button.setIcon(QIcon("icons:/add.ico"))

        button_style = "QPushButton { background-color: #3e3e3e; border: none; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; } QPushButton:hover { background-color: #4a4a4a; } QPushButton:pressed { background-color: #555; }"
        copy_button.setStyleSheet(button_style)
        insert_button.setStyleSheet(button_style)
        copy_button.clicked.connect(self.copy_to_clipboard)
        insert_button.clicked.connect(self.request_insert)
        button_layout.addWidget(copy_button)
        button_layout.addWidget(insert_button)
        main_layout.addWidget(button_container)

    def copy_to_clipboard(self): QApplication.clipboard().setText(self.raw_text)
    def request_insert(self): self.insert_requested.emit(self.raw_text)
    def update_content(self, full_text):
        self.raw_text = full_text
        html_content = markdown.markdown(self.raw_text, extensions=['fenced_code', 'codehilite', 'tables'])
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
        message_label.setStyleSheet("background: transparent; border: none; padding: 0;")
        layout.addWidget(message_label)


class AIChatWidget(QWidget):
    response_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.model = None
        self.client = None
        self.current_ai_message_widget = None
        self.worker = None
        self.conversation_history = []
        self.setup_ui()
        self.setup_ai()

    def setup_ui(self):
        self.setStyleSheet("background-color: #252526;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(0, 0, 0, 5)
        header_layout.addStretch()
        self.clear_button = QPushButton("Clear Chat")
        self.clear_button.setStyleSheet("""
            QPushButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QPushButton:hover { background-color: #555; } QPushButton:pressed { background-color: #666; }
        """)
        self.clear_button.clicked.connect(self.clear_chat)
        header_layout.addWidget(self.clear_button)
        main_layout.addWidget(header_container)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background-color: #252526; }
            QScrollBar:vertical { background: #252526; width: 10px; margin: 0; }
            QScrollBar::handle:vertical { background: #4a4a4a; min-height: 20px; border-radius: 5px; }
            QScrollBar::handle:vertical:hover { background: #555; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setSpacing(15)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.chat_container)
        main_layout.addWidget(self.scroll_area)

        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 5, 0, 0)
        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("Ask AI to generate or modify code...")
        self.input_text.setStyleSheet("""
            QLineEdit { color: #d4d4d4; background-color: #1e1e1e; border: 1px solid #3a3a3a; padding: 8px; border-radius: 4px; min-height: 20px; }
            QLineEdit:focus { border: 1px solid #007acc; }
        """)
        input_layout.addWidget(self.input_text)

        self.send_button = QPushButton("")
        self.send_button.setIcon(QIcon("icons:/send.ico"))
        self.send_button.setFixedSize(38, 38)
        self.send_button.setIconSize(QSize(20, 20))
        self.send_button.setStyleSheet("""
            QPushButton { background-color: #007acc; border-radius: 4px; color: white; }
            QPushButton:hover { background-color: #008ae6; }
            QPushButton:pressed { background-color: #006bb3; }
            QPushButton:disabled { background-color: #555; }
        """)
        input_layout.addWidget(self.send_button)
        main_layout.addWidget(input_container)

        self.send_button.clicked.connect(self.send_message)
        self.input_text.returnPressed.connect(self.send_message)

    def clear_chat(self):
        self.conversation_history = []
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
        self.current_ai_message_widget.insert_requested.connect(self.response_received.emit)
        hbox = QHBoxLayout()
        hbox.addWidget(self.current_ai_message_widget, alignment=Qt.AlignLeft, stretch=0)
        hbox.addStretch()
        self.chat_layout.addLayout(hbox)
        self.scroll_to_bottom()

    def send_message(self):
        user_message = self.input_text.text().strip()
        if not user_message or not self.client or (self.worker and self.worker.isRunning()):
            return

        self.add_user_message_widget(user_message)
        self.input_text.clear()
        self.send_button.setEnabled(False)
        self.create_and_add_ai_message_widget()

        user_part = types.Part.from_text(text=user_message)
        self.conversation_history.append(types.Content(role="user", parts=[user_part]))
        
        model = "gemini-2.5-pro"
        
        tools = [
            types.Tool(google_search=types.GoogleSearch())
        ]
        
        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_budget=-1,
            ),
            tools=tools,
        )

        self.worker = GeminiWorker(self.client, self.conversation_history, model, generate_content_config)
        self.worker.chunk_received.connect(self.update_ai_message)
        self.worker.finished_streaming.connect(self.finalize_ai_message)
        self.worker.error_occurred.connect(self.handle_ai_error)
        self.worker.start()

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
                model_part = types.Part.from_text(text=final_response_text)
                self.conversation_history.append(types.Content(role="model", parts=[model_part]))
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
                    if layout.count() > 0 and layout.itemAt(0).widget() == self.current_ai_message_widget:
                        self.clear_layout(layout)
                        self.chat_layout.removeItem(item)
                        break
        
        QMessageBox.warning(self, "AI Error", f"An error occurred:\n{error_message}")
        
        if self.conversation_history and self.conversation_history[-1].role == "user":
            self.conversation_history.pop()

        self.finalize_ai_message()

    def setup_ai(self):
        if genai is None:
            QMessageBox.critical(self, "Setup Error", "The 'google-genai' library is not installed.\nPlease run 'pip install google-genai'.")
            self.send_button.setEnabled(False)
            return

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            QMessageBox.critical(self, "Setup Error", "Environment variable GEMINI_API_KEY not found.\nPlease set the key to use the application.")
            self.send_button.setEnabled(False)
            return

        try:
            self.client = genai.Client(api_key=api_key)
        except Exception as e:
            QMessageBox.critical(self, "Connection Error", f"Failed to initialize the AI client:\n{e}")
            self.send_button.setEnabled(False)

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()
