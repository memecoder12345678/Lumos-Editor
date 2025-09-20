### **`README.md` (Phiên bản cuối cùng)**

# Lumos Editor

A modern, extensible code editor built with PyQt5 on Windows, featuring syntax highlighting, file tree navigation, Markdown preview, and a flexible plugin system.

## Features

- Clean, modern dark theme UI
- File tree navigation and management
- Syntax highlighting for Python and JSON
- Integrated terminal support
- Markdown preview with code block syntax highlighting 
- Multi-tab editing
- Image viewer support for common formats
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

1.  `manifest.json`
2.  `lexer.py`
3.  An icon file (e.g., `icon.png`)

#### 1. `manifest.json`

This file contains metadata about your plugin.

**Example for a JavaScript plugin:**
```json
{
  "languageName": "JavaScript",
  "pluginVersion": "1.0.0",
  "author": "Your Name",
  "fileExtensions": [".js", ".mjs"],
  "iconFile": "js-icon.png",
  "lexerFile": "lexer.py",
  "lexerClass": "JavaScriptLexer",
  "autocompleteFile": "completer.py",
  "autocompleteClass": "JavaScriptCompleter"
}
```
- **`fileExtensions`**: An array of file extensions this plugin applies to.
- **`lexerClass`**: The name of your custom lexer class inside `lexer.py`.

#### 2. `lexer.py`

This file contains the core logic for syntax highlighting. You must create a class that inherits from `src.lexer.BaseLexer`.

**Basic `lexer.py` template:**
```python
import re
from src.lexer import BaseLexer # BaseLexer is provided by the editor at runtime

class YourLexerClassName(BaseLexer):
    def __init__(self, editor):
        # Call the parent constructor with your language name
        super().__init__("Your Language Name", editor)
        
        # Define keywords for your language
        self.setKeywords(['keyword1', 'keyword2', 'if', 'else'])

    def styleText(self, start, end):
        """This method is called by the editor to apply styles."""
        self.startStyling(start)
        text = self.editor.text()[start:end]
        
        # --- YOUR TOKENIZING AND STYLING LOGIC GOES HERE ---
        # Example:
        # for token, length in self.tokenize(text):
        #     if token in self.keywords_list:
        #         self.setStyling(length, self.KEYWORD)
        #     else:
        #         self.setStyling(length, self.DEFAULT)
```

**For a more advanced and detailed example, you can see the implementation of the built-in `PythonLexer` in `src/lexer.py`.**

#### 3. Packaging the Plugin

Once you have your three files (`manifest.json`, `lexer.py`, `icon.png`), select all of them, right-click, and compress them into a `.zip` file. **Important:** Do not zip the parent folder, only the files themselves.

Rename the final `.zip` file to have a `.lumosplugin` extension (e.g., `javascript.lumosplugin`). That's it!

## Keyboard Shortcuts

-   **Ctrl+N** - New file
-   **Ctrl+O** - Open file
-   **Ctrl+S** - Save file
-   **Ctrl+Shift+S** - Save file as
-   **Ctrl+B** - Toggle file tree
-   **Ctrl+Shift+E** - Show explorer
-   **Ctrl+K** - Open folder
-   **Ctrl+Shift+K** - Close folder
-   **Ctrl+P** - Toggle Markdown preview
-   **Ctrl+Shift+`** - Open terminal
-   **Ctrl+Q** - Exit

## Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## Credits

-   Original idea from: [https://github.com/Fus3n/pyqt-code-editor-yt](https://github.com/Fus3n/pyqt-code-editor-yt)
-   Additional inspiration from VSCode's UI/UX

## License

[MIT](https://choosealicense.com/licenses/mit/)
