import re
import json
import os
from typing import TypedDict
import keyword
import builtins
import jedi
from PyQt5.Qsci import QsciAPIs
import types
from PyQt5.QtCore import QTimer
from PyQt5.Qsci import QsciLexerCustom
from PyQt5.QtGui import QFont, QColor


class DefaultConfig(TypedDict):
    color: str
    paper: str
    font: tuple[str, int]


class BaseLexer(QsciLexerCustom):
    def __init__(
        self, language_name, editor, theme=None, defaults: DefaultConfig = None
    ):
        super(BaseLexer, self).__init__(editor)

        self.editor = editor
        self.apis = QsciAPIs(self)
        self.language_name = language_name
        self.theme_json = None
        if theme is None:
            self.theme = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), f".{os.sep}theme.json"
            )
        else:
            self.theme = theme

        self.token_list: list[str, str] = []

        self.keywords_list = []
        self.builtin_names = []

        if defaults is None:
            defaults: DefaultConfig = {}
            defaults["color"] = "#b2eff5"
            defaults["paper"] = "#181a1b"
            defaults["font"] = ("Consolas", 14)

        self.setDefaultColor(QColor(defaults["color"]))
        self.setDefaultPaper(QColor(defaults["paper"]))
        self.setDefaultFont(QFont(defaults["font"][0], defaults["font"][1]))

        self._init_theme_vars()
        self._init_theme()

    def setKeywords(self, keywords: list[str]):
        self.keywords_list = keywords

    def setBuiltinNames(self, buitin_names: list[str]):
        self.builtin_names = buitin_names

    def _init_theme_vars(self):

        self.DEFAULT = 0
        self.KEYWORD = 1
        self.TYPES = 2
        self.STRING = 3
        self.BRACKETS = 4
        self.COMMENTS = 5
        self.CONSTANTS = 6
        self.FUNCTIONS = 7
        self.FUNCTION_DEF = 8
        self.CLASS_DEF = 9
        self.CLASSES = 10

        self.default_names = [
            "default",
            "keyword",
            "functions",
            "class_def",
            "function_def",
            "classes",
            "string",
            "types",
            "brackets",
            "comments",
            "constants",
        ]

        self.style_map = {
            "default": self.DEFAULT,
            "keyword": self.KEYWORD,
            "types": self.TYPES,
            "string": self.STRING,
            "brackets": self.BRACKETS,
            "comments": self.COMMENTS,
            "constants": self.CONSTANTS,
            "functions": self.FUNCTIONS,
            "class_def": self.CLASS_DEF,
            "function_def": self.FUNCTION_DEF,
            "classes": self.CLASSES,
        }

        self.font_weights = {
            "thin": QFont.Thin,
            "extralight": QFont.ExtraLight,
            "light": QFont.Light,
            "normal": QFont.Normal,
            "medium": QFont.Medium,
            "demibold": QFont.DemiBold,
            "bold": QFont.Bold,
            "extrabold": QFont.ExtraBold,
            "black": QFont.Black,
        }

    def _init_theme(self):
        if not os.path.exists(self.theme):
            return

        try:
            with open(self.theme, "r") as f:
                self.theme_json = json.load(f)
        except Exception as e:
            return

        colors = self.theme_json["theme"]["syntax"]

        for clr in colors:
            name: str = list(clr.keys())[0]

            if name not in self.default_names:
                continue

            style_id = self.style_map.get(name)
            if style_id is None:
                continue

            for k, v in clr[name].items():
                if k == "color":
                    self.setColor(QColor(v), style_id)
                elif k == "paper-color":
                    self.setPaper(QColor(v), style_id)
                elif k == "font":
                    try:
                        self.setFont(
                            QFont(
                                v.get("family", "Consolas"),
                                v.get("font-size", 14),
                                self.font_weights.get(
                                    v.get("font-weight", QFont.Normal)
                                ),
                                v.get("italic", False),
                            ),
                            style_id,
                        )
                    except AttributeError as e:
                        pass

    def language(self) -> str:
        return self.language_name

    def description(self, style: int) -> str:
        if style == self.DEFAULT:
            return "DEFAULT"
        elif style == self.CLASSES:
            return "CLASSES"
        elif style == self.KEYWORD:
            return "KEYWORD"
        elif style == self.TYPES:
            return "TYPES"
        elif style == self.STRING:
            return "STRING"
        elif style == self.COMMENTS:
            return "COMMENTS"
        elif style == self.FUNCTIONS:
            return "FUNCTIONS"
        elif style == self.FUNCTION_DEF:
            return "FUNCTION_DEF"
        elif style == self.CLASS_DEF:
            return "CLASS_DEF"
        elif style == self.BRACKETS:
            return "BRACKETS"
        elif style == self.CONSTANTS:
            return "CONSTANTS"
        return ""

    def generate_tokens(self, text):
        p = re.compile(r"/\*|\*/|\s+|\w+|\W")
        self.token_list = [
            (token, len(bytearray(token, "utf-8"))) for token in p.findall(text)
        ]

    def next_tok(self, skip: int = None):
        if skip is not None and skip > 0:
            for _ in range(skip):
                if len(self.token_list) > 0:
                    self.token_list.pop(0)
                else:
                    return None
        if len(self.token_list) > 0:
            return self.token_list.pop(0)
        else:
            return None

    def peek_tok(self, n=0):
        try:
            return self.token_list[n]
        except IndexError:
            return ("", 0)

    def skip_spaces_peek(self, skip_tokens=None):
        i = 0
        if skip_tokens is not None:
            i = skip_tokens

        temp_idx = i
        while (
            temp_idx < len(self.token_list) and self.token_list[temp_idx][0].isspace()
        ):
            temp_idx += 1

        if temp_idx < len(self.token_list):
            return self.token_list[temp_idx], temp_idx + 1
        else:
            return ("", 0), temp_idx + 1

    def build_apis(self):
        self.apis.clear()
        self.apis.prepare()


class PythonLexer(BaseLexer):
    def __init__(self, editor):
        super(PythonLexer, self).__init__("Python", editor)

        self.current_file = None
        self.class_names = set()
        self.apis = QsciAPIs(self)
        self.user_functions = set()
        self.builtin_functions = set(
            name
            for name, obj in vars(builtins).items()
            if isinstance(obj, types.BuiltinFunctionType)
        )
        self.builtin_classes = set(
            name for name, obj in vars(builtins).items() if isinstance(obj, type)
        )

        self.setKeywords(keyword.kwlist)

        self.in_string_mode = False
        self.string_quote_char = None
        self.is_triple_string = False
        self.triple_closing_match_count = 0
        self.is_escape_sequence_char = False

        self.current_lexer_pos = 0

        self.recheck_timer = QTimer()
        self.recheck_timer.setSingleShot(True)
        self.recheck_timer.setInterval(400)
        self.recheck_timer.timeout.connect(self.perform_name_check)

        if self.editor:
            self.editor.textChanged.connect(self.trigger_recheck)

    def trigger_recheck(self):
        self.recheck_timer.start()

    def perform_name_check(self):
        text = self.editor.text()

        processed_text = re.sub(r'""".*?"""|\'\'\'.*?\'\'\'', "", text, flags=re.DOTALL)

        processed_text = re.sub(
            r'"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\'', "", processed_text
        )

        text_no_comments_or_strings = re.sub(
            r"#.*$", "", processed_text, flags=re.MULTILINE
        )

        class_pattern = r"\bclass\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        current_class_names = set(
            re.findall(class_pattern, text_no_comments_or_strings)
        )

        func_pattern = r"\bdef\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        current_func_names = set(re.findall(func_pattern, text_no_comments_or_strings))

        if (
            self.class_names != current_class_names
            or self.user_functions != current_func_names
        ):
            self.class_names = current_class_names
            self.user_functions = current_func_names
            if hasattr(self.editor, "SendScintilla") and hasattr(
                self.editor, "SCI_COLOURISE"
            ):
                self.editor.SendScintilla(self.editor.SCI_COLOURISE, 0, -1)

    def set_current_file(self, filepath):
        self.current_file = filepath
        if filepath:
            text = self.editor.text()
            self.check_removed_names(text)
        else:
            self.class_names.clear()
            self.user_functions.clear()

    def _update_state_up_to(self, scan_to_pos):
        if scan_to_pos == 0:
            self.in_string_mode = False
            self.string_quote_char = None
            self.is_triple_string = False
            self.triple_closing_match_count = 0
            self.is_escape_sequence_char = False
            self.current_lexer_pos = 0
            return

        if getattr(self, "current_lexer_pos", 0) >= scan_to_pos:
            self.in_string_mode = False
            self.string_quote_char = None
            self.is_triple_string = False
            self.triple_closing_match_count = 0
            self.is_escape_sequence_char = False

        editor = self.editor
        current_line_num = editor.SendScintilla(
            editor.SCI_LINEFROMPOSITION, scan_to_pos
        )
        line_start_pos = editor.SendScintilla(
            editor.SCI_POSITIONFROMLINE, current_line_num
        )

        if (
            line_start_pos < scan_to_pos
            and getattr(self, "current_lexer_pos", 0) < line_start_pos
        ):
            pass

        self.current_lexer_pos = scan_to_pos

    def styleText(self, start: int, end: int) -> None:
        if start >= end:
            return

        full_text = self.editor.text()
        if not full_text:
            return

        self._update_state_up_to(start)
        self.startStyling(start)

        visible_text = full_text[start : min(end, len(full_text))]
        self.generate_tokens(visible_text)

        token_index_in_visible_text = 0

        line_comment_active = False
        if start > 0:
            previous_style_nr = self.editor.SendScintilla(
                self.editor.SCI_GETSTYLEAT, start - 1
            )
            if previous_style_nr == self.COMMENTS:
                char_before_start = self.editor.text(start - 1, start)
                if char_before_start and char_before_start != "\n":
                    line_comment_active = True

        visible_text = full_text[start : min(end, len(full_text))]
        self.generate_tokens(visible_text)

        while True:
            if line_comment_active:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                self.setStyling(curr_token[1], self.COMMENTS)
                if "\n" in curr_token[0]:
                    line_comment_active = False
                continue

            if self.in_string_mode:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                tok_str_mode = curr_token[0]
                tok_len_mode = curr_token[1]
                self.setStyling(tok_len_mode, self.STRING)

                if self.is_triple_string:
                    if tok_str_mode == self.string_quote_char:
                        self.triple_closing_match_count += 1
                        if self.triple_closing_match_count == 3:
                            self.in_string_mode = False
                            self.is_triple_string = False
                    else:
                        self.triple_closing_match_count = 0
                else:
                    if self.is_escape_sequence_char:
                        self.is_escape_sequence_char = False
                    elif tok_str_mode == "\\":
                        self.is_escape_sequence_char = True
                    elif tok_str_mode == self.string_quote_char:
                        self.in_string_mode = False
                continue

            tok_num1_peek = self.peek_tok(0)
            tok_dot_peek = self.peek_tok(1)
            tok_num2_peek = self.peek_tok(2)

            if (
                tok_num1_peek
                and tok_num1_peek[0].isnumeric()
                and tok_dot_peek
                and tok_dot_peek[0] == "."
                and tok_num2_peek
                and tok_num2_peek[0].isnumeric()
            ):

                num1_tok = self.next_tok()
                self.setStyling(num1_tok[1], self.CONSTANTS)

                dot_tok = self.next_tok()
                self.setStyling(dot_tok[1], self.CONSTANTS)

                num2_tok = self.next_tok()
                self.setStyling(num2_tok[1], self.CONSTANTS)
                continue

            if tok_num1_peek is None:
                break

            curr_token = self.next_tok()
            if curr_token is None:
                break

            tok_str: str = curr_token[0]
            tok_len: int = curr_token[1]

            if line_comment_active:
                self.setStyling(tok_len, self.COMMENTS)
                if "\n" in tok_str:
                    line_comment_active = False
                continue

            if self.in_string_mode:
                self.setStyling(tok_len, self.STRING)
                if self.is_triple_string:
                    if tok_str == self.string_quote_char:
                        self.triple_closing_match_count += 1
                        if self.triple_closing_match_count == 3:
                            self.in_string_mode = False
                            self.is_triple_string = False
                            self.string_quote_char = None
                            self.triple_closing_match_count = 0
                    else:
                        self.triple_closing_match_count = 0
                else:
                    if self.is_escape_sequence_char:
                        self.is_escape_sequence_char = False
                    elif tok_str == "\\":
                        self.is_escape_sequence_char = True
                    elif tok_str == self.string_quote_char:
                        self.in_string_mode = False
                        self.string_quote_char = None
                token_index_in_visible_text += len(tok_str.encode("utf-8"))
                continue

            if tok_str == "#":
                self.setStyling(tok_len, self.COMMENTS)
                line_comment_active = True
                continue

            if tok_str in ['"', "'"]:
                p1 = self.peek_tok(0)
                p2 = self.peek_tok(1)
                if p1[0] == tok_str and p2[0] == tok_str:
                    combined_len = tok_len + p1[1] + p2[1]
                    self.setStyling(combined_len, self.STRING)
                    _ = self.next_tok()
                    _ = self.next_tok()

                    self.in_string_mode = True
                    self.is_triple_string = True
                    self.string_quote_char = tok_str
                    self.triple_closing_match_count = 0
                    self.is_escape_sequence_char = False
                    token_index_in_visible_text += len((tok_str * 3).encode("utf-8"))
                    continue
                else:
                    self.setStyling(tok_len, self.STRING)
                    self.in_string_mode = True
                    self.is_triple_string = False
                    self.string_quote_char = tok_str
                    self.is_escape_sequence_char = False
                    self.triple_closing_match_count = 0
                    token_index_in_visible_text += len(tok_str.encode("utf-8"))
                    continue

            if tok_str in self.class_names:
                self.setStyling(tok_len, self.CLASSES)
            elif tok_str in self.user_functions:
                self.setStyling(tok_len, self.FUNCTIONS)
            elif tok_str in self.builtin_functions:
                self.setStyling(tok_len, self.FUNCTIONS)
            elif tok_str in self.builtin_classes:
                self.setStyling(tok_len, self.CLASSES)
            elif tok_str == "class":
                name_candidate_tok, num_tokens_to_name = self.skip_spaces_peek()
                if name_candidate_tok[0] and name_candidate_tok[0].isidentifier():
                    after_name_tok, _ = self.skip_spaces_peek(num_tokens_to_name)
                    if after_name_tok[0] in (":", "("):
                        self.setStyling(tok_len, self.KEYWORD)
                        for _ in range(
                            num_tokens_to_name
                            - 1
                            - (1 if name_candidate_tok[0].isspace() else 0)
                        ):
                            space_tok = self.next_tok()
                            self.setStyling(space_tok[1], self.DEFAULT)
                        name_tok_actual = self.next_tok()
                        self.setStyling(name_tok_actual[1], self.CLASS_DEF)
                    else:
                        self.setStyling(tok_len, self.KEYWORD)
                else:
                    self.setStyling(tok_len, self.KEYWORD)
            elif tok_str == "def":
                name_candidate_tok, num_tokens_to_name = self.skip_spaces_peek()
                if name_candidate_tok[0] and name_candidate_tok[0].isidentifier():
                    self.setStyling(tok_len, self.KEYWORD)
                    for _ in range(
                        num_tokens_to_name
                        - 1
                        - (1 if name_candidate_tok[0].isspace() else 0)
                    ):
                        space_tok = self.next_tok()
                        self.setStyling(space_tok[1], self.DEFAULT)
                    name_tok_actual = self.next_tok()
                    self.setStyling(name_tok_actual[1], self.FUNCTION_DEF)
                else:
                    self.setStyling(tok_len, self.KEYWORD)
            elif tok_str in self.keywords_list and tok_str not in [
                "True",
                "False",
                "None",
            ]:
                self.setStyling(tok_len, self.KEYWORD)
            elif tok_str.strip() == "." and self.peek_tok(0)[0].isidentifier():
                self.setStyling(tok_len, self.DEFAULT)
                identifier_after_dot = self.next_tok()
                if self.peek_tok(0)[0] == "(":
                    self.setStyling(identifier_after_dot[1], self.FUNCTIONS)
                else:
                    self.setStyling(identifier_after_dot[1], self.DEFAULT)
            elif tok_str == "self" or tok_str in ["True", "False", "None"]:
                self.setStyling(tok_len, self.TYPES)
            elif tok_str.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok_str in ["(", ")", "[", "]", "{", "}"]:
                self.setStyling(tok_len, self.BRACKETS)
            elif tok_str.isspace():
                self.setStyling(tok_len, self.DEFAULT)
            else:
                self.setStyling(tok_len, self.DEFAULT)

    def build_apis(self):
        self.apis.clear()

        editor = self.editor
        code = editor.text()
        line, col = editor.getCursorPosition()
        pos = editor.SendScintilla(editor.SCI_GETCURRENTPOS)
        style = editor.SendScintilla(editor.SCI_GETSTYLEAT, pos - 1) if pos > 0 else -1

        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return

        script = jedi.Script(code=code)
        completions = script.complete(line + 1, col)

        for completion in completions:
            self.apis.add(completion.name)

        self.apis.prepare()


class JsonLexer(BaseLexer):
    def __init__(self, editor):
        super(JsonLexer, self).__init__("JSON", editor)
        self.apis = QsciAPIs(self)

    def styleText(self, start, end):
        self.startStyling(start)
        text = self.editor.text()[start:end]

        self.generate_tokens(text)

        string_mode = False

        while len(self.token_list) > 0:
            if string_mode:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                tok_str_mode, tok_len_mode = curr_token

                self.setStyling(tok_len_mode, self.STRING)
                if tok_str_mode == '"':
                    string_mode = False
                continue

            tok_num1_peek = self.peek_tok(0)
            tok_dot_peek = self.peek_tok(1)
            tok_num2_peek = self.peek_tok(2)

            if (
                tok_num1_peek
                and tok_num1_peek[0].isnumeric()
                and tok_dot_peek
                and tok_dot_peek[0] == "."
                and tok_num2_peek
                and tok_num2_peek[0].isnumeric()
            ):

                num1_tok = self.next_tok()
                self.setStyling(num1_tok[1], self.CONSTANTS)

                dot_tok = self.next_tok()
                self.setStyling(dot_tok[1], self.CONSTANTS)

                num2_tok = self.next_tok()
                self.setStyling(num2_tok[1], self.CONSTANTS)
                continue

            if tok_num1_peek is None:
                break

            curr_token_data = self.next_tok()
            if curr_token_data is None:
                break

            tok: str = curr_token_data[0]
            tok_len: int = curr_token_data[1]

            if tok == '"':
                self.setStyling(tok_len, self.STRING)
                string_mode = True
                continue

            if tok == "-":
                self.setStyling(tok_len, self.TYPES)
            if tok in "()[]{}":
                self.setStyling(tok_len, self.BRACKETS)
            elif tok.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok in ["true", "false", "null"]:
                self.setStyling(tok_len, self.TYPES)
            else:
                self.setStyling(tok_len, self.DEFAULT)

    def build_apis(self):
        self.apis.clear()

        editor = self.editor
        pos = editor.SendScintilla(editor.SCI_GETCURRENTPOS)
        style = editor.SendScintilla(editor.SCI_GETSTYLEAT, pos - 1) if pos > 0 else -1

        if style in (self.STRING,):
            self.apis.prepare()
            return

        self.apis.add("true")
        self.apis.add("false")
        self.apis.add("null")

        self.apis.prepare()
