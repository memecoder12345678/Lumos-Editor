# Cần giả định rằng BaseLexer có thể được import từ môi trường của plugin.
# Trong thực tế, PluginManager của bạn sẽ xử lý việc này.
from src.lexer import BaseLexer
from PyQt5.Qsci import QsciAPIs

class AquaLexer(BaseLexer):
    def __init__(self, editor):
        super(AquaLexer, self).__init__("AquaScript", editor)

        self.keywords_list = ['let', 'func', 'return', 'if', 'else', 'for', 'while']
        self.builtin_names = ['print', 'string', 'number', 'boolean', 'true', 'false', 'null']
        
        self.setKeywords(self.keywords_list)
        
    def styleText(self, start, end):
        self.startStyling(start)
        text = self.editor.text()[start:end]

        self.generate_tokens(text) # Tách văn bản thành các token

        string_mode = False
        comment_mode = False

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
            if comment_mode:
                self.setStyling(tok_len, self.COMMENTS)
                if "\n" in tok_str:
                    comment_mode = False
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

            tok_str: str = curr_token_data[0]
            tok_len: int = curr_token_data[1]

            if tok_str == "//":
                self.setStyling(tok_len, self.COMMENTS)
                comment_mode = True
            elif tok_str == '"':
                self.setStyling(tok_len, self.STRING)
                string_mode = True
            elif tok_str in self.keywords_list:
                self.setStyling(tok_len, self.KEYWORD)
            elif tok_str in self.builtin_names:
                self.setStyling(tok_len, self.TYPES)
            elif tok_str.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok_str in "()[]{}":
                self.setStyling(tok_len, self.BRACKETS)
            else:
                self.setStyling(tok_len, self.DEFAULT)

    def build_apis(self):
        # Cung cấp gợi ý auto-complete đơn giản
        self.apis.clear()
        for kw in self.keywords_list:
            self.apis.add(kw)
        for bn in self.builtin_names:
            self.apis.add(bn)
        self.apis.prepare()