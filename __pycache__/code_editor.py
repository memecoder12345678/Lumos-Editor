import customtkinter as ctk
import tkinter as tk
from tkinter import ttk
import re, keyword, sys, os, difflib

FONT_FAMILY = 'Consolas' if sys.platform.startswith('win') else 'Courier'
FONT_SIZE = 12
TAB_SPACES = ' ' * 4
DEFAULT_THEME = {'background': '#1E2127', 'foreground': '#DCDCDC', 'gutter_bg': '#21232A', 'gutter_fg': '#6B7080', 'current_line': '#2E3238', 'selection': '#3E4450', 'keyword': '#FFC66D', 'builtin': '#C794EA', 'string': '#98C379', 'number': '#D19A66', 'comment': '#5C6370', 'function': '#56B6C2', 'operator': '#FFFFFF',}
PY_KEYWORDS = set(keyword.kwlist)
PY_BUILTINS = set(['print', 'len', 'list', 'dict', 'set', 'tuple', 'str', 'int', 'float', 'bool', 'True', 'False', 'None', 'self', 'super', 'range', 'open', 'enumerate'])
import re
import builtins, types
from typing import Optional
RE_TRIPLE = re.compile('(?s)("{3}|\\\'{3})')
RE_IDENTIFIER = re.compile('[A-Za-z_][A-Za-z0-9_]*')
RE_NUMBER = re.compile('\\d+(\\.\\d+)?')
RE_COMMENT_LINE = re.compile('#.*')
RE_STRING_SIMPLE = re.compile('(?s)"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"|\\\'[^\\\'\\\\]*(?:\\\\.[^\\\'\\\\]*)*\\\'')
PY_KEYWORDS = set(__import__('keyword').kwlist)


class TkPythonLexer:
    RECHECK_MS = 400

    def __init__(self, editor, theme_name='default'):
        self.editor = editor
        self.textwidget = editor.text
        self.theme = getattr(editor, 'theme', {})
        self.theme_name = theme_name
        self.class_names = set()
        self.user_functions = set()
        self.builtin_functions = set((name for name, obj in vars(builtins).items() if isinstance(obj, types.BuiltinFunctionType)))
        self.builtin_classes = set((name for name, obj in vars(builtins).items() if isinstance(obj, type)))
        self.in_string_mode = False
        self.string_quote_char = None
        self.is_triple_string = False
        self.is_escape_sequence_char = False
        self.current_lexer_pos = 0
        self.token_list = []
        self._tok_index = 0
        self._after_id = None
        self._ensure_tags()
        try:
            self.textwidget.bind('<KeyRelease>', lambda e: self.trigger_recheck(), add='+')
            self.textwidget.bind('<<Paste>>', lambda e: self.trigger_recheck(), add='+')
        except Exception:
            pass

    def _ensure_tags(self):
        t = self.textwidget
        theme = self.theme or {}

        def cfg(name, **kwargs):
            try:
                t.tag_configure(name, **kwargs)
            except Exception:
                pass
        cfg('keyword', foreground=theme.get('keyword', '#FFC66D'))
        cfg('builtin', foreground=theme.get('builtin', '#C794EA'))
        cfg('string', foreground=theme.get('string', '#98C379'))
        cfg('number', foreground=theme.get('number', '#D19A66'))
        cfg('comment', foreground=theme.get('comment', '#5C6370'))
        cfg('function', foreground=theme.get('function', '#56B6C2'))
        cfg('class', foreground=theme.get('function', '#56B6C2'))
        cfg('operator', foreground=theme.get('operator', '#FFFFFF'))
        cfg('constant', foreground=theme.get('number', '#D19A66'))
        cfg('bracket', background='#3B4252')

    def trigger_recheck(self):
        """Schedule perform_name_check after RECHECK_MS (debounced)."""
        if self._after_id:
            try:
                self.textwidget.after_cancel(self._after_id)
            except Exception:
                pass
        self._after_id = self.textwidget.after(self.RECHECK_MS, self.perform_name_check)

    def perform_name_check(self):
        """Parse the whole buffer (fast regex strip) and update class/function sets."""
        self._after_id = None
        try:
            full = self.textwidget.get('1.0', 'end-1c')
        except Exception:
            full = ''
        processed = re.sub('(?s)("{3}.*?"{3}|\\\'{3}.*?\\\'{3})', '', full)
        processed = re.sub('(?s)"[^"\\\\]*(?:\\\\.[^"\\\\]*)*"|\\\'[^\\\'\\\\]*(?:\\\\.[^\\\'\\\\]*)*\\\'', '', processed)
        processed = re.sub('(?m)#.*$', '', processed)
        classes = set(re.findall('\\bclass\\s+([A-Za-z_][A-Za-z0-9_]*)', processed))
        funcs = set(re.findall('\\bdef\\s+([A-Za-z_][A-Za-z0-9_]*)', processed))
        changed = False
        if classes != self.class_names:
            self.class_names = classes
            changed = True
        if funcs != self.user_functions:
            self.user_functions = funcs
            changed = True
        if changed:
            try:
                self.editor._schedule_highlight(10)
            except Exception:
                try:
                    self.editor._highlight_all()
                except Exception:
                    pass

    def set_current_file(self, filepath: Optional[str]):
        """Reset known names when switching file (or check content)."""
        if filepath is None:
            self.class_names.clear()
            self.user_functions.clear()
        else:
            self.perform_name_check()

    def _update_state_up_to(self, scan_to_pos: int):
        """
        Ensure the lexer state is valid up to absolute char position `scan_to_pos`.
        For simplicity: if scan_to_pos < current_lexer_pos => reset state.
        Otherwise scan from current_lexer_pos to scan_to_pos updating string state only.
        """
        if scan_to_pos <= 0:
            self.in_string_mode = False
            self.string_quote_char = None
            self.is_triple_string = False
            self.is_escape_sequence_char = False
            self.current_lexer_pos = 0
            return
        if getattr(self, 'current_lexer_pos', 0) > scan_to_pos:
            self.in_string_mode = False
            self.string_quote_char = None
            self.is_triple_string = False
            self.is_escape_sequence_char = False
            self.current_lexer_pos = 0
        try:
            full = self.textwidget.get('1.0', 'end-1c')
        except Exception:
            full = ''
        start = self.current_lexer_pos
        fragment = full[start:scan_to_pos]
        i = 0
        L = len(fragment)
        while i < L:
            ch = fragment[i]
            if self.in_string_mode:
                if ch == '\\':
                    i += 2
                    continue
                if self.is_triple_string:
                    if fragment.startswith(self.string_quote_char * 3, i):
                        self.in_string_mode = False
                        self.is_triple_string = False
                        i += 3
                        continue
                    else:
                        i += 1
                        continue
                else:
                    if ch == self.string_quote_char:
                        self.in_string_mode = False
                        self.string_quote_char = None
                    i += 1
                    continue
            else:
                if fragment.startswith('"""', i) or fragment.startswith("'''", i):
                    self.in_string_mode = True
                    self.is_triple_string = True
                    self.string_quote_char = fragment[i]
                    i += 3
                    continue
                if ch == '"' or ch == "'":
                    self.in_string_mode = True
                    self.is_triple_string = False
                    self.string_quote_char = ch
                    i += 1
                    continue
                if ch == '#':
                    nl = fragment.find('\n', i)
                    if nl == -1:
                        break
                    else:
                        i = nl + 1
                        continue
                i += 1
        self.current_lexer_pos = scan_to_pos

    def generate_tokens(self, text_segment: str):
        """Fill self.token_list as [(tok_str, tok_len), ...] scanning text_segment from 0..len."""
        self.token_list = []
        i = 0
        L = len(text_segment)
        while i < L:
            ch = text_segment[i]
            if ch.isspace():
                j = i + 1
                while j < L and text_segment[j].isspace() and (text_segment[j] != '\n'):
                    j += 1
                self.token_list.append((text_segment[i:j], j - i))
                i = j
                continue
            if ch == '#':
                j = i
                while j < L and text_segment[j] != '\n':
                    j += 1
                self.token_list.append((text_segment[i:j], j - i))
                continue
            if text_segment.startswith('"""', i) or text_segment.startswith("'''", i):
                quote = text_segment[i]
                closing = text_segment.find(quote * 3, i + 3)
                if closing == -1:
                    self.token_list.append((text_segment[i:], L - i))
                    break
                else:
                    endpos = closing + 3
                    self.token_list.append((text_segment[i:endpos], endpos - i))
                    i = endpos
                    continue
            if ch == '"' or ch == "'":
                quote = ch
                j = i + 1
                escaped = False
                while j < L:
                    c2 = text_segment[j]
                    if escaped:
                        escaped = False
                        j += 1
                        continue
                    if c2 == '\\':
                        escaped = True
                        j += 1
                        continue
                    if c2 == quote:
                        j += 1
                        break
                    j += 1
                self.token_list.append((text_segment[i:j], j - i))
                i = j
                continue
            m = RE_NUMBER.match(text_segment, i)
            if m:
                s = m.group(0)
                self.token_list.append((s, len(s)))
                i += len(s)
                continue
            m = RE_IDENTIFIER.match(text_segment, i)
            if m:
                s = m.group(0)
                self.token_list.append((s, len(s)))
                i += len(s)
                continue
            two = text_segment[i:i + 2]
            three = text_segment[i:i + 3]
            if three in ('<<=', '>>='):
                self.token_list.append((three, 3))
                i += 3
                continue
            if two in ('==', '!=', '<=', '>=', '//', '**', '+=', '-=', '*=', '/=', '%='):
                self.token_list.append((two, 2))
                i += 2
                continue
            self.token_list.append((ch, 1))
            i += 1
        self._tok_index = 0

    def next_tok(self):
        if self._tok_index >= len(self.token_list):
            return None
        t = self.token_list[self._tok_index]
        self._tok_index += 1
        return t

    def peek_tok(self, offset=0):
        idx = self._tok_index + offset
        if idx >= len(self.token_list):
            return ('', 0)
        return self.token_list[idx]

    def skip_spaces_peek(self, start_offset=0):
        """Return first non-space token and how many tokens we skipped (including spaces)"""
        idx = self._tok_index + start_offset
        skipped = 0
        while idx < len(self.token_list):
            tok, ln = self.token_list[idx]
            if tok.isspace():
                idx += 1
                skipped += 1
                continue
            return (tok, skipped)
        return ('', skipped)

    def style_text(self, abs_start: int, abs_end: int):
        """
        Style text in [abs_start, abs_end). abs_* are absolute character offsets from buffer start.
        Uses tags created in _ensure_tags() and EditorTab tag conventions.
        """
        if abs_start >= abs_end:
            return
        self._update_state_up_to(abs_start)
        try:
            full = self.textwidget.get('1.0', 'end-1c')
        except Exception:
            full = ''
        if not full:
            return
        seg_start = abs_start
        seg_end = min(abs_end, len(full))
        visible = full[seg_start:seg_end]
        tags_to_clear = ['keyword', 'builtin', 'string', 'number', 'comment', 'function', 'class', 'operator', 'constant', 'bracket']
        start_index = f'1.0+{seg_start}c'
        end_index = f'1.0+{seg_end}c'
        for tag in tags_to_clear:
            try:
                self.textwidget.tag_remove(tag, start_index, end_index)
            except Exception:
                pass
        self.generate_tokens(visible)
        offset = 0
        line_comment_active = False
        while True:
            tok = self.next_tok()
            if tok is None:
                break
            s, ln = tok
            abs_tok_start = seg_start + offset
            abs_tok_end = abs_tok_start + ln
            idx_start = f'1.0+{abs_tok_start}c'
            idx_end = f'1.0+{abs_tok_end}c'
            if s.startswith('#'):
                self.textwidget.tag_add('comment', idx_start, idx_end)
                offset += ln
                continue
            if s.startswith('"') or s.startswith("'"):
                self.textwidget.tag_add('string', idx_start, idx_end)
                offset += ln
                continue
            if RE_NUMBER.fullmatch(s):
                self.textwidget.tag_add('number', idx_start, idx_end)
                offset += ln
                continue
            if s in ('(', ')', '[', ']', '{', '}') or re.match('^[+\\-*/%=&|^~<>:.,]+$', s):
                if s in ('(', ')', '[', ']', '{', '}'):
                    self.textwidget.tag_add('bracket', idx_start, idx_end)
                else:
                    self.textwidget.tag_add('operator', idx_start, idx_end)
                offset += ln
                continue
            if RE_IDENTIFIER.fullmatch(s):
                if s in self.class_names:
                    self.textwidget.tag_add('class', idx_start, idx_end)
                elif s in self.user_functions:
                    self.textwidget.tag_add('function', idx_start, idx_end)
                elif s in self.builtin_functions:
                    self.textwidget.tag_add('function', idx_start, idx_end)
                elif s in self.builtin_classes:
                    self.textwidget.tag_add('class', idx_start, idx_end)
                elif s in PY_KEYWORDS and s not in ('True', 'False', 'None'):
                    self.textwidget.tag_add('keyword', idx_start, idx_end)
                elif s in ('True', 'False', 'None'):
                    self.textwidget.tag_add('builtin', idx_start, idx_end)
                else:
                    nxt = self.peek_tok(0)
                    if nxt and nxt[0] == '(':
                        self.textwidget.tag_add('function', idx_start, idx_end)
                offset += ln
                continue
            offset += ln
        self.current_lexer_pos = max(self.current_lexer_pos, abs_end)

    def highlight_entire_buffer(self):
        try:
            full_len = len(self.textwidget.get('1.0', 'end-1c'))
        except Exception:
            full_len = 0
        if full_len > 0:
            self.style_text(0, full_len)


class EditorTab(ttk.Frame):
    def __init__(self, master, theme):
        super().__init__(master)
        self.theme = theme
        self._highlight_after_id = None
        self.filepath = None
        self.name = 'Untitled'
        self._visible_cache = {}
        self._build_widgets()
        self._configure_tags()
        self._bind_events()
        self.lexer = TkPythonLexer(self)
        self.lexer.perform_name_check()
        self._schedule_highlight(10)

    def _build_widgets(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.gutter = tk.Text(self, width=5, padx=4, takefocus=0, border=0,
                              background=self.theme['gutter_bg'], foreground=self.theme['gutter_fg'],
                              state='disabled', font=(FONT_FAMILY, FONT_SIZE))
        self.gutter.grid(row=0, column=0, sticky='ns')

        self.text = tk.Text(self, wrap='none', undo=True, font=(FONT_FAMILY, FONT_SIZE),
                            background=self.theme['background'], foreground=self.theme['foreground'],
                            insertbackground=self.theme['foreground'], padx=6, pady=4)
        self.text.grid(row=0, column=1, sticky='nsew')

        self.vscroll = tk.Scrollbar(self, orient='vertical', command=self.text.yview)
        self.vscroll.grid(row=0, column=2, sticky='ns')
        self.text.config(yscrollcommand=self.vscroll.set)

        self.hscroll = tk.Scrollbar(self, orient='horizontal', command=self.text.xview)
        self.hscroll.grid(row=1, column=1, sticky='ew')
        self.text.config(xscrollcommand=self.hscroll.set)


    def _configure_tags(self):
        t = self.text
        t.tag_configure('current_line', background=self.theme['current_line'])
        t.tag_configure('keyword', foreground=self.theme['keyword'])
        t.tag_configure('builtin', foreground=self.theme['builtin'])
        t.tag_configure('string', foreground=self.theme['string'])
        t.tag_configure('number', foreground=self.theme['number'])
        t.tag_configure('comment', foreground=self.theme['comment'])
        t.tag_configure('function', foreground=self.theme['function'])
        t.tag_configure('operator', foreground=self.theme['operator'])
        t.tag_configure('bracket', background='#3B4252')
        t.tag_configure('sel', background=self.theme['selection'])
        t.tag_configure('search', background='#44475a')

    def _bind_events(self):
        self.text.bind('<<Modified>>', self._on_modified)
        self.text.bind('<KeyRelease>', self._on_keyrelease)
        self.text.bind('<Tab>', self._on_tab)
        self.text.bind('<Return>', self._on_return)
        self.text.bind('<Button-1>', lambda e: self._schedule_highlight(30))
        self.text.bind('<Configure>', lambda e: self._schedule_highlight(10))
        if sys.platform.startswith('win'):
            self.text.bind('<MouseWheel>', self._on_mousewheel)
        else:
            self.text.bind('<Button-4>', self._on_mousewheel)
            self.text.bind('<Button-5>', self._on_mousewheel)
        self.text.bind('<KeyRelease>', self._on_cursor_move)
        self.text.bind('<ButtonRelease-1>', self._on_cursor_move)

    def _on_mousewheel(self, event):
        if sys.platform.startswith('win'):
            delta = -1 * (event.delta // 120)
            self.text.yview_scroll(delta, 'units')
        else:
            if getattr(event, 'num', None) == 4:
                self.text.yview_scroll(-1, 'units')
            else:
                self.text.yview_scroll(1, 'units')
        self._sync_gutter()
        self._schedule_highlight(10)
        return 'break'

    def _sync_gutter(self):
        last_line = int(self.text.index('end-1c').split('.')[0])
        lines = '\n'.join(str(i) for i in range(1, last_line + 1))
        self.gutter.config(state='normal')
        self.gutter.delete('1.0', 'end')
        self.gutter.insert('1.0', lines + '\n')
        self.gutter.config(state='disabled')

    def _on_modified(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self._sync_gutter()
            self._schedule_highlight(80)

    def _on_tab(self, event):
        self.text.insert('insert', TAB_SPACES)
        return 'break'

    def _on_return(self, event):
        line_start = self.text.index('insert linestart')
        line_end = self.text.index('insert')
        current_line_text = self.text.get(line_start, line_end)
        indent = re.match(r'\s*', current_line_text).group(0)
        self.text.insert('insert', '\n' + indent)
        if re.search(r':\s*$', current_line_text):
            self.text.insert('insert', TAB_SPACES)
        return 'break'

    def _on_keyrelease(self, event):
        key = event.keysym
        if len(event.char) == 1 and (event.char.isalnum() or event.char == '_'):
            self.show_autocomplete()
        elif key in ('space', 'BackSpace', 'Left', 'Right', 'Up', 'Down', 'Return'):
            self.hide_autocomplete()
        self._schedule_highlight(30)

    def _on_cursor_move(self, event=None):
        self._highlight_brackets()
        self._highlight_current_line()

    def _schedule_highlight(self, delay_ms=50):
        if self._highlight_after_id:
            try:
                self.after_cancel(self._highlight_after_id)
            except Exception:
                pass
        self._highlight_after_id = self.after(delay_ms, self._highlight_visible_region)

    def _abs_pos(self, index):
        parts = index.split('.')
        line = int(parts[0]); col = int(parts[1])
        abs_pos = 0
        for l in range(1, line):
            abs_pos += len(self.text.get(f'{l}.0', f'{l}.end')) + 1
        abs_pos += col
        return abs_pos

    def _index_from_abs(self, abs_pos):
        return f'1.0+{abs_pos}c'

    def _highlight_visible_region(self):
        if not hasattr(self, 'text') or not self.lexer:
            return
        text_widget = self.text
        lexer = self.lexer

        try:
            first_visible_index = text_widget.index('@0,0')
            first_visible_line = int(first_visible_index.split('.')[0])
            bottom_y = max(0, text_widget.winfo_height() - 1)
            last_visible_index = text_widget.index(f'@0,{bottom_y}')
            last_visible_line = int(last_visible_index.split('.')[0])
            total_lines = int(text_widget.index('end-1c').split('.')[0])
            first_visible_line = max(1, first_visible_line)
            last_visible_line = min(total_lines, last_visible_line)
        except Exception:
            first_visible_line = 1
            last_visible_line = int(text_widget.index('end-1c').split('.')[0])

        try:
            abs_start = self._abs_pos(f'{first_visible_line}.0')
            abs_end = self._abs_pos(f'{last_visible_line}.end')
        except Exception:
            abs_start = 0
            abs_end = len(text_widget.get('1.0', 'end-1c'))

        lexer.style_text(abs_start, abs_end)
        self._highlight_current_line()
        self._highlight_brackets()

    def _highlight_current_line(self):
        self.text.tag_remove('current_line', '1.0', 'end')
        idx = self.text.index('insert')
        line = idx.split('.')[0]
        self.text.tag_add('current_line', line + '.0', line + '.end')

    def _highlight_brackets(self):
        t = self.text
        t.tag_remove('bracket', '1.0', 'end')
        idx = t.index('insert')
        pos = t.index(f'{idx}-1c')
        ch = t.get(pos)
        pair = {'(': ')', '[': ']', '{': '}', ')': '(', '}': '{', ']': '['}
        if ch in pair:
            try:
                if ch in '([{':
                    match_idx = t.search(r'\%s' % pair[ch], pos, stopindex='end', regexp=False)
                else:
                    match_idx = t.search(r'\%s' % pair[ch], '1.0', stopindex=pos, regexp=False)
                if match_idx:
                    t.tag_add('bracket', pos, f'{pos}+1c')
                    t.tag_add('bracket', match_idx, f'{match_idx}+1c')
            except Exception:
                pass

    def show_autocomplete(self):
        prefix = self._get_prefix()
        if not prefix or len(prefix) < 2:
            self.hide_autocomplete()
            return
        words = self._collect_words()
        matches = difflib.get_close_matches(prefix, words, n=50, cutoff=0.0)
        matches = [w for w in words if w.startswith(prefix)] + [m for m in matches if m not in words or not m.startswith(prefix)]
        if not matches:
            self.hide_autocomplete()
            return
        if not hasattr(self, 'ac_popup') or not self.ac_popup:
            self.ac_popup = ctk.CTkToplevel(self)
            self.ac_popup.wm_overrideredirect(True)
            self.ac_list = tk.Listbox(self.ac_popup, activestyle='dotbox', selectmode='browse')
            self.ac_list.pack(fill='both', expand=True)
            self.ac_list.bind('<Double-Button-1>', lambda e: self._complete_from_list())
            self.ac_list.bind('<Return>', lambda e: self._complete_from_list())
            self.ac_list.bind('<Escape>', lambda e: self.hide_autocomplete())
        else:
            self.ac_list.delete(0, 'end')
        for w in matches[:200]:
            self.ac_list.insert('end', w)
        bbox = self.text.bbox('insert')
        if bbox:
            x, y, w, h = bbox
            abs_x = self.text.winfo_rootx() + x
            abs_y = self.text.winfo_rooty() + y + h
        else:
            abs_x = self.text.winfo_rootx()
            abs_y = self.text.winfo_rooty()
        self.ac_popup.geometry(f'+{abs_x}+{abs_y}')
        self.ac_popup.lift()
        self.ac_list.selection_set(0)
        self.ac_list.focus_set()

    def hide_autocomplete(self):
        if hasattr(self, 'ac_popup') and self.ac_popup:
            try:
                self.ac_popup.destroy()
            except Exception:
                pass
            self.ac_popup = None
            self.ac_list = None

    def _complete_from_list(self):
        if not hasattr(self, 'ac_list') or not self.ac_list:
            return
        sel = self.ac_list.curselection()
        if not sel:
            return
        word = self.ac_list.get(sel[0])
        prefix = self._get_prefix()
        for _ in range(len(prefix)):
            self.text.delete('insert-1c')
        self.text.insert('insert', word)
        self.hide_autocomplete()
        self._schedule_highlight(10)

    def _get_prefix(self):
        idx = self.text.index('insert')
        line, col = map(int, idx.split('.'))
        start = f'{line}.{max(col - 100, 0)}'
        txt = self.text.get(start, idx)
        m = re.search(r'([A-Za-z_][A-Za-z0-9_]*)$', txt)
        return m.group(1) if m else ''

    def _collect_words(self):
        txt = self.text.get('1.0', 'end-1c')
        words = set(re.findall(r'\b[A-Za-z_][A-Za-z0-9_]{2,}\b', txt))
        words |= PY_KEYWORDS
        words |= PY_BUILTINS
        return sorted(words)
