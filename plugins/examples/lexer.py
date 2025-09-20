from src.lexer import BaseLexer
from PyQt5.Qsci import QsciAPIs


class JavaScriptLexer(BaseLexer):
    def __init__(self, editor):
        super(JavaScriptLexer, self).__init__("JavaScript", editor)
        self.apis = QsciAPIs(self)

        self.setKeywords(
            [
                "break", "case", "catch", "class", "const", "continue",
                "debugger", "default", "delete", "do", "else", "export",
                "extends", "finally", "for", "function", "if", "import",
                "in", "instanceof", "let", "new", "return", "super",
                "switch", "this", "throw", "try", "typeof", "var",
                "void", "while", "with", "yield", "async", "await",
            ]
        )

        self.setBuiltinNames(["true", "false", "null", "undefined", "NaN", "Infinity"])

    def styleText(self, start, end):
        self.startStyling(start)
        text = self.editor.text()[start:end]

        self.generate_tokens(text)

        previous_style = (
            self.editor.SendScintilla(self.editor.SCI_GETSTYLEAT, start - 1)
            if start > 0
            else self.DEFAULT
        )
        in_multiline_comment = previous_style == self.COMMENTS
        in_single_line_comment = False
        in_string = False
        string_char = ""

        while len(self.token_list) > 0:
            if in_single_line_comment:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                self.setStyling(curr_token[1], self.COMMENTS)
                if "\n" in curr_token[0]:
                    in_single_line_comment = False
                continue

            if in_multiline_comment:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                self.setStyling(curr_token[1], self.COMMENTS)
                if curr_token[0] == "*/":
                    in_multiline_comment = False
                continue

            if in_string:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                if curr_token[0] == "\\":
                    self.setStyling(curr_token[1], self.STRING)
                    next_char = self.next_tok()
                    if next_char:
                        self.setStyling(next_char[1], self.STRING)
                elif curr_token[0] == string_char:
                    self.setStyling(curr_token[1], self.STRING)
                    in_string = False
                else:
                    self.setStyling(curr_token[1], self.STRING)
                continue

            tok1_peek = self.peek_tok(0)
            tok2_peek = self.peek_tok(1)
            if tok1_peek and tok1_peek[0] == "/" and tok2_peek and tok2_peek[0] == "/":
                tok1 = self.next_tok()
                self.setStyling(tok1[1], self.COMMENTS)
                tok2 = self.next_tok()
                self.setStyling(tok2[1], self.COMMENTS)
                in_single_line_comment = True
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
                self.setStyling(self.next_tok()[1], self.CONSTANTS)
                self.setStyling(self.next_tok()[1], self.CONSTANTS)
                self.setStyling(self.next_tok()[1], self.CONSTANTS)
                continue

            if not self.peek_tok(0) or not self.peek_tok(0)[0]:
                break

            curr_token_data = self.next_tok()
            if curr_token_data is None:
                break
            tok: str = curr_token_data[0]
            tok_len: int = curr_token_data[1]

            if tok == "/*":
                self.setStyling(tok_len, self.COMMENTS)
                in_multiline_comment = True
            elif tok in ('"', "'", "`"):
                self.setStyling(tok_len, self.STRING)
                in_string = True
                string_char = tok
            elif tok in self.keywords_list:
                self.setStyling(tok_len, self.KEYWORD)
            elif tok in self.builtin_names:
                self.setStyling(tok_len, self.TYPES)
            elif tok.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok in "()[]{}":
                self.setStyling(tok_len, self.BRACKETS)
            else:
                self.setStyling(tok_len, self.DEFAULT)

    def build_apis(self):
        self.apis.clear()

        editor = self.editor
        pos = editor.SendScintilla(editor.SCI_GETCURRENTPOS)
        style = editor.SendScintilla(editor.SCI_GETSTYLEAT, pos - 1) if pos > 0 else -1

        if style in (self.STRING, self.COMMENTS):
            self.apis.prepare()
            return

        for keyword in self.keywords_list:
            self.apis.add(keyword)
        for built_in in self.builtin_names:
            self.apis.add(built_in)

        self.apis.prepare()
