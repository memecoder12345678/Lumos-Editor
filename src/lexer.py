import builtins
import io
import json
import keyword
import os
import re
import tokenize
from typing import TypedDict

import jedi
from pygments import lex
# from pygments.lexer import bygroups, inherit
from pygments.lexers.data import JsonLexer as PyG_JsonLexer
from pygments.lexers.markup import MarkdownLexer as PyG_MarkdownLexer

# from pygments.lexers.python import PythonLexer as PyG_PythonLexer
from pygments.token import (
    Comment,
    Generic,
    Keyword,
    Literal,
    Name,
    Number,
    # Operator,
    Punctuation,
    String,
    # Text,
    Token,
)
from PyQt5.Qsci import QsciAPIs, QsciLexerCustom
from PyQt5.QtGui import QColor, QFont


class DefaultConfig(TypedDict):
    color: str
    paper: str
    font: tuple[str, int]


class BaseLexer(QsciLexerCustom):
    def __init__(
        self,
        language_name,
        editor,
        theme_name="default",
        defaults: DefaultConfig = None,
    ):
        super(BaseLexer, self).__init__(editor)

        self.editor = editor
        self.apis = QsciAPIs(self)
        self.language_name = language_name
        self.theme_json = None

        themes_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "themes"
        )
        self.theme = os.path.join(themes_dir, theme_name, "theme.json")

        if defaults is None:
            defaults: DefaultConfig = {}
            defaults["color"] = "#d4d4d4"
            defaults["paper"] = "#181a1b"
            defaults["font"] = ("Consolas", 14)

        self.setDefaultColor(QColor(defaults["color"]))
        self.setDefaultPaper(QColor(defaults["paper"]))
        self.setDefaultFont(QFont(defaults["font"][0], defaults["font"][1]))

        self._init_theme_vars()
        self._init_theme()

    def _init_theme_vars(self):
        self.DEFAULT = 0
        self.KEYWORD = 1
        self.TYPES = 2
        self.STRING = 3
        self.COMMENTS = 4
        self.CONSTANTS = 5
        self.FUNCTIONS = 6
        self.FUNCTION_DEF = 7
        self.CLASS_DEF = 8
        self.CLASSES = 9

        self.default_names = [
            "default",
            "keyword",
            "functions",
            "class_def",
            "function_def",
            "classes",
            "string",
            "types",
            "comments",
            "constants",
        ]

        self.style_map = {
            "default": self.DEFAULT,
            "keyword": self.KEYWORD,
            "types": self.TYPES,
            "string": self.STRING,
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
            with open(self.theme, "r", encoding="utf-8") as f:
                self.theme_json = json.load(f)
        except Exception:
            return

        paper_color = self.theme_json.get("theme", {}).get("paper-color")
        margin_color = self.theme_json.get("theme", {}).get("margin-color")
        if paper_color:
            bg_color = QColor(paper_color)
            self.setDefaultPaper(bg_color)
            if hasattr(self, "editor") and self.editor:
                self.editor.setPaper(bg_color)
                self.editor.setMarginsBackgroundColor(bg_color.darker(110))
                self.editor.setMarginsForegroundColor(
                    QColor(margin_color) if margin_color else bg_color.lighter(150)
                )
                self.editor.setStyleSheet(
                    f"""
                    QAbstractItemView {{
                        background-color: {bg_color.lighter(110).name()};
                        color: {self.color(self.DEFAULT).name()};
                        border: None;
                        border-radius: 4px;
                        padding: 2px;
                        min-height: 28px;
                    }}
                    QAbstractItemView::item:selected {{
                        background-color: {bg_color.lighter(130).name()};
                        color: {self.color(self.DEFAULT).name()};
                    }}
                """
                )
                self.editor.setMatchedBraceBackgroundColor(bg_color.lighter(120))
                self.editor.setUnmatchedBraceBackgroundColor(bg_color.lighter(120))
        else:
            self.setDefaultPaper(QColor("#181a1b"))
            self.editor.setPaper(self.defaultPaper())
            self.editor.setMarginsBackgroundColor(QColor("#1e1e1e"))
            self.editor.setMarginsForegroundColor(QColor("#1177AA"))
            self.editor.setMatchedBraceBackgroundColor(self.editor.paper().lighter(120))
            self.editor.setUnmatchedBraceBackgroundColor(
                self.editor.paper().lighter(120)
            )
            self.editor.setStyleSheet(
                f"""
                    QAbstractItemView {{
                        background-color: {self.editor.paper().lighter(110).name()};
                        color: {self.color(self.DEFAULT).name()};
                        border: None;
                        border-radius: 4px;
                        padding: 2px;
                        min-height: 28px;
                    }}
                    QAbstractItemView::item:selected {{
                        background-color: {self.editor.paper().lighter(130).name()};
                        color: {self.color(self.DEFAULT).name()};
                    }}
                """
            )

        colors = self.theme_json.get("theme", {}).get("syntax", [])
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
                    except AttributeError:
                        pass

    def language(self) -> str:
        return self.language_name

    def description(self, style: int) -> str:
        reverse_map = {v: k.upper() for k, v in self.style_map.items()}
        return reverse_map.get(style, "")


class PythonCustomLexer(BaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Python", editor, theme_name=theme_name)

        all_keywords = set(keyword.kwlist)
        if hasattr(keyword, "softkwlist"):
            all_keywords.update(keyword.softkwlist)

        self.keyword_set = all_keywords

        builtin_names = {name for name in dir(builtins) if not name.startswith("_")}

        self.builtin_set = builtin_names

        self.ident_re = re.compile(r"[A-Za-z_]\w*")
        self.decorator_re = re.compile(r"@[A-Za-z_]\w*")
        self.class_def_re = re.compile(r"\bclass\s+([A-Za-z_]\w*)")
        self.func_def_re = re.compile(r"\bdef\s+([A-Za-z_]\w*)")
        self.func_call_re = re.compile(r"\b([A-Za-z_]\w*)\b(?=\s*\()")
        self.number_re = re.compile(r"\b(?:0[bB][01](?:_?[01])*|0[oO][0-7](?:_?[0-7])*|0[xX][0-9a-fA-F](?:_?[0-9a-fA-F])*|\d(?:_?\d)*(?:\.\d(?:_?\d)*)?(?:[eE][+-]?\d(?:_?\d)*)?j?)\b")

    def _pos_to_index(self, text, line_starts, pos):
        line, col = pos
        return line_starts[line - 1] + col

    def styleText(self, start: int, end: int):
        text = self.editor.text()[start:end]
        if not text:
            return

        line_starts = [0]
        for m in re.finditer(r"\n", text):
            line_starts.append(m.end())

        spans = []

        try:
            toks = tokenize.generate_tokens(io.StringIO(text).readline)
            for tok in toks:
                ttype = tok.type
                tstr = tok.string

                if ttype == tokenize.COMMENT:
                    s = self._pos_to_index(text, line_starts, tok.start)
                    e = self._pos_to_index(text, line_starts, tok.end)
                    spans.append((s, e, self.COMMENTS))

                elif ttype == tokenize.STRING:
                    s = self._pos_to_index(text, line_starts, tok.start)
                    e = self._pos_to_index(text, line_starts, tok.end)
                    spans.append((s, e, self.STRING))

                elif ttype == tokenize.NAME:
                    s = self._pos_to_index(text, line_starts, tok.start)
                    e = self._pos_to_index(text, line_starts, tok.end)

                    if tstr in self.keyword_set:
                        spans.append((s, e, self.KEYWORD))
                    elif tstr in self.builtin_set:
                        spans.append((s, e, self.TYPES))

        except tokenize.TokenError:
            pass

        for m in self.decorator_re.finditer(text):
            spans.append((m.start(), m.end(), self.FUNCTIONS))

        for m in self.class_def_re.finditer(text):
            spans.append((m.start(1), m.end(1), self.CLASS_DEF))

        for m in self.func_def_re.finditer(text):
            spans.append((m.start(1), m.end(1), self.FUNCTION_DEF))

        for m in self.func_call_re.finditer(text):
            name = m.group(1)
            if name not in self.keyword_set and name not in self.builtin_set:
                spans.append((m.start(1), m.end(1), self.FUNCTIONS))

        for m in self.number_re.finditer(text):
            spans.append((m.start(), m.end(), self.CONSTANTS))

        styles = [self.DEFAULT] * len(text)
        prio = [-1] * len(text)

        priority = {
            self.COMMENTS: 100,
            self.STRING: 90,
            self.FUNCTION_DEF: 70,
            self.CLASS_DEF: 70,
            self.KEYWORD: 60,
            self.TYPES: 50,
            self.CONSTANTS: 40,
            self.FUNCTIONS: 10,
        }

        for s, e, sty in spans:
            p = priority.get(sty, 0)
            s = max(0, s)
            e = min(len(text), e)
            for i in range(s, e):
                if p >= prio[i]:
                    prio[i] = p
                    styles[i] = sty

        self.startStyling(start)
        i = 0
        while i < len(text):
            cur = styles[i]
            j = i + 1
            while j < len(text) and styles[j] == cur:
                j += 1
            self.setStyling(j - i, cur)
            i = j

    def build_apis(self):
        self.apis.clear()
        code = self.editor.text()
        line, col = self.editor.getCursorPosition()
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )

        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return

        try:
            script = jedi.Script(code=code)
            completions = script.complete(line + 1, col)
            for completion in completions:
                self.apis.add(completion.name)
        except Exception:
            pass

        self.apis.prepare()


class PygmentsBaseLexer(BaseLexer):
    def __init__(self, language_name, editor, theme_name="default"):
        super().__init__(language_name, editor, theme_name=theme_name)
        self.pygments_lexer = None
        self.token_map = {}

    def styleText(self, start: int, end: int):
        if not self.pygments_lexer or not self.token_map:
            return

        self.startStyling(start)
        text = self.editor.text()[start:end]

        tokens = lex(text, self.pygments_lexer)

        current_pos = 0
        for ttype, value in tokens:
            token_len = len(value.encode("utf-8"))

            if current_pos >= start:
                style_id = self._get_style_from_token(ttype)
                self.setStyling(token_len, style_id)

            current_pos += token_len
            if current_pos >= end:
                break

    def _get_style_from_token(self, ttype):
        while ttype in self.token_map:
            return self.token_map[ttype]
        if ttype.parent:
            return self._get_style_from_token(ttype.parent)
        return self.DEFAULT


# all_keywords = keyword.kwlist.copy()
# if hasattr(keyword, "softkwlist"):
#     all_keywords.extend(keyword.softkwlist)

# KEYWORD_PATTERN = "|".join(map(re.escape, all_keywords))


# class CustomPyG_PythonLexer(PyG_PythonLexer):
#     tokens = {
#         "root": [
#             (
#                 rf"\b(?!(?:{KEYWORD_PATTERN})\b)([A-Za-z_]\w*)(\s*)(\()",
#                 bygroups(Name.Function.Call, Text, Punctuation),
#             ),
#             inherit,
#         ]
#     }


# It is no longer in use because it is too slow
# If you want a complete experience, you can modify the code yourself to use this lexer,
# but be aware that it may cause performance issues in large files (>1000 lines)
# class PythonLexer(PygmentsBaseLexer):
#     def __init__(self, editor, theme_name="default"):
#         super().__init__("Python", editor, theme_name=theme_name)

#         self.pygments_lexer = CustomPyG_PythonLexer()

#         self.token_map = {
#             Token.Text: self.DEFAULT,
#             Token.Whitespace: self.DEFAULT,
#             Punctuation: self.DEFAULT,
#             Operator: self.DEFAULT,
#             Comment: self.COMMENTS,
#             Comment.Hashbang: self.COMMENTS,
#             Comment.Single: self.COMMENTS,
#             Comment.Multiline: self.COMMENTS,
#             String.Doc: self.STRING,
#             Keyword: self.KEYWORD,
#             Keyword.ControlFlow: self.KEYWORD,
#             Keyword.Declaration: self.KEYWORD,
#             Keyword.Namespace: self.KEYWORD,
#             Keyword.Pseudo: self.KEYWORD,
#             Keyword.Reserved: self.KEYWORD,
#             Keyword.Operator: self.KEYWORD,
#             Keyword.Type: self.TYPES,
#             Name.Class: self.CLASSES,
#             Name.Exception: self.CLASSES,
#             Name.Builtin.Pseudo: self.KEYWORD,
#             Name.Function: self.FUNCTION_DEF,
#             Name.Builtin: self.FUNCTIONS,
#             Name.Decorator: self.FUNCTIONS,
#             Name.Function.Call: self.FUNCTIONS,
#             Number: self.CONSTANTS,
#             Number.Bin: self.CONSTANTS,
#             Number.Float: self.CONSTANTS,
#             Number.Hex: self.CONSTANTS,
#             Number.Integer: self.CONSTANTS,
#             Number.Integer.Long: self.CONSTANTS,
#             Number.Oct: self.CONSTANTS,
#             Keyword.Constant: self.CONSTANTS,
#             Name.Constant: self.CONSTANTS,
#             String: self.STRING,
#             String.Affix: self.KEYWORD,
#             String.Backtick: self.STRING,
#             String.Char: self.STRING,
#             String.Delimiter: self.STRING,
#             String.Double: self.STRING,
#             String.Escape: self.CONSTANTS,
#             String.Heredoc: self.STRING,
#             String.Interpol: self.DEFAULT,
#             String.Other: self.STRING,
#             String.Regex: self.STRING,
#             String.Single: self.STRING,
#             Name.Variable: self.DEFAULT,
#             Name.Variable.Class: self.DEFAULT,
#             Name.Variable.Global: self.DEFAULT,
#             Name.Variable.Instance: self.DEFAULT,
#             Name.Variable.Magic: self.DEFAULT,
#             Name.Attribute: self.DEFAULT,
#             Name.Label: self.DEFAULT,
#             Name.Tag: self.KEYWORD,
#         }

#     def build_apis(self):
#         self.apis.clear()

#         code = self.editor.text()
#         line, col = self.editor.getCursorPosition()
#         pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
#         style = (
#             self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
#             if pos > 0
#             else -1
#         )

#         if style in (self.STRING, self.COMMENTS):
#             self.apis.prepare()
#             return

#         try:
#             script = jedi.Script(code=code)
#             completions = script.complete(line + 1, col)
#             for completion in completions:
#                 self.apis.add(completion.name)
#         except Exception:
#             pass

#         self.apis.prepare()


class JsonLexer(PygmentsBaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("JSON", editor, theme_name=theme_name)

        self.pygments_lexer = PyG_JsonLexer()

        self.token_map = {
            Token.Text: self.DEFAULT,
            String: self.STRING,
            Number: self.CONSTANTS,
            Keyword: self.TYPES,
            Keyword.Constant: self.TYPES,
            Punctuation: self.DEFAULT,
            Name.Tag: self.CLASS_DEF,
        }

    def build_apis(self):
        self.apis.clear()
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )

        if style not in (self.STRING,):
            self.apis.add("true")
            self.apis.add("false")
            self.apis.add("null")

        self.apis.prepare()


class MarkdownLexer(PygmentsBaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Markdown", editor, theme_name=theme_name)

        self.pygments_lexer = PyG_MarkdownLexer()

        self.token_map = {
            Token.Text: self.DEFAULT,
            Generic.Heading: self.CLASS_DEF,
            Generic.Subheading: self.CLASS_DEF,
            Generic.Strong: self.FUNCTIONS,
            Generic.Emph: self.TYPES,
            String.Backtick: self.STRING,
            Literal.String.Backtick: self.STRING,
            Comment.Preproc: self.STRING,
            Keyword: self.DEFAULT,
            Generic.Prompt: self.COMMENTS,
            Generic.Traceback: self.CONSTANTS,
            Name.Tag: self.FUNCTIONS,
            Name.Attribute: self.CONSTANTS,
        }

    def build_apis(self):
        self.apis.clear()
        self.apis.prepare()


class PlainTextLexer(BaseLexer):
    def __init__(self, editor, theme_name="default"):
        super().__init__("Plain Text", editor, theme_name=theme_name)

    def styleText(self, start: int, end: int):
        if start >= end:
            return

    def build_apis(self):
        self.apis.clear()
        self.apis.prepare()
