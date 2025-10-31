# Lumos Editor

A modern, extensible code editor built with PyQt5 on Windows, featuring syntax highlighting, file tree navigation, Markdown preview, and a flexible plugin system.

## Features

- Clean, modern dark theme UI
- Source Control for easy code management and sync
- AI Chat for instant coding help
- File tree navigation and management
- Syntax highlighting for Python and JSON
- Integrated terminal support
- Markdown preview with code block syntax highlighting 
- Multi-tab editing
- Media viewer support for common formats
- File operations (copy, cut, paste, rename, delete)
- Easily add support for new languages with a simple plugin structure.

## Installation

1.  **Clone this repository:**
```sh
git clone https://github.com/memecoder12345678/lumos-editor.git
cd lumos-editor
```

2.  **Install dependencies:**
```sh
pip install -r requirements.txt
```

3.  **(Optional) Install Plugins:**
    - Create a `plugins` folder in the root directory.
    - Download `.lumosplugin` files and place them inside the `plugins` folder.

4.  **Run the editor:**
```sh
python lumos_editor.py
```

## Plugin System

Lumos Editor supports plugins to add syntax highlighting and custom icons for new languages. You can enable, disable, or manage your installed plugins via the `Plugins` menu.

### Creating a Syntax Highlighting Plugin

Creating a plugin is straightforward. All you need is a `.zip` file with a `.lumosplugin` extension containing three essential files:

1. `manifest.json`
2. `lexer.py`
3. An icon file (e.g., `icon.ico`)

#### 1. `manifest.json`

This file contains metadata about your plugin.

**Example for a JavaScript plugin:**
```json
{
    "languageName": "JavaScript",
    "fileExtensions": [".js", ".mjs"],
    "iconFile": "js-icon.ico",
    "lexerFile": "lexer.py",
    "lexerClass": "JavaScriptLexer"
}
```
- **`fileExtensions`**: An array of file extensions this plugin applies to.
- **`lexerClass`**: The name of your custom lexer class inside `lexer.py`.

#### 2. `lexer.py`

This file contains the core logic for syntax highlighting. You must create a class that inherits from `src.lexer.BaseLexer`.

**Basic `lexer.py` template:**
```python
from src.lexer import BaseLexer
from PyQt5.Qsci import QsciAPIs


class JavaScriptLexer(BaseLexer):
    def __init__(self, editor):
        super(JavaScriptLexer, self).__init__("JavaScript", editor)
        self.apis = QsciAPIs(self)

        self.setKeywords(
            [
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
                "let",
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
                "async",
                "await",
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

```

**For a more advanced and detailed example, you can see the implementation of the built-in `PythonLexer` in `src/lexer.py`.**

#### 3. Packaging the Plugin

Once you have your three files (`manifest.json`, `lexer.py`, `icon.ico`), select all of them, right-click, and compress them into a `.zip` file. **Important:** Do not zip the parent folder, only the files themselves.

Rename the final `.zip` file to have a `.lumosplugin` extension (e.g., `javascript.lumosplugin`). That's it!


## Keyboard Shortcuts

### File

* **Ctrl+N** – New file
* **Ctrl+O** – Open file
* **Ctrl+K** – Open folder
* **Ctrl+Shift+K** – Close folder
* **Ctrl+S** – Save file
* **Ctrl+Shift+S** – Save file as
* **Ctrl+Q** – Exit

### Edit

* **Ctrl+Z** – Undo
* **Ctrl+Y** – Redo
* **Ctrl+X** – Cut
* **Ctrl+C** – Copy
* **Ctrl+V** – Paste
* **Ctrl+A** – Select all
* **Ctrl+F** – Find
* **Ctrl+H** – Replace
* **Ctrl+W** – Toggle wrap mode

### View

* **Ctrl+B** – Toggle explorer panel
* **Ctrl+P** – Toggle Markdown preview

### Terminal

* **Ctrl+Shift+`** – Open terminal

### AI Chat

* **Ctrl+Shift+A** – Open AI Chat

### Source Control

* **Ctrl+Shift+G** – Open Source Control

### Plugins

* *Ctrl+Shift+B* – Enable/disable plugins
* *Ctrl+Shift+M* – Manage individual plugins




## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## Credits

- Original idea from: [https://github.com/Fus3n/pyqt-code-editor-yt](https://github.com/Fus3n/pyqt-code-editor-yt)
- Additional inspiration from VSCode's UI/UX

## License

[MIT](https://choosealicense.com/licenses/mit/)

