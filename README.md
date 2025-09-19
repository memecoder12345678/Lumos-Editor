# Lumos Editor

A modern code editor built with PyQt5 on Windows, featuring syntax highlighting, file tree navigation, and Markdown preview support.

## Features

- Clean, modern dark theme UI
- File tree navigation and management
- Syntax highlighting for Python and JSON
- Integrated terminal support
- Markdown preview with code block syntax highlighting 
- Multi-tab editing
- Image viewer support for common formats
- File operations (copy, cut, paste, rename, delete)
- Auto-completion for Python using Jedi
- Line numbering and bracket matching
- Customizable themes

## Requirements

```txt
PyQtWebEngine==5.15.7
PyQt5==5.15.11
QScintilla==2.14.1
mistune==3.1.3
jedi==0.19.2
```

## Installation

1. Clone this repository:
```sh 
git clone https://github.com/memecoder12345678/lumos-editor.git
cd lumos-editor
```

2. Install dependencies:
```sh
pip install -r requirements.txt
```

3. Run the editor:
```sh
python lumos_editor.py
```

## Keyboard Shortcuts

- **Ctrl+N** - New file
- **Ctrl+O** - Open file
- **Ctrl+S** - Save file
- **Ctrl+Shift+S** - Save file as
- **Ctrl+B** - Toggle file tree
- **Ctrl+Shift+E** - Show explorer
- **Ctrl+K** - Open folder
- **Ctrl+Shift+K** - Close folder
- **Ctrl+P** - Toggle Markdown preview
- **Ctrl+Shift+`** - Open terminal
- **Ctrl+Q** - Exit

# Contributing

Pull requests are welcome! For major changes, please open an issue first to discuss what you would like to change.

## Credits

- Original idea from: [https://github.com/Fus3n/pyqt-code-editor-yt](https://github.com/Fus3n/pyqt-code-editor-yt)
- Additional inspiration from VSCode's UI/UX

## License

[MIT](https://choosealicense.com/licenses/mit/)
