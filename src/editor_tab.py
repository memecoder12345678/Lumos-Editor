import base64
import mimetypes
import os
import re

from PyQt5.Qsci import QsciScintilla
from PyQt5.QtCore import QEvent, QObject, QPointF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QDesktopServices, QFont, QPainter
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import QHBoxLayout, QScrollBar, QWidget

from src.lexer import JsonLexer, MarkdownLexer, PythonLexer

from . import md_renderer


class ExternalLinkHandlerPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, navigation_type, is_main_frame):
        if navigation_type == QWebEnginePage.NavigationTypeLinkClicked:
            if url.scheme() in ["http", "https"]:
                QDesktopServices.openUrl(url)
                return False
            else:
                return False


class AutoPairEventFilter(QObject):
    PAIRS = {
        "(": ")",
        "{": "}",
        "[": "]",
        '"': '"',
        "'": "'",
        "`": "`",
    }

    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def eventFilter(self, obj, event):
        if obj is not self.editor:
            return False

        if event.type() != QEvent.KeyPress:
            return False

        key = event.key()
        text = event.text()
        mods = event.modifiers()

        if mods & Qt.ControlModifier:
            if key in (Qt.Key_V,):
                return False
            return False

        if text in self.PAIRS:
            open_ch = text
            close_ch = self.PAIRS[open_ch]

            if self.editor.hasSelectedText():
                sel = self.editor.selectedText()
                wrapped = open_ch + sel + close_ch
                self.editor.replaceSelectedText(wrapped)
                sl, si, el, ei = self.editor.getSelection()
                self.editor.setCursorPosition(sl, si + 1)
                return True

            line, col = self.editor.getCursorPosition()
            self.editor.insert(open_ch + close_ch)
            self.editor.setCursorPosition(line, col + 1)
            return True

        if text and text in self.PAIRS.values():
            line, col = self.editor.getCursorPosition()
            line_text = self.editor.text(line)
            if col < len(line_text) and line_text[col] == text:
                self.editor.setCursorPosition(line, col + 1)
                return True
            return False

        if key == Qt.Key_Backspace:
            line, col = self.editor.getCursorPosition()
            if col == 0:
                return False
            line_text = self.editor.text(line)
            prev_char = line_text[col - 1] if (col - 1) < len(line_text) else None
            next_char = line_text[col] if col < len(line_text) else None
            if prev_char in self.PAIRS and self.PAIRS[prev_char] == next_char:
                self.editor.setSelection(line, col - 1, line, col + 1)
                self.editor.replaceSelectedText("")
                self.editor.setCursorPosition(line, col - 1)
                return True
            return False

        return False


class MiniMap(QWidget):
    SCROLLBAR_WIDTH = 12
    HIGH_RANGE = 100000

    def __init__(self, editor=None):
        super().__init__()
        self.editor = editor
        self.setFixedWidth(120)
        self.setMouseTracking(True)

        self._line_cache = {}
        self.LINE_PX = 2.0
        self.STYLE_FETCH_THRESHOLD = 3000
        self._mini_font = QFont("Monospace", 1)
        self._mini_font.setPixelSize(2)

        self._update_timer = QTimer(self)
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(100)
        self._update_timer.timeout.connect(self._on_update_timeout)

        self.editor.destroyed.connect(self._on_editor_destroyed)

        self.scrollbar = QScrollBar(Qt.Vertical, self)
        self.scrollbar.setFixedWidth(self.SCROLLBAR_WIDTH)
        self.scrollbar.setRange(0, self.HIGH_RANGE)
        self.scrollbar.setSingleStep(1)
        self.scrollbar.valueChanged.connect(self._on_scrollbar_value_changed)

        if self.editor:
            self.editor.SCN_UPDATEUI.connect(self._sync_scroll_from_editor)
            self.editor.textChanged.connect(self._request_update)
            self.editor.cursorPositionChanged.connect(self._request_update)
            self.editor.selectionChanged.connect(self._request_update)
            self.editor.modificationChanged.connect(self._request_update)
            vbar = self.editor.verticalScrollBar()
            vbar.valueChanged.connect(self._request_update)
            vbar.rangeChanged.connect(self._sync_scroll_from_editor)

            QTimer.singleShot(0, self._sync_scroll_from_editor)

    def _on_editor_destroyed(self, *args, **kwargs):
        if self._update_timer.isActive():
            self._update_timer.stop()
        self.editor = None

    def _update_scrollbar_thumb(self):
        if not self.editor:
            return
        total_lines = max(1, self.editor.lines())
        visible_lines = max(
            1, self.editor.SendScintilla(QsciScintilla.SCI_LINESONSCREEN)
        )

        page_ratio = float(visible_lines) / float(total_lines)
        page_ratio = max(0.0, min(1.0, page_ratio))

        page_step = max(1, int(round(page_ratio * self.HIGH_RANGE)))

        sb_h = max(1, self.scrollbar.height())
        min_px = 12
        min_ratio_needed = float(min_px) / float(sb_h)
        min_page_step = int(round(min_ratio_needed * self.HIGH_RANGE))
        if min_page_step < 1:
            min_page_step = 1

        page_step = max(page_step, min_page_step)
        page_step = min(page_step, self.HIGH_RANGE)

        self.scrollbar.setPageStep(page_step)

    def resizeEvent(self, event):
        self.scrollbar.setGeometry(
            self.width() - self.SCROLLBAR_WIDTH, 0, self.SCROLLBAR_WIDTH, self.height()
        )
        self._update_scrollbar_thumb()
        self._request_update()
        super().resizeEvent(event)

    def _request_update(self, *a, **k):
        if not self._update_timer.isActive():
            self._update_timer.start()

    def _on_update_timeout(self):
        if not self.editor:
            return
        self._rebuild_visible_cache()
        self._update_scrollbar_thumb()
        self.update()

    def _rebuild_visible_cache(self):
        if not self.editor:
            return
        total_lines = max(1, self.editor.lines())
        height = float(max(1, self.height()))
        lines_to_draw = min(int(height / self.LINE_PX), total_lines)
        start_line = int(self._scroll_start_line())
        lexer = None
        lexer = self.editor.lexer()
        use_full_styles = (total_lines <= self.STYLE_FETCH_THRESHOLD) and (
            lexer is not None
        )
        self._line_cache.clear()
        for i in range(lines_to_draw):
            ln = start_line + i
            if ln >= total_lines:
                break
            text = self.editor.text(ln)
            if not text or not text.strip():
                continue
            chars = []
            if use_full_styles:
                line_start = self.editor.positionFromLineIndex(ln, 0)
                if line_start is None:
                    for ch in text:
                        if not ch.isspace():
                            color = self.editor.color()
                            chars.append((ch, color))
                else:
                    for idx, ch in enumerate(text):
                        try:
                            style = self.editor.SendScintilla(
                                QsciScintilla.SCI_GETSTYLEAT, line_start + idx
                            )
                            color = lexer.color(style)
                        except Exception:
                            color = self.editor.color()
                        chars.append((ch, color))
            else:
                for ch in text:
                    if not ch.isspace():
                        try:
                            style0 = self.editor.SendScintilla(
                                QsciScintilla.SCI_GETSTYLEAT,
                                self.editor.positionFromLineIndex(ln, 0),
                            )
                            color = (
                                lexer.color(style0) if lexer else self.editor.color()
                            )
                        except Exception:
                            color = self.editor.color()
                        chars.append((ch, color))
            self._line_cache[ln] = chars

    def _scroll_start_line(self):
        if not self.editor:
            return 0
        total_lines = max(1, self.editor.lines())
        visible_lines = max(
            1, self.editor.SendScintilla(QsciScintilla.SCI_LINESONSCREEN)
        )
        max_first = max(0, total_lines - visible_lines)
        if max_first == 0:
            return 0
        ratio = float(self.scrollbar.value()) / float(self.HIGH_RANGE)
        start = int(round(ratio * max_first))
        return max(0, min(start, max_first))

    def _sync_scroll_from_editor(self, *a, **k):
        if not self.editor:
            return

        self._update_scrollbar_thumb()
        total_lines = max(1, self.editor.lines())
        visible_lines = max(
            1, self.editor.SendScintilla(QsciScintilla.SCI_LINESONSCREEN)
        )
        max_first = max(0, total_lines - visible_lines)
        first_visible = int(self.editor.firstVisibleLine())
        if max_first <= 0:
            ratio_val = 0
        else:
            ratio_val = float(first_visible) / float(max_first)
        new_val = int(round(ratio_val * self.HIGH_RANGE))
        prev = self.scrollbar.blockSignals(True)
        try:
            self.scrollbar.setValue(max(0, min(self.HIGH_RANGE, new_val)))
        finally:
            self.scrollbar.blockSignals(prev)
        self._request_update()

    def _on_scrollbar_value_changed(self, value):
        if not self.editor:
            return
        total_lines = max(1, self.editor.lines())
        visible_lines = max(
            1, self.editor.SendScintilla(QsciScintilla.SCI_LINESONSCREEN)
        )
        max_first = max(0, total_lines - visible_lines)
        if max_first <= 0:
            target_first = 0
        else:
            ratio = float(value) / float(self.HIGH_RANGE)
            target_first = int(round(ratio * max_first))
            target_first = max(0, min(target_first, max_first))

        self.editor.setFirstVisibleLine(target_first)

        if target_first == max_first:
            last = max(0, total_lines - 1)
            self.editor.ensureLineVisible(last)

        self._request_update()

    def paintEvent(self, event):
        if not self.editor:
            return
        painter = QPainter(self)
        painter.save()

        content_rect = self.rect().adjusted(0, 0, -self.SCROLLBAR_WIDTH, 0)
        editor_bg = self.editor.paper()
        lighter_bg = editor_bg.lighter(106)
        painter.fillRect(content_rect, lighter_bg)

        painter.setFont(self._mini_font)

        total_lines = max(1, self.editor.lines())
        if total_lines == 0:
            painter.restore()
            return

        height = float(max(1, content_rect.height()))
        lines_to_draw = min(int(height / self.LINE_PX), total_lines)
        start_line = int(self._scroll_start_line())

        for i in range(lines_to_draw):
            line_num = start_line + i
            if line_num >= total_lines:
                break
            y_pos = i * self.LINE_PX
            chars = self._line_cache.get(line_num)

            x = 2.0
            if chars:
                for ch, color in chars:
                    painter.setPen(color)
                    painter.drawText(QPointF(x, y_pos + self.LINE_PX - 0.5), ch)
                    x += 1.0
            else:
                text = self.editor.text(line_num)
                if text and text.strip():
                    lexer = self.editor.lexer()
                    style0 = self.editor.SendScintilla(
                        QsciScintilla.SCI_GETSTYLEAT,
                        self.editor.positionFromLineIndex(line_num, 0),
                    )
                    color = lexer.color(style0) if lexer else self.editor.color()
                    painter.setPen(color)
                    for ch in text:
                        if not ch.isspace():
                            painter.drawText(QPointF(x, y_pos + self.LINE_PX - 0.5), ch)
                            x += 1.0

        painter.restore()

    def mousePressEvent(self, event):
        if not self.editor:
            return

        if event.pos().x() >= (self.width() - self.SCROLLBAR_WIDTH):
            y = event.pos().y()
            sb_h = max(1, self.scrollbar.height())
            ratio = float(y) / float(sb_h)
            ratio = max(0.0, min(1.0, ratio))
            val = int(round(ratio * self.HIGH_RANGE))
            self.scrollbar.setValue(val)
            return

        clicked_offset = int(event.pos().y() / self.LINE_PX)

        total_lines = max(1, self.editor.lines())
        visible_lines = max(
            1, self.editor.SendScintilla(QsciScintilla.SCI_LINESONSCREEN)
        )

        start_line = self._scroll_start_line()

        clicked_line = start_line + clicked_offset
        clicked_line = max(0, min(clicked_line, total_lines - 1))

        desired_first = clicked_line - (visible_lines // 2)
        max_first = max(0, total_lines - visible_lines)
        desired_first = max(0, min(desired_first, max_first))

        self.editor.setFirstVisibleLine(desired_first)

        if max_first <= 0:
            self.scrollbar.setValue(0)
        else:
            ratio_val = float(desired_first) / float(max_first)
            self.scrollbar.setValue(int(round(ratio_val * self.HIGH_RANGE)))

        self._request_update()

    def wheelEvent(self, event):
        if not self.editor:
            return
        delta = event.angleDelta().y()
        if delta == 0:
            return
        steps = int(delta / 120)
        cur = self.scrollbar.value()
        step = max(1, self.HIGH_RANGE // 200)
        new_val = max(0, min(self.HIGH_RANGE, cur - steps * step))
        self.scrollbar.setValue(new_val)
        event.accept()


class EditorTab(QWidget):
    contentChanged = pyqtSignal(bool)

    def __init__(
        self, plugin_manager, filepath=None, main_window=None, wrap_mode=False
    ):
        super().__init__()
        self.plugin_manager = plugin_manager
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.setStyleSheet("border: none; margin: 0px; padding: 0px;")

        self.setLayout(main_layout)

        self.editor = QsciScintilla()

        self.minimap = MiniMap(self.editor)
        self.filepath = filepath
        self.is_modified = False
        self.main_window = main_window
        self.wrap_mode = wrap_mode
        self.theme_name = (
            self.main_window.config_manager.get("theme", "default-theme")
            if self.main_window
            else "default-theme"
        )
        main_layout.addWidget(self.editor)
        main_layout.addWidget(self.minimap)
        self.tabname = (
            os.path.splitext(os.path.basename(filepath or ""))[0][:27] + "..."
            if len(os.path.splitext(os.path.basename(filepath or ""))[0]) > 26
            else os.path.basename(filepath or "Untitled")
        )
        self.editor.textChanged.connect(self.handle_text_changed)
        self.editor.cursorPositionChanged.connect(self.update_cursor_position)

        self.is_markdown = filepath and filepath.endswith(".md")

        self.auto_pair_filter = AutoPairEventFilter(self.editor)
        self.editor.installEventFilter(self.auto_pair_filter)

        self.setup_basic_editor()

        self.setup_lexer_features(filepath)

        self.editor.installEventFilter(self)
        self.preview_mode = False
        self.preview_widget = None

    def setup_lexer_features(self, filepath):
        if not filepath or not self.plugin_manager:
            return

        lexer_class = self.plugin_manager.get_lexer_for_file(filepath)

        if lexer_class:
            font = self.editor.font()
            try:
                import inspect

                sig = inspect.signature(lexer_class.__init__)
                if "theme_name" in sig.parameters:
                    self.lexer = lexer_class(self.editor, theme_name=self.theme_name)
                else:
                    self.lexer = lexer_class(self.editor)
            except:
                self.lexer = lexer_class(self.editor)
            self.lexer.setDefaultFont(font)
            self.editor.setLexer(self.lexer)
            self.lexer.build_apis()
            self.editor.setAutoCompletionSource(QsciScintilla.AcsAPIs)
            self.editor.setAutoCompletionThreshold(1)
            self.editor.setAutoCompletionCaseSensitivity(False)
            self.editor.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

            self.auto_timer = QTimer(self)
            self.auto_timer.timeout.connect(self.refresh_autocomplete)
            return

        if filepath.endswith((".py", ".pyw")):
            self.setup_python_features()
        elif filepath.endswith(".json"):
            self.setup_json_features()
        elif self.is_markdown:
            self.setup_markdown_features()

    def refresh_autocomplete(self):
        if hasattr(self, "lexer") and self.filepath:
            self.lexer.build_apis()

    def setup_basic_editor(self):
        self.editor.textChanged.connect(self.on_text_changed)
        self.editor.textChanged.connect(self.update_line_count)
        self.editor.setPaper(QColor("#181a1b"))
        self.editor.setColor(QColor("#d4d4d4"))
        self.editor.setStyleSheet(
            """
            QAbstractItemView {
                background-color: #252526;
                color: #d4d4d4;
                border: None;
                border-radius: 4px;
                padding: 2px;
                min-height: 28px;
            }
            QAbstractItemView::item:selected {
                background-color: #323232;
                color: #d4d4d4;
            }
            QScrollBar:horizontal {
                border: none;
                background: #181a1b;
                height: 12px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #404040;
                min-width: 25px;
                border-radius: 6px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4a4a4a;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                border: none;
                background: none;
                width: 0px;
                height: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """
        )
        self.editor.SendScintilla(QsciScintilla.SCI_SETBUFFEREDDRAW, True)
        self.editor.SendScintilla(
            QsciScintilla.SCI_SETLAYOUTCACHE, QsciScintilla.SC_CACHE_PAGE
        )
        self.editor.SendScintilla(
            QsciScintilla.SCI_SETCODEPAGE, QsciScintilla.SC_CP_UTF8
        )

        self.editor.setWhitespaceVisibility(QsciScintilla.WsInvisible)
        self.editor.setEolVisibility(False)
        if self.wrap_mode:
            self.editor.setWrapMode(QsciScintilla.WrapWord)
            self.editor.setWrapVisualFlags(QsciScintilla.WrapFlagNone)
            self.editor.setWrapIndentMode(QsciScintilla.WrapIndentSame)
        else:
            self.editor.setWrapVisualFlags(QsciScintilla.WrapFlagNone)
            self.editor.setWrapMode(QsciScintilla.WrapNone)
        self.editor.setWhitespaceSize(0)

        font = QFont("consolas", 14)
        font.setFixedPitch(True)
        self.editor.setFont(font)

        self.editor.setPaper(QColor("#181a1b"))
        self.editor.setColor(QColor("#d4d4d4"))
        self.editor.setUtf8(True)

        self.editor.setMarginType(0, QsciScintilla.NumberMargin)
        self.update_line_count()
        self.editor.setMarginsForegroundColor(QColor("#1177AA"))
        self.editor.setMarginsBackgroundColor(QColor("#1e1e1e"))
        self.editor.setMarginsFont(font)
        self.editor.setMarginLineNumbers(0, True)

        cursor_color = QColor("#00ffdd")
        cursor_glow = QColor("#00ffdd")
        cursor_glow.setAlpha(20)

        self.editor.setCaretForegroundColor(cursor_color)
        self.editor.setCaretLineVisible(True)
        self.editor.setCaretWidth(2)
        self.editor.setCaretLineBackgroundColor(cursor_glow)

        selection_color = QColor("#00ffff")
        selection_glow = QColor("#00ffff")
        selection_glow.setAlpha(30)

        self.editor.setSelectionBackgroundColor(selection_glow)
        self.editor.setSelectionForegroundColor(selection_color)

        self.editor.setAutoIndent(True)
        self.editor.setIndentationGuides(True)
        self.editor.setIndentationsUseTabs(False)
        self.editor.setTabWidth(4)
        self.editor.setIndentationWidth(4)
        self.editor.convertIndents = True
        self.editor.setBackspaceUnindents(True)

        self.editor.setEolMode(QsciScintilla.EolUnix)
        self.editor.convertEols(QsciScintilla.EolUnix)

        self.editor.setBraceMatching(QsciScintilla.SloppyBraceMatch)

        self.editor.setMatchedBraceBackgroundColor(QColor("#3B514D"))
        self.editor.setMatchedBraceForegroundColor(QColor("#FFEF28"))

        self.editor.setUnmatchedBraceBackgroundColor(QColor("#3B514D"))
        self.editor.setUnmatchedBraceForegroundColor(QColor("#FF0000"))

        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.editor.SendScintilla(QsciScintilla.SCI_SETENDATLASTLINE, 0)

        self.editor.SendScintilla(QsciScintilla.SCI_SETSCROLLWIDTH, 1)
        self.editor.SendScintilla(QsciScintilla.SCI_SETSCROLLWIDTHTRACKING, True)

    def update_line_count(self):
        line_count = self.editor.lines()
        if line_count > 999999:
            self.editor.setMarginWidth(0, "00000000")
        if line_count > 99999:
            self.editor.setMarginWidth(0, "0000000")
        if line_count > 9999:
            self.editor.setMarginWidth(0, "000000")
        elif line_count > 999:
            self.editor.setMarginWidth(0, "00000")
        elif line_count > 99:
            self.editor.setMarginWidth(0, "0000")
        elif line_count > 0:
            self.editor.setMarginWidth(0, "000")

    def setup_markdown_features(self):
        font = self.editor.font()
        self.lexer = MarkdownLexer(self.editor, theme_name=self.theme_name)
        self.lexer.setDefaultFont(font)
        self.editor.setLexer(self.lexer)

    def setup_python_features(self):
        font = self.editor.font()
        self.lexer = PythonLexer(self.editor, theme_name=self.theme_name)
        self.lexer.setDefaultFont(font)
        self.editor.setLexer(self.lexer)

        self.lexer.build_apis()

        self.editor.setAutoCompletionSource(QsciScintilla.AcsAPIs)
        self.editor.setAutoCompletionThreshold(1)
        self.editor.setAutoCompletionCaseSensitivity(False)
        self.editor.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

        self.auto_timer = QTimer(self)
        self.auto_timer.timeout.connect(self.refresh_autocomplete)

    def setup_json_features(self):
        font = self.editor.font()
        self.lexer = JsonLexer(self.editor, theme_name=self.theme_name)
        self.lexer.setDefaultFont(font)
        self.editor.setLexer(self.lexer)

        self.lexer.build_apis()

        self.editor.setAutoCompletionSource(QsciScintilla.AcsAPIs)
        self.editor.setAutoCompletionThreshold(1)
        self.editor.setAutoCompletionCaseSensitivity(False)
        self.editor.setAutoCompletionUseSingle(QsciScintilla.AcusNever)

    def toggle_markdown_preview(self):
        if not self.is_markdown:
            return
        if self.preview_mode:
            self.preview_mode = False
            if self.preview_widget:
                self.preview_widget.hide()
                self.preview_widget.deleteLater()
                self.preview_widget = None
            self.editor.show()
            self.minimap.show()
        else:
            self.preview_mode = True
            self.editor.hide()
            self.minimap.hide()
            self.preview_widget = QWebEngineView(self)
            self.preview_widget.setPage(ExternalLinkHandlerPage(self.preview_widget))
            self.layout().addWidget(self.preview_widget)
            self.update_markdown_preview()

    def update_markdown_preview(self):
        if self.preview_mode and self.preview_widget:

            def replace_image_paths(match):
                img_path = match.group(2)
                if not os.path.isabs(img_path) and self.filepath:
                    img_path = os.path.join(os.path.dirname(self.filepath), img_path)

                if os.path.exists(img_path):
                    mime_type = mimetypes.guess_type(img_path)[0]
                    if mime_type and mime_type.startswith("image/"):
                        with open(img_path, "rb") as img_file:
                            img_data = base64.b64encode(img_file.read()).decode()
                            return f'<img src="data:{mime_type};base64,{img_data}"'
                return match.group(0)

            markdown_text = self.editor.text()
            lines = str(markdown_text).split("\n")

            out = []
            in_code = False
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                    out.append(line.strip())
                elif in_code:
                    out.append(line)
                else:
                    out.append(line.strip())

            markdown_text = "\n".join(out)

            html_content = md_renderer.markdown(markdown_text)

            html_content = re.sub(
                r'<img([^>]*?)src="([^"]+)"', replace_image_paths, html_content
            )

            html_template = f"""<html>
<head>
    <link href='https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism-tomorrow.min.css' rel='stylesheet' />
    <script src='https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.js'></script>
    <script src='https://cdn.jsdelivr.net/npm/prismjs@1.29.0/plugins/autoloader/prism-autoloader.min.js'></script>
    <style>
        ::-webkit-scrollbar {{
            background: #1a1a1a;
            width: 12px;
            height: 12px;
        }}
        ::-webkit-scrollbar-thumb {{
            background: #404040;
            min-height: 20px;
            min-width: 20px;
            border-radius: 6px;
        }}
        ::-webkit-scrollbar-thumb:hover {{
            background: #4a4a4a;
        }}
        body {{ 
            background: #181a1b; 
            color: #d4d4d4;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
        }}
        img {{ max-width: 60%; height: auto; }}
        table {{
            border-collapse: collapse;
            width: 60%;
            margin: 15px 0;
            background: #1e1e1e;
        }}
        th, td {{
            border: 1px solid #404040;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #252526;
            color: #0098ff;
            font-weight: bold;
        }}
        td {{
            color: #d4d4d4;
        }}
        tr:nth-child(odd) {{
            background-color: #252526;
        }}
        tr:hover {{
            background-color: #2d2d2d;
        }}
        pre {{
            background: #1e1e1e;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
            margin: 16px 0;
            width: 100%;
            word-break: break-word;
        }}
        inline_code {{
            width: 100%;
            font-family: Consolas, monospace;
            color: #9cdcfe;
            font-size: 14px;
        }}
        block_code {{
            width: 100%;
            font-family: Consolas, monospace;
            color: #9cdcfe;
            font-size: 14px;
            display: block;
            white-space: pre-wrap;
            word-break: break-word;
        }}
        table.code-block {{
            width: 100%;
            margin: 16px 0;
            background: #1e1e1e;
            border-radius: 4px;
        }}
        table.code-block td {{
            white-space: pre;
        }}
        table.code-block pre {{
            margin: 0;
            padding: 0;
            background: transparent;
            white-space: pre;
        }}
        table.code-block code {{
            font-family: Consolas, monospace;  
            color: #9cdcfe;
            font-size: 14px;
            white-space: pre;
            display: block;
        }}
        .markdown-quote {{
            border-left: 4px solid #d0d7de;
            padding: 0 1em;
            color: #656d76;
            margin: 1em 0;
        }}

        .task-list-item {{
            list-style-type: none;
        }}

        .task-list-item input[type="checkbox"] {{
            margin: 0 0.5em 0.25em -1.4em;
            vertical-align: middle;
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>"""
            self.preview_widget.setHtml(html_template)

    def handle_text_changed(self):
        if not self.is_modified:
            self.is_modified = True
            current_index = self.main_window.tabs.currentIndex()
            current_text = self.main_window.tabs.tabText(current_index)
            if not current_text.startswith("*"):
                self.main_window.tabs.setTabText(current_index, "*" + current_text)

    def on_text_changed(self):
        if not self.is_modified:
            self.is_modified = True
        if hasattr(self, "lexer"):
            self.editor.recolor()

    def save(self):
        self.is_modified = False
        current_index = self.main_window.tabs.currentIndex()
        current_text = self.main_window.tabs.tabText(current_index)
        if current_text.startswith("*") and self.filepath:
            self.main_window.tabs.setTabText(current_index, current_text[1:])

    def eventFilter(self, obj, event):
        if obj is self.editor and event.type() == QEvent.KeyPress:
            if event.modifiers() & Qt.ControlModifier and event.key() == Qt.Key_Slash:
                orig_line, orig_idx = self.editor.getCursorPosition()
                if self.editor.hasSelectedText():
                    sl, _, el, _ = self.editor.getSelection()
                    if el < self.editor.lines() - 1:
                        self.editor.setSelection(sl, 0, el + 1, 0)
                    else:
                        self.editor.setSelection(sl, 0, el, self.editor.lineLength(el))
                    text = self.editor.selectedText()
                    self.editor.replaceSelectedText(self.toggle_comment(text))
                else:
                    line, _ = self.editor.getCursorPosition()
                    self.editor.setSelection(
                        line, 0, line, self.editor.lineLength(line)
                    )
                    text = self.editor.selectedText()
                    self.editor.replaceSelectedText(self.toggle_comment(text))
                self.editor.setSelection(-1, -1, -1, -1)
                self.editor.setCursorPosition(orig_line, orig_idx)
                return True

            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_X:
                if not self.editor.hasSelectedText():
                    line, _ = self.editor.getCursorPosition()
                    self.editor.setSelection(
                        line, 0, line, self.editor.lineLength(line)
                    )
                    self.editor.cut()
                    return True

            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_C:
                if not self.editor.hasSelectedText():
                    line, _ = self.editor.getCursorPosition()
                    self.editor.setSelection(
                        line, 0, line, self.editor.lineLength(line)
                    )
                    self.editor.copy()
                    self.editor.setCursorPosition(
                        line, self.editor.getCursorPosition()[1]
                    )
                    self.editor.setSelection(-1, -1, -1, -1)
                    return True

            if event.modifiers() == Qt.ControlModifier and event.key() == Qt.Key_Space:
                if self.filepath:
                    self.lexer.build_apis()
                    self.editor.autoCompleteFromAPIs()
                    return True

        return super().eventFilter(obj, event)

    def toggle_comment(self, text):
        lines = text.splitlines(True)

        to_comment = any(
            line.strip() and not line.strip().startswith("#") for line in lines
        )

        result = []
        for line in lines:
            stripped_line = line.lstrip()

            if to_comment:
                if line.strip() and not stripped_line.startswith("#"):
                    indent_len = 0
                    while indent_len < len(line) and line[indent_len].isspace():
                        indent_len += 1
                    result.append(line[:indent_len] + "# " + line[indent_len:])
                else:
                    result.append(line)
            else:
                if stripped_line.startswith("#"):
                    hash_pos = line.find("#")

                    if hash_pos != -1:
                        if hash_pos + 1 < len(line) and line[hash_pos + 1] == " ":
                            result.append(line[:hash_pos] + line[hash_pos + 2 :])
                        else:
                            result.append(line[:hash_pos] + line[hash_pos + 1 :])
                    else:
                        result.append(line)
                else:
                    result.append(line)

        return "".join(result)

    def update_cursor_position(self):
        line, col = self.editor.getCursorPosition()
        self.main_window.status_position.setText(f"Ln {line + 1}, Col {col + 1}")

    def start_analysis_loop(self):
        if hasattr(self, "auto_timer"):
            self.auto_timer.start(500)

    def stop_analysis_loop(self):
        if hasattr(self, "auto_timer"):
            self.auto_timer.stop()
