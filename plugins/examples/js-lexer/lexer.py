import re

from pygments.lexer import bygroups, inherit
from pygments.lexers.javascript import JavascriptLexer as PyG_JavascriptLexer
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    Text,
    Token,
)

js_keywords = [
    "break",
    "case",
    "catch",
    "class",
    "const",
    "continue",
    "debugger",
    "default",
    "delete",
    "do",
    "else",
    "export",
    "extends",
    "finally",
    "for",
    "function",
    "if",
    "import",
    "in",
    "instanceof",
    "new",
    "return",
    "super",
    "switch",
    "this",
    "throw",
    "try",
    "typeof",
    "var",
    "void",
    "while",
    "with",
    "yield",
    "let",
    "static",
    "enum",
    "await",
    "async",
    "true",
    "false",
    "null",
    "undefined",
    "console",
    "log",
    "window",
    "document",
    "JSON",
    "Math",
    "Object",
    "Array",
    "String",
    "Number",
    "Boolean",
    "Symbol",
    "Set",
    "Map",
    "WeakSet",
    "WeakMap",
    "Date",
    "RegExp",
    "Promise",
    "Error",
    "EvalError",
    "RangeError",
    "ReferenceError",
    "SyntaxError",
    "TypeError",
    "URIError",
]

JS_KEYWORD_PATTERN = "|".join(map(re.escape, js_keywords))


class CustomPyG_JavascriptLexer(PyG_JavascriptLexer):
    tokens = {
        "root": [
            (
                rf"\b(?!(?:{JS_KEYWORD_PATTERN})\b)([A-Za-z_]\w*)(\s*)(\()",
                bygroups(Name.Function.Call, Text, Punctuation),
            ),
            inherit,
        ]
    }


class JavascriptLexer(lumos.PygmentsBaseLexer):  # type: ignore
    def __init__(self, editor, theme_name="default"):
        super().__init__("JavaScript", editor, theme_name=theme_name)

        self.pygments_lexer = CustomPyG_JavascriptLexer()

        self.token_map = {
            Token.Text: self.DEFAULT,
            Token.Other: self.DEFAULT,
            Keyword: self.KEYWORD,
            Keyword.Reserved: self.KEYWORD,
            Keyword.Declaration: self.KEYWORD,
            Keyword.Constant: self.TYPES,
            Name.Function: self.FUNCTION_DEF,
            Name.Class: self.CLASS_DEF,
            Name.Builtin: self.FUNCTIONS,
            Name.Builtin.Pseudo: self.TYPES,
            Name.Variable: self.DEFAULT,
            Name.Constant: self.CONSTANTS,
            Name.Decorator: self.FUNCTIONS,
            Name.Other: self.DEFAULT,
            Name.Attribute: self.DEFAULT,
            String: self.STRING,
            String.Double: self.STRING,
            String.Single: self.STRING,
            String.Backtick: self.STRING,
            String.Regex: self.CONSTANTS,
            Number: self.CONSTANTS,
            Operator: self.DEFAULT,
            Punctuation: self.DEFAULT,
            Comment: self.COMMENTS,
            Comment.Single: self.COMMENTS,
            Comment.Multiline: self.COMMENTS,
            Comment.Special: self.COMMENTS,
        }

    def build_apis(self):
        """
        You can use tree-sitter to build a more accurate API list,
        but this is a simple example using keywords and built-in functions
        """
        self.apis.clear()
        pos = self.editor.SendScintilla(self.editor.SCI_GETCURRENTPOS)
        style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, pos - 1)
            if pos > 0
            else -1
        )

        if style not in (self.STRING, self.COMMENTS):
            for kw in js_keywords:
                self.apis.add(kw)

        self.apis.prepare()
