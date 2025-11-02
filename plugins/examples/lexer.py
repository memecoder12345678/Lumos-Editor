from src.lexer import BaseLexer


class LumosLexer(BaseLexer):
    def __init__(self, editor):
        super(LumosLexer, self).__init__("LumosScript", editor)

        self.keywords_list = ["set", "func", "return", "if", "else", "for", "while"]
        self.builtin_names = ["true", "false", "null"]

        self.setKeywords(self.keywords_list)

    def styleText(self, start, end):
        self.startStyling(start)
        text = self.editor.text()[start:end]
        self.generate_tokens(text)

        string_mode = False
        comment_mode = False
        is_escape_char = False

        while len(self.token_list) > 0:

            if comment_mode:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                self.setStyling(curr_token[1], self.COMMENTS)
                if "\n" in curr_token[0]:
                    comment_mode = False
                continue

            if string_mode:
                curr_token = self.next_tok()
                if curr_token is None:
                    break
                tok_str, tok_len = curr_token

                self.setStyling(tok_len, self.STRING)

                if is_escape_char:
                    is_escape_char = False
                elif tok_str == "\\":
                    is_escape_char = True
                elif tok_str == '"':
                    string_mode = False
                continue

            tok_num1_peek, tok_dot_peek, tok_num2_peek = (
                self.peek_tok(0),
                self.peek_tok(1),
                self.peek_tok(2),
            )
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

            curr_token_data = self.next_tok()
            if curr_token_data is None:
                break
            tok_str, tok_len = curr_token_data

            if tok_str == "/":
                next_tok = self.peek_tok(0)
                if next_tok and next_tok[0] == "/":
                    self.setStyling(tok_len, self.COMMENTS)
                    comment_mode = True
                else:
                    self.setStyling(tok_len, self.DEFAULT)
            elif tok_str == '"':
                self.setStyling(tok_len, self.STRING)
                string_mode = True
                is_escape_char = False

            elif tok_str == "func":
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

            elif tok_str in self.keywords_list:
                self.setStyling(tok_len, self.KEYWORD)
            elif tok_str in self.builtin_names:
                self.setStyling(tok_len, self.TYPES)

            elif tok_str.isidentifier():
                if self.peek_tok(0)[0] == "(":
                    self.setStyling(tok_len, self.FUNCTIONS)
                else:
                    self.setStyling(tok_len, self.DEFAULT)

            elif tok_str.isnumeric():
                self.setStyling(tok_len, self.CONSTANTS)
            elif tok_str in "()[]{}":
                self.setStyling(tok_len, self.BRACKETS)
            else:
                self.setStyling(tok_len, self.DEFAULT)

    def build_apis(self):
        self.apis.clear()
        for kw in self.keywords_list:
            self.apis.add(kw)
        for bn in self.builtin_names:
            self.apis.add(bn)
        self.apis.prepare()
