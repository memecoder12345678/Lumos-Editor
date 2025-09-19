import jedi
from PyQt5.Qsci import QsciAPIs
from .lexer import PythonLexer, JsonLexer


def build_autocomplete(lexer: PythonLexer | JsonLexer) -> QsciAPIs:
    apis = QsciAPIs(lexer)
    apis.clear()

    editor = lexer.editor
    code = editor.text()
    line, col = editor.getCursorPosition()
    pos = editor.SendScintilla(editor.SCI_GETCURRENTPOS)
    style = editor.SendScintilla(editor.SCI_GETSTYLEAT, pos - 1) if pos > 0 else -1

    if style in (lexer.STRING, lexer.COMMENTS):
        apis.prepare()
        return apis
    if isinstance(lexer, PythonLexer):
        script = jedi.Script(code=code)
        completions = script.complete(line + 1, col)

        for completion in completions:
            apis.add(completion.name)
    elif isinstance(lexer, JsonLexer):
        apis.add("true")
        apis.add("false")
        apis.add("null")

    apis.prepare()
    return apis
