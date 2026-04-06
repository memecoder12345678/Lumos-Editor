import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import google.genai as genai
from google.genai import types
from PyQt5.QtCore import QSize, Qt, QThread, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from . import md_renderer

MARKDOWN_CSS = """
body {
	background: transparent;
	color: #d4d4d4;
	padding: 20px;
	font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
	line-height: 1.6;
}
img {
	max-width: 60%;
	height: auto;
}
table {
	border-collapse: collapse;
	width: 60%;
	margin: 15px 0;
	background: #1e1e1e;
}
th, td {
	border: 1px solid #404040;
	padding: 12px;
	text-align: left;
}
th {
	background-color: #252526;
	color: #0098ff;
	font-weight: bold;
}
td {
	color: #d4d4d4;
}
tr:nth-child(odd) {
	background-color: #252526;
}
tr:hover {
	background-color: #2d2d2d;
}
pre {
	background: #1e1e1e;
	padding: 10px;
	border-radius: 4px;
	overflow-x: auto;
	margin: 16px 0;
	width: 100%;
	word-break: break-word;
}
inline_code {
	width: 100%;
	font-family: Consolas, monospace;
	color: #9cdcfe;
	font-size: 14px;
}
block_code {
	width: 100%;
	font-family: Consolas, monospace;
	color: #9cdcfe;
	font-size: 14px;
	display: block;
	white-space: pre-wrap;
	word-break: break-word;
}
table.code-block {
	width: 100%;
	margin: 16px 0;
	background: #1e1e1e;
	border-radius: 4px;
}
table.code-block td {
	white-space: pre;
}
table.code-block pre {
	margin: 0;
	padding: 0;
	background: transparent;
	white-space: pre;
}
table.code-block code {
	font-family: Consolas, monospace;
	color: #9cdcfe;
	font-size: 14px;
	white-space: pre;
	display: block;
}
.markdown-quote {
	border-left: 4px solid #d0d7de;
	padding: 0 1em;
	color: #656d76;
	margin: 1em 0;
}
.task-list-item {
	list-style-type: none;
}
.task-list-item input[type="checkbox"] {
	margin: 0 0.5em 0.25em -1.4em;
	vertical-align: middle;
}
"""


def dt_name():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def get_unique_path(path):
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    i = 1

    while True:
        new_path = f"{base} ({i}){ext}"
        if not os.path.exists(new_path):
            return new_path
        i += 1


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
                if hasattr(chunk, "text") and chunk.text is not None:
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
        self._min_w = 260
        self._max_w = 700

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.content_browser = QTextBrowser()
        self.content_browser.setOpenExternalLinks(True)
        self.content_browser.setStyleSheet(
            "background-color: #2d2d2d; border: 1px solid #3a3a3a; border-radius: 8px; padding: 10px; color: #d4d4d4;"
        )
        self.content_browser.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.content_browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content_browser.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.content_browser.document().setDefaultStyleSheet(MARKDOWN_CSS)
        main_layout.addWidget(self.content_browser)

        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 5, 0, 0)
        button_layout.addStretch()

        copy_button = QPushButton(" Copy")
        copy_button.setIcon(QIcon("resources:/copy-icon.ico"))
        copy_button.setStyleSheet(
            "QPushButton { background-color: #3e3e3e; border: none; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; } QPushButton:hover { background-color: #4a4a4a; } QPushButton:pressed { background-color: #555; }"
        )
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)

        main_layout.addWidget(button_container)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def copy_to_clipboard(self):
        QApplication.clipboard().setText(self.raw_text)

    def set_max_width(self, max_w):
        self._max_w = max(240, int(max_w))
        self._reflow()

    def _reflow(self):
        doc = self.content_browser.document()
        doc.setDocumentMargin(0)
        doc.adjustSize()

        natural_w = int(doc.idealWidth()) + 28
        w = max(self._min_w, min(self._max_w, natural_w))

        self.content_browser.setFixedWidth(w)
        doc.setTextWidth(w - 28)
        doc.adjustSize()

        h = int(doc.size().height()) + 26
        h = max(60, min(h, 600))
        self.content_browser.setFixedHeight(h)

        self.adjustSize()
        self.updateGeometry()

    def update_content(self, full_text):
        self.raw_text = full_text
        html_content = md_renderer.markdown(full_text)
        self.content_browser.setHtml(html_content)
        QTimer.singleShot(0, self._reflow)


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


class ChatInput(QTextEdit):
    send_requested = pyqtSignal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ControlModifier:
                self.send_requested.emit()
                return
        super().keyPressEvent(event)


class AIChat(QWidget):
    response_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_modified = None
        self.parent = parent
        self.contents = []
        self.tabname = "AI Chat"
        self.model = None
        self.client = None
        self.current_ai_message_widget = None
        self.worker = None
        self.conversation_history = []
        self.current_file_path = None
        self.current_file_content = None

        self.data_dir = Path.home() / ".lumos_editor"
        self.sessions_dir = self.data_dir / "sessions"
        self.config_path = self.data_dir / "config.json"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

        self.current_session_id = None
        self.current_session_name = None
        self.session_button = None

        self.setup_ui()
        self.setup_ai()
        self.refresh_session_menu()

    def setup_ui(self):
        self.setStyleSheet("background-color: #252526;")
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        header_container = QWidget()
        header_layout = QHBoxLayout(header_container)
        header_layout.setContentsMargins(5, 5, 5, 5)
        header_layout.addStretch()

        self.session_button = QToolButton()
        self.session_button.setText("Sessions")
        self.session_button.setPopupMode(QToolButton.InstantPopup)
        self.session_button.setStyleSheet(
            """
            QToolButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QToolButton:hover { background-color: #555; }
            QToolButton:pressed { background-color: #666; }
            """
        )
        header_layout.addWidget(self.session_button)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search chats...")
        self.search_box.setStyleSheet(
            """
        QLineEdit {
            background-color: #1e1e1e;
            border: 1px solid #3a3a3a;
            padding: 4px 8px;
            border-radius: 4px;
            color: #d4d4d4;
        }
        QLineEdit:focus {
            border: 1px solid #007acc;
        }
        """
        )

        self.search_box.textChanged.connect(self.search_sessions)

        header_layout.insertWidget(0, self.search_box)

        self.new_button = QPushButton("New Chat")
        self.new_button.setStyleSheet(
            """
            QPushButton { background-color: #4a4a4a; border: 1px solid #555; padding: 5px 10px; border-radius: 4px; color: #d4d4d4; }
            QPushButton:hover { background-color: #555; }
            QPushButton:pressed { background-color: #666; }
            """
        )
        self.new_button.clicked.connect(self.new_chat)
        header_layout.addWidget(self.new_button)
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

        self.input_text = ChatInput()
        self.input_text.setPlaceholderText(
            "Ask AI to generate or modify code... (Enter for a new line, press Ctrl+Enter to send)"
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
        self.input_text.send_requested.connect(self.send_message)
        input_layout.addWidget(self.input_text)

        self.send_button = QPushButton("")
        self.send_button.setIcon(QIcon("resources:/send-icon.ico"))
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

    def search_sessions(self, text):
        text = text.lower().strip()

        cfg = self._load_config()
        sessions = cfg.get("sessions", [])

        menu = QMenu(self)

        if not text:
            self.refresh_session_menu()
            return

        found = False

        for s in sessions:
            try:
                path = Path(s.get("path"))
                if not path.exists():
                    continue

                with open(path, "r", encoding="utf-8") as f:
                    payload = json.load(f)

                messages = payload.get("messages", [])

                hit = any(text in m.get("text", "").lower() for m in messages)

                if hit:
                    found = True
                    label = f'{s.get("name")} ({s.get("count", 0)} msgs)'
                    act = QAction(label, self)
                    sid = s.get("id")
                    act.triggered.connect(
                        lambda checked=False, session_id=sid: self.load_session(
                            session_id
                        )
                    )
                    menu.addAction(act)

            except Exception:
                continue

        if not found:
            empty = QAction("No results found", self)
            empty.setEnabled(False)
            menu.addAction(empty)

        self.session_button.setMenu(menu)

    def _ai_bubble_max_width(self):
        return max(260, self.scroll_area.viewport().width() - 80)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        max_w = self._ai_bubble_max_width()
        for i in range(self.chat_layout.count()):
            item = self.chat_layout.itemAt(i)
            if item and item.layout():
                layout = item.layout()
                if layout.count() > 0:
                    w = layout.itemAt(0).widget()
                    if isinstance(w, AIMessageWidget):
                        w.set_max_width(max_w)
        QTimer.singleShot(0, self.scroll_to_bottom)

    def new_chat(self, skip_save=False):
        if not skip_save:
            self.ask_session_name_and_save()

        self.conversation_history = []
        self.contents = []
        self.current_ai_message_widget = None

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

    def add_ai_message_widget_static(self, text):
        ai_widget = AIMessageWidget()
        ai_widget.set_max_width(self._ai_bubble_max_width())
        ai_widget.update_content(text)
        hbox = QHBoxLayout()
        hbox.addWidget(ai_widget, alignment=Qt.AlignLeft, stretch=0)
        hbox.addStretch()
        self.chat_layout.addLayout(hbox)

    def create_and_add_ai_message_widget(self):
        self.current_ai_message_widget = AIMessageWidget()
        self.current_ai_message_widget.set_max_width(self._ai_bubble_max_width())
        self.current_ai_message_widget.insert_requested.connect(
            self.response_received.emit
        )
        hbox = QHBoxLayout()
        hbox.addWidget(
            self.current_ai_message_widget, alignment=Qt.AlignLeft, stretch=0
        )
        hbox.addStretch()
        self.chat_layout.addLayout(hbox)
        QTimer.singleShot(0, self.scroll_to_bottom)

    @pyqtSlot(str)
    def update_ai_message(self, full_text_so_far):
        if self.current_ai_message_widget:
            self.current_ai_message_widget.update_content(full_text_so_far)
            QTimer.singleShot(0, self.scroll_to_bottom)

    @pyqtSlot()
    def finalize_ai_message(self):
        if self.current_ai_message_widget:
            final_response_text = self.current_ai_message_widget.raw_text
            if final_response_text:
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
        self.refresh_session_menu()

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
                            inner = layout.takeAt(0)
                            widget = inner.widget()
                            if widget:
                                widget.deleteLater()
                        self.chat_layout.removeItem(item)
                        break

        msg_box = QMessageBox(None)
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setWindowTitle("AI Error")
        msg_box.setText(f"An error occurred:\n{error_message}")
        msg_box.setWindowIcon(QIcon("resources:/lumos-icon.ico"))
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
            msg_box.setWindowIcon(QIcon("resources:/lumos-icon.ico"))
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
            msg_box.setWindowIcon(QIcon("resources:/lumos-icon.ico"))
            msg_box.exec_()
            self.send_button.setEnabled(False)

    def scroll_to_bottom(self):
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(
            self.scroll_area.verticalScrollBar().maximum()
        )

    def add_context_files(self):
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

    def _load_config(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {"sessions": []}
        return {"sessions": []}

    def _save_config(self, data):
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _session_file_path(self, session_id):
        return self.sessions_dir / f"{session_id}.json"

    def _serialize_conversation(self):
        msgs = []
        for m in self.conversation_history:
            role = getattr(m, "role", "")
            text = ""
            try:
                parts = getattr(m, "parts", [])
                if parts:
                    text = getattr(parts[0], "text", "") or ""
            except Exception:
                text = ""
            if role in ("user", "model") and text:
                msgs.append({"role": role, "text": text})

        if self.current_ai_message_widget and self.current_ai_message_widget.raw_text:
            if not msgs or msgs[-1]["role"] != "model":
                msgs.append(
                    {"role": "model", "text": self.current_ai_message_widget.raw_text}
                )

        return msgs

    def _save_current_session(self):
        msgs = self._serialize_conversation()
        if not msgs:
            return None

        session_id = self.current_session_id or uuid.uuid4().hex[:12]
        name = self.current_session_name or dt_name()

        payload = {
            "id": session_id,
            "name": get_unique_path(name),
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "messages": msgs,
        }

        path = self._session_file_path(session_id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        cfg = self._load_config()
        sessions = cfg.get("sessions", [])
        sessions = [s for s in sessions if s.get("id") != session_id]
        sessions.insert(
            0,
            {
                "id": session_id,
                "name": get_unique_path(name),
                "path": str(path),
                "saved_at": payload["saved_at"],
                "count": len(msgs),
            },
        )
        cfg["sessions"] = sessions[:50]
        cfg["last_session_id"] = session_id
        self._save_config(cfg)

        self.current_session_id = session_id
        self.current_session_name = name
        self.refresh_session_menu()
        return path

    def refresh_session_menu(self):
        menu = QMenu(self)
        cfg = self._load_config()
        sessions = cfg.get("sessions", [])

        if not sessions:
            empty_action = QAction("No saved sessions", self)
            empty_action.setEnabled(False)
            menu.addAction(empty_action)
        else:
            for s in sessions:
                label = f'{s.get("name", "Session")} ({s.get("count", 0)} msgs)'
                act = QAction(label, self)
                sid = s.get("id")
                act.triggered.connect(
                    lambda checked=False, session_id=sid: self.load_session(session_id)
                )
                menu.addAction(act)

        menu.addSeparator()

        open_action = QAction("Open JSON file...", self)
        open_action.triggered.connect(self.open_session_json)
        menu.addAction(open_action)

        self.session_button.setMenu(menu)

    def load_session(self, session_id):
        path = self._session_file_path(session_id)
        if not path.exists():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Warning)
            msg_box.setWindowTitle("Load Session")
            msg_box.setText("Session file not found.")
            msg_box.exec_()
            return

        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Load Session")
            msg_box.setText(f"Failed to load session:\n{e}")
            msg_box.exec_()
            return

        self.new_chat(skip_save=True)
        self.current_session_id = payload.get("id", session_id)
        self.current_session_name = payload.get("name", dt_name())

        for msg in payload.get("messages", []):
            role = msg.get("role")
            text = msg.get("text", "")
            if role == "user":
                self.add_user_message_widget(text)
                user_part = types.Part(text=text)
                self.conversation_history.append(
                    types.Content(role="user", parts=[user_part])
                )
            elif role == "model":
                self.add_ai_message_widget_static(text)
                model_part = types.Part(text=text)
                self.conversation_history.append(
                    types.Content(role="model", parts=[model_part])
                )

        self.refresh_session_menu()
        self.scroll_to_bottom()

    def open_session_json(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Chat Session",
            str(self.sessions_dir),
            "JSON Files (*.json)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception as e:
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setWindowTitle("Open Session")
            msg_box.setText(f"Failed to open session file:\n{e}")
            msg_box.exec_()
            return

        self.new_chat(skip_save=True)
        self.current_session_id = payload.get("id", uuid.uuid4().hex[:12])
        self.current_session_name = payload.get("name", dt_name())

        for msg in payload.get("messages", []):
            role = msg.get("role")
            text = msg.get("text", "")
            if role == "user":
                self.add_user_message_widget(text)
                user_part = types.Part(text=text)
                self.conversation_history.append(
                    types.Content(role="user", parts=[user_part])
                )
            elif role == "model":
                self.add_ai_message_widget_static(text)
                model_part = types.Part(text=text)
                self.conversation_history.append(
                    types.Content(role="model", parts=[model_part])
                )

        self.refresh_session_menu()
        self.scroll_to_bottom()

    def send_message(self):

        if self.current_session_id is None:
            self.current_session_name = None

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

        user_part = types.Part(text=user_message)
        current_user_content = types.Content(role="user", parts=[user_part])
        self.conversation_history.append(current_user_content)
        self.contents = list(self.conversation_history)

        context_str = "\n- ".join(context_content) if context_content else " None"
        system_instruction = f"""
==================== SYSTEM ====================
You are LumosAI, a senior-level embedded debugging and code repair agent operating inside a professional code editor environment.

PRIMARY OBJECTIVE
- Deliver the most correct, minimal, production-safe fix possible.
- Perform deep multi-phase root-cause analysis before touching any code.
- Self-verify every fix for correctness, regressions, and edge cases.
- Use web search when knowledge may be outdated, version-specific, or unverifiable from context alone.
- Ask the user targeted clarifying questions when critical information is absent or ambiguous.

NON-NEGOTIABLE PRIORITIES
1. Correctness - the fix must be provably right, not just plausible
2. Runnability - output must execute without modification
3. Safety      - no regressions, no side effects, no data loss
4. Clarity     - every decision must be explainable in one sentence
5. Minimalism  - smallest safe change that solves the root cause

ABSOLUTE CONSTRAINTS
- Never invent APIs, methods, file paths, library behavior, or version features.
- Never assume behavior not evidenced in context or verifiable sources.
- Never repeat information already provided in the conversation.
- Never output malicious, destructive, legally unsafe, or privacy-violating code.
- Never proceed on ambiguous specs - ask first.
- If exact correctness cannot be verified, declare it explicitly and explain why.

==================== DEVELOPER ====================

DEEP DEBUG PROTOCOL - Execute every phase in order. Skip none.

PHASE 1 * COMPREHENSION
- Fully understand the stated goal, constraints, language, framework, and runtime.
- Identify what "working correctly" means in concrete, testable terms.
- Flag any unstated assumptions immediately.

PHASE 2 * CONTEXT AUDIT
- Treat all provided context files, logs, stack traces, and snippets as the authoritative source of truth.
- Map the execution path from entry point to failure point.
- Identify all symbols, dependencies, and state involved in the failure.
- If context contradicts inference, always trust the context.

PHASE 3 * ERROR CLASSIFICATION
Classify the bug internally as exactly one of:
- Syntax        - malformed code the parser/compiler rejects
- Runtime       - valid code that fails during execution
- Logical       - code runs but produces wrong results
- Concurrency   - race conditions, deadlocks, ordering issues
- API Misuse    - incorrect usage of a library or external interface
- Configuration - wrong environment, config values, or build setup

Use this classification to select the correct fix strategy before proceeding.
A Syntax bug      -> parser-level fix.
A Logical bug     -> trace the invariant violation.
A Concurrency bug -> minimize shared mutable state, prefer locks or atomic ops.
An API Misuse bug -> verify against official docs or web search before patching.

PHASE 4 * ROOT CAUSE ANALYSIS
- Identify the single deepest root cause, not symptoms.
- Enumerate all plausible alternative causes ranked by likelihood.
- Eliminate alternatives with explicit reasoning.
- If multiple root causes coexist, address each independently.

PHASE 5 * ASSUMPTION LOCK
- Any assumption made during analysis MUST be stated explicitly in one line before the fix.
- Format: "Assumption: [statement]"
- If more than one critical assumption is required to proceed -> stop and ask the user instead.
- Never silently assume. Never guess and proceed without disclosure.

PHASE 6 * PATCH SAFETY MODE
Before writing any code, classify the fix risk level:

  LOW RISK    - change is isolated; affects only a local variable, single function, or private logic
                with no shared callers and no external contract changes.

  MEDIUM RISK - change touches a shared function, module, or interface used by multiple callers.
                Flag all known affected call sites.

  HIGH RISK   - change affects global state, core business logic, a public API contract,
                a database schema, or any external integration.

Enforcement rules by level:
- LOW    -> proceed normally.
- MEDIUM -> explicitly list all affected call sites before patching.
- HIGH   -> minimize surface area to the absolute minimum.
           Do not refactor. Do not restructure.
           Prefer guard clauses and narrow conditionals over any structural rewrite.
           State the risk level in the output so the user can review before applying.

PHASE 7 * DIFF DISCIPLINE
- Do not modify more lines than the root cause requires.
- If the patch exceeds 10 changed lines, internally justify why before proceeding.
  If justification is weak -> reduce scope further.
- Prefer surgical single-point edits over block rewrites.
- Never reformat, rename, or reorganize code outside the direct fix area.
- Do not touch whitespace, comments, or style in lines unrelated to the fix.

PHASE 8 * ANTI-OVERENGINEERING
Do not introduce any of the following unless the user has explicitly requested it:
- New abstractions (base classes, interfaces, generics, factories)
- New architectural layers (services, repositories, middleware)
- New external dependencies or packages
- New files or modules beyond what the fix strictly requires
- Design patterns applied speculatively

If the temptation to add any of the above arises, suppress it.
Fix the bug. Nothing more.

PHASE 9 * IMPACT ASSESSMENT
- Determine blast radius: what else could this fix break?
- Check: state mutations, async behavior, error boundaries, type contracts, API contracts, performance.
- If the fix touches shared logic, confirm all affected call sites were already identified in Phase 6.

PHASE 10 * SELF-VERIFICATION CHECKLIST
Before finalizing any output, confirm every item below internally:
  [ ] Syntax is valid for the target language and version
  [ ] Logic correctly addresses the root cause
  [ ] No new bugs introduced (regression check)
  [ ] Edge cases handled: null/undefined, empty input, boundary values, concurrent access
  [ ] Types and contracts are satisfied
  [ ] No unused imports, dead code, or debug artifacts remain
  [ ] Fix is idempotent or stateless where required
  [ ] Assumption Lock disclosures are present if any assumption was made
  [ ] Patch Safety level is correct and enforced
  [ ] Diff is minimal - no unrelated lines changed
  [ ] No new abstractions or dependencies snuck in
  [ ] Output will run as-is without user modification

If any item fails -> revise before outputting. Do not output a failing checklist.

PHASE 11 * VERIFICATION MODE
Choose the lightest verification level that provides meaningful confidence. Do not exceed it.

  Level 1 - Static reasoning     : trace the logic mentally and confirm correctness (default)
  Level 2 - Example input/output : show a concrete before/after or sample value
  Level 3 - Test snippet         : provide a minimal, self-contained test case
  Level 4 - Command / runtime    : provide an exact shell command or runtime assertion

Escalate to a higher level only when the lower level cannot adequately confirm correctness.
Never attach a Level 3 or 4 verification to a trivial or obvious fix.

==================== POLICIES ====================

REASONING POLICY
- All internal analysis happens silently across all phases.
- Never expose chain-of-thought, scratchpad, phase narration, or checklist states.
- Only surface: error classification, assumptions (if any), patch risk level (if MEDIUM/HIGH), diagnosis, fix rationale, and final output.

WEB SEARCH POLICY
Trigger a web search when any of the following conditions are met:
- The bug involves a specific library version, runtime version, or platform behavior not in context.
- The error message, API, or behavior requires external documentation to verify.
- The knowledge required may have changed after the training cutoff.
- The user references a tool, package, or framework version that cannot be verified internally.
- Error classification is API Misuse -> always verify against official docs.

After searching: cite the source inline with a short reference. Integrate findings directly into the fix.

CLARIFICATION POLICY
Ask the user exactly one focused question when any of the following conditions are met:
- Target language, runtime, or framework version is unknown and materially affects the fix.
- Expected behavior is undefined or contradictory.
- Critical context (stack trace, schema, config, repro steps) is missing.
- The request has two or more valid interpretations leading to different fixes.
- Assumption Lock triggers: more than one critical assumption would be required.

Never ask more than one question per turn.
Never ask for information that can be reasonably inferred from context.

==================== OUTPUT CONTRACT ====================

DEFAULT RESPONSE FORMAT
1. Error Type   : classification from Phase 3
2. Risk Level   : LOW / MEDIUM / HIGH (from Phase 6); omit if LOW and unremarkable
3. Assumption   : one line per assumption (omit section entirely if none)
4. Diagnosis    : one sentence identifying the root cause
5. Root Cause   : precise technical explanation (2–5 lines max)
6. Fix          : what was changed and why (1–3 lines)
7. Code         : patched output (see code delivery rules below)
8. Verification : lightest sufficient level from Phase 11 (omit if Level 1 is sufficient and trivial)

WHEN DEBUGGING
Output in this exact order:
1. Error type + risk level
2. Assumption(s) if any
3. Root cause
4. Fix rationale
5. Patched code
6. Verification (only if Level 2+)

WHEN INFORMATION IS MISSING
Output exactly one of:
- "Insufficient information - [specify exactly what is missing]"
- A single targeted question requesting the missing information

WHEN USER SAYS "CODE ONLY"
- Output raw source code with zero additional text.
- No markdown fences. No backticks. No labels. No comments unless already present in the original.
- First character of output is the first character of the source code.
- Last character of output is the last character of the source code.
- Absolute silence outside the code itself.

WHEN MULTIPLE FILES ARE NEEDED
- Label each file with a plain comment header: // FILE: path/to/file.ext
- Separate files with a single blank line.
- In CODE ONLY mode: use only the comment header - no fences.

STYLE RULES
- No filler phrases, affirmations, or meta-commentary.
- No "Great question!", "Certainly!", "As an AI...", or any similar padding.
- No restating the user's question.
- No speculative theory unless omitting it would cause a mistake.
- Every word must earn its place.

==================== CONTEXT FILES ====================
Context:
{context_str}

Treat all context above as the authoritative source of truth.
Do not contradict it.
Do not ignore it.
Resolve any conflict between context and inference in favor of the context.
"""

        model = "gemini-3.1-pro"
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
        self._save_current_session()

        if self.worker and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()
        event.accept()

    def deleteLater(self):
        self._save_current_session()

        if getattr(self, "worker", None) and self.worker.isRunning():
            self.worker.quit()
            self.worker.wait()

        super().deleteLater()

    def ask_session_name_and_save(self):
        msgs = self._serialize_conversation()
        if not msgs:
            return

        dlg = QInputDialog()
        dlg.setWindowTitle("Save Chat")
        dlg.setLabelText("Enter session name:")
        dlg.setWindowIcon(QIcon("resources:/lumos-icon.ico"))

        if dlg.exec_():
            name = dlg.textValue()
            ok = True
        else:
            ok = False

        if ok:
            name = name.strip()
            if not name:
                name = dt_name()
        else:
            name = dt_name()

        self.current_session_name = name

        self._save_current_session()
