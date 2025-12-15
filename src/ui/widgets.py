"""Custom urwid widgets for the language learning app."""

from dataclasses import dataclass
import urwid

from src.core.models import WordStage
from src.core.text_processor import TextProcessor, AnnotatedToken
from src.ui.theme import get_stage_attr, get_cursor_attr


@dataclass
class WordInfo:
    """Information about a word in the text."""
    text: str           # Original text
    normalized: str     # Lowercase normalized form
    stage: WordStage    # Vocabulary stage
    line_idx: int       # Line index in document
    word_idx: int       # Word index within line
    global_idx: int     # Global word index in document
    char_start: int     # Character start position in line
    char_end: int       # Character end position in line


class SelectableText(urwid.WidgetWrap):
    """A text widget that can be selected/focused."""

    def __init__(self, text, attr=None):
        self.text = text
        self._attr = attr
        widget = urwid.Text(text)
        if attr:
            widget = urwid.AttrMap(widget, attr)
        super().__init__(widget)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key


class ListItem(urwid.WidgetWrap):
    """A selectable list item."""

    def __init__(self, id: str, title: str, subtitle: str = "", on_select=None):
        self.id = id
        self.title = title
        self.subtitle = subtitle
        self.on_select = on_select

        # Create the display
        if subtitle:
            text = f"{title}\n  {subtitle}"
        else:
            text = title

        self.text_widget = urwid.Text(text)
        widget = urwid.AttrMap(
            self.text_widget,
            "list_item",
            focus_map="list_item_focus"
        )
        super().__init__(widget)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "enter" and self.on_select:
            self.on_select(self.id)
            return None
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1 and self.on_select:
            self.on_select(self.id)
            return True
        return False


class ListBrowser(urwid.WidgetWrap):
    """A scrollable list browser widget."""

    def __init__(self, on_select=None):
        self.on_select = on_select
        self.items = []
        self.walker = urwid.SimpleFocusListWalker([])
        self.listbox = urwid.ListBox(self.walker)
        super().__init__(self.listbox)

    def set_items(self, items: list[tuple[str, str, str]]):
        """Set list items. Each item is (id, title, subtitle)."""
        self.items = items
        self.walker.clear()

        for id, title, subtitle in items:
            item = ListItem(id, title, subtitle, on_select=self.on_select)
            self.walker.append(item)

    def get_focused_id(self) -> str | None:
        """Get the ID of the currently focused item."""
        if self.walker and self.walker.focus is not None:
            focus_widget = self.walker[self.walker.focus]
            if hasattr(focus_widget, "id"):
                return focus_widget.id
        return None


class TextLine(urwid.WidgetWrap):
    """A line of text with words that can be highlighted."""

    def __init__(self, line_idx: int, tokens: list[AnnotatedToken], on_click=None):
        self.line_idx = line_idx
        self.tokens = tokens
        self.on_click = on_click
        self.cursor_word_idx: int | None = None
        self.selected_word_indices: set[int] = set()

        # Build word info for this line
        self.word_infos: list[tuple[int, AnnotatedToken]] = []  # (word_idx_in_line, token)
        word_idx = 0
        for token in tokens:
            if token.is_word:
                self.word_infos.append((word_idx, token))
                word_idx += 1

        self.text_widget = urwid.Text("")
        self._update_display()
        super().__init__(self.text_widget)

    def _update_display(self):
        """Build urwid text markup with colors."""
        markup = []
        word_idx = 0
        for token in self.tokens:
            if token.is_word:
                is_cursor = (word_idx == self.cursor_word_idx)
                is_selected = (word_idx in self.selected_word_indices)

                if is_cursor:
                    attr = get_cursor_attr(token.stage, is_selected)
                elif is_selected:
                    attr = "selected"
                else:
                    attr = get_stage_attr(token.stage)

                markup.append((attr, token.text))
                word_idx += 1
            else:
                markup.append(token.text)

        self.text_widget.set_text(markup)

    def set_cursor(self, word_idx: int | None):
        """Set cursor to word index (within this line) or None."""
        if self.cursor_word_idx != word_idx:
            self.cursor_word_idx = word_idx
            self._update_display()

    def set_selected(self, word_indices: set[int]):
        """Set which word indices are selected."""
        if self.selected_word_indices != word_indices:
            self.selected_word_indices = word_indices
            self._update_display()

    def get_word_at_col(self, col: int) -> int | None:
        """Get word index at character column, or None."""
        pos = 0
        word_idx = 0
        for token in self.tokens:
            token_end = pos + len(token.text)
            if token.is_word:
                if pos <= col < token_end:
                    return word_idx
                word_idx += 1
            pos = token_end
        return None

    def get_word_count(self) -> int:
        """Get number of words in this line."""
        return len(self.word_infos)

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and self.on_click:
            word_idx = self.get_word_at_col(col)
            # Check for modifier keys
            # urwid doesn't directly expose modifiers, but we can check button values
            # button 1 = left click, higher values can indicate modifiers on some terminals
            self.on_click(self.line_idx, word_idx, col, event, button)
            return True
        return False


class AnnotatedTextViewer(urwid.WidgetWrap):
    """Display annotated text with cursor navigation and selection."""

    def __init__(self, on_word_click=None):
        self.on_word_click = on_word_click
        self.processor = TextProcessor()

        # All words in document order
        self.words: list[WordInfo] = []
        # Lines with their widgets
        self.lines: list[TextLine] = []
        # Current cursor position (index into self.words)
        self.cursor_pos: int = 0
        # Selected word indices (into self.words)
        self.selected_indices: set[int] = set()

        self._text = ""
        self._known_words: set[str] = set()
        self._learning_words: set[str] = set()

        self.walker = urwid.SimpleFocusListWalker([])
        self.listbox = urwid.ListBox(self.walker)
        super().__init__(self.listbox)

    def set_text(
        self,
        text: str,
        known_words: set[str],
        learning_words: set[str],
    ):
        """Set the text to display with vocabulary highlighting."""
        self._text = text
        self._known_words = known_words
        self._learning_words = learning_words
        self.selected_indices.clear()
        self.cursor_pos = 0
        self._rebuild()

    def _rebuild(self):
        """Rebuild the display."""
        self.walker.clear()
        self.lines.clear()
        self.words.clear()

        global_word_idx = 0

        for line_idx, line_tokens in enumerate(self.processor.iter_lines_annotated(
            self._text, self._known_words, self._learning_words
        )):
            # Build word info for this line
            char_pos = 0
            word_idx_in_line = 0
            for token in line_tokens:
                if token.is_word:
                    word_info = WordInfo(
                        text=token.text,
                        normalized=token.normalized,
                        stage=token.stage,
                        line_idx=line_idx,
                        word_idx=word_idx_in_line,
                        global_idx=global_word_idx,
                        char_start=char_pos,
                        char_end=char_pos + len(token.text),
                    )
                    self.words.append(word_info)
                    global_word_idx += 1
                    word_idx_in_line += 1
                char_pos += len(token.text)

            line_widget = TextLine(line_idx, line_tokens, on_click=self._on_line_click)
            self.lines.append(line_widget)
            self.walker.append(line_widget)

        # Set initial cursor if we have words
        if self.words:
            self._update_display()

    def _update_display(self):
        """Update all lines to reflect current cursor and selection."""
        # Group selected indices by line
        selected_by_line: dict[int, set[int]] = {}
        for idx in self.selected_indices:
            if idx < len(self.words):
                word = self.words[idx]
                if word.line_idx not in selected_by_line:
                    selected_by_line[word.line_idx] = set()
                selected_by_line[word.line_idx].add(word.word_idx)

        # Get cursor line and word
        cursor_line = None
        cursor_word = None
        if self.words and 0 <= self.cursor_pos < len(self.words):
            cursor_word_info = self.words[self.cursor_pos]
            cursor_line = cursor_word_info.line_idx
            cursor_word = cursor_word_info.word_idx

        # Update each line
        for line_idx, line in enumerate(self.lines):
            line.set_cursor(cursor_word if line_idx == cursor_line else None)
            line.set_selected(selected_by_line.get(line_idx, set()))

        # Scroll to cursor line
        if cursor_line is not None and cursor_line < len(self.walker):
            self.listbox.set_focus(cursor_line)

    def _on_line_click(self, line_idx: int, word_idx: int | None, col: int, event: str, button: int):
        """Handle click on a line."""
        if word_idx is None:
            return

        # Find global word index
        global_idx = self._find_global_idx(line_idx, word_idx)
        if global_idx is None:
            return

        # Plain click: move cursor only
        # Note: urwid doesn't give us direct access to modifier keys in most terminals
        # We'll handle cmd-click and shift-click via a workaround or just use keyboard
        self.cursor_pos = global_idx
        self._update_display()

        if self.on_word_click:
            self.on_word_click(self.words[global_idx].normalized, False)

    def _find_global_idx(self, line_idx: int, word_idx: int) -> int | None:
        """Find global word index from line and word index."""
        for word in self.words:
            if word.line_idx == line_idx and word.word_idx == word_idx:
                return word.global_idx
        return None

    def move_cursor(self, direction: str):
        """Move cursor: 'left', 'right', 'up', 'down', 'line_start', 'line_end'."""
        if not self.words:
            return

        current = self.words[self.cursor_pos]

        if direction == "left" or direction == "backward":
            if self.cursor_pos > 0:
                self.cursor_pos -= 1
        elif direction == "right" or direction == "forward":
            if self.cursor_pos < len(self.words) - 1:
                self.cursor_pos += 1
        elif direction == "up":
            # Find nearest word on previous line
            target_line = current.line_idx - 1
            if target_line >= 0:
                self.cursor_pos = self._find_nearest_word_on_line(target_line, current.char_start)
        elif direction == "down":
            # Find nearest word on next line
            target_line = current.line_idx + 1
            max_line = max(w.line_idx for w in self.words)
            if target_line <= max_line:
                self.cursor_pos = self._find_nearest_word_on_line(target_line, current.char_start)
        elif direction == "line_start":
            # First word on current line
            for word in self.words:
                if word.line_idx == current.line_idx:
                    self.cursor_pos = word.global_idx
                    break
        elif direction == "line_end":
            # Last word on current line
            for word in reversed(self.words):
                if word.line_idx == current.line_idx:
                    self.cursor_pos = word.global_idx
                    break

        self._update_display()

    def _find_nearest_word_on_line(self, line_idx: int, target_char: int) -> int:
        """Find word on line closest to target character position."""
        words_on_line = [w for w in self.words if w.line_idx == line_idx]
        if not words_on_line:
            return self.cursor_pos

        # Find closest by character position
        best = min(words_on_line, key=lambda w: abs(w.char_start - target_char))
        return best.global_idx

    def toggle_select_current(self):
        """Toggle selection on current word."""
        if not self.words:
            return

        if self.cursor_pos in self.selected_indices:
            self.selected_indices.remove(self.cursor_pos)
        else:
            self.selected_indices.add(self.cursor_pos)

        self._update_display()

        if self.on_word_click:
            word = self.words[self.cursor_pos]
            self.on_word_click(word.normalized, self.cursor_pos in self.selected_indices)

    def select_range_to(self, target_idx: int):
        """Select all words from current cursor to target index."""
        if not self.words:
            return

        start = min(self.cursor_pos, target_idx)
        end = max(self.cursor_pos, target_idx)

        for i in range(start, end + 1):
            self.selected_indices.add(i)

        self.cursor_pos = target_idx
        self._update_display()

    def get_selected_words(self) -> list[str]:
        """Get selected words in document order."""
        sorted_indices = sorted(self.selected_indices)
        return [self.words[i].normalized for i in sorted_indices if i < len(self.words)]

    def get_selected_words_original(self) -> list[str]:
        """Get selected words in original form (not normalized) in document order."""
        sorted_indices = sorted(self.selected_indices)
        return [self.words[i].text for i in sorted_indices if i < len(self.words)]

    def get_current_word(self) -> str | None:
        """Get the current word under cursor."""
        if self.words and 0 <= self.cursor_pos < len(self.words):
            return self.words[self.cursor_pos].normalized
        return None

    def get_current_word_original(self) -> str | None:
        """Get the current word under cursor in original form."""
        if self.words and 0 <= self.cursor_pos < len(self.words):
            return self.words[self.cursor_pos].text
        return None

    def is_selection_contiguous(self) -> bool:
        """Check if selected words are contiguous in the document."""
        if len(self.selected_indices) <= 1:
            return True

        sorted_indices = sorted(self.selected_indices)
        for i in range(1, len(sorted_indices)):
            if sorted_indices[i] != sorted_indices[i-1] + 1:
                return False
        return True

    def get_selection_as_phrase(self) -> str | None:
        """Get selected words as a phrase if contiguous, None otherwise."""
        if not self.selected_indices:
            return None

        if not self.is_selection_contiguous():
            return None

        return " ".join(self.get_selected_words_original())

    def clear_selection(self):
        """Clear all selected words but keep cursor."""
        self.selected_indices.clear()
        self._update_display()

    def keypress(self, size, key):
        """Handle navigation keys."""
        # Emacs keys
        if key == "ctrl f" or key == "right":
            self.move_cursor("forward")
            return None
        elif key == "ctrl b" or key == "left":
            self.move_cursor("backward")
            return None
        elif key == "ctrl n" or key == "down":
            self.move_cursor("down")
            return None
        elif key == "ctrl p" or key == "up":
            self.move_cursor("up")
            return None
        elif key == "ctrl a":
            self.move_cursor("line_start")
            return None
        elif key == "ctrl e":
            self.move_cursor("line_end")
            return None
        elif key == " ":
            self.toggle_select_current()
            return None

        return key


class TabBar(urwid.WidgetWrap):
    """A horizontal tab bar."""

    def __init__(self, tabs: list[str], on_tab_change=None):
        self.tabs = tabs
        self.active_tab = 0
        self.on_tab_change = on_tab_change

        self._build()

    def _build(self):
        """Build the tab bar widget."""
        columns = []
        for i, tab in enumerate(self.tabs):
            if i == self.active_tab:
                attr = "tab_active"
            else:
                attr = "tab_inactive"

            btn = urwid.Text(f" {tab} ")
            btn = urwid.AttrMap(btn, attr)
            columns.append(("pack", btn))
            columns.append(("pack", urwid.Text(" ")))

        widget = urwid.Columns(columns)
        widget = urwid.AttrMap(widget, "header")
        self._w = widget

    def set_active(self, index: int):
        """Set the active tab."""
        if 0 <= index < len(self.tabs):
            self.active_tab = index
            self._build()
            if self.on_tab_change:
                self.on_tab_change(index)

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key == "left":
            self.set_active(max(0, self.active_tab - 1))
            return None
        elif key == "right":
            self.set_active(min(len(self.tabs) - 1, self.active_tab + 1))
            return None
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1:
            # Calculate which tab was clicked
            x = 0
            for i, tab in enumerate(self.tabs):
                tab_width = len(tab) + 2 + 1  # text + padding + spacer
                if x <= col < x + tab_width:
                    self.set_active(i)
                    return True
                x += tab_width
        return False


class StatusBar(urwid.WidgetWrap):
    """A status bar showing hints and messages."""

    def __init__(self, text: str = ""):
        self.text_widget = urwid.Text(text)
        widget = urwid.AttrMap(self.text_widget, "footer")
        super().__init__(widget)

    def set_text(self, text: str):
        """Set the status text."""
        self.text_widget.set_text(text)

    def set_hint(self, hint: str):
        """Set a keyboard hint."""
        self.set_text(hint)


class Dialog(urwid.WidgetWrap):
    """A modal dialog widget."""

    def __init__(self, title: str, body: urwid.Widget, buttons: list[tuple[str, callable]]):
        self.title = title
        self.buttons = buttons

        # Title
        title_widget = urwid.Text(title, align="center")
        title_widget = urwid.AttrMap(title_widget, "dialog_title")

        # Buttons
        button_widgets = []
        for label, callback in buttons:
            btn = urwid.Button(label)
            urwid.connect_signal(btn, "click", lambda b, cb=callback: cb())
            btn = urwid.AttrMap(btn, "button", focus_map="button_focus")
            button_widgets.append(btn)

        button_row = urwid.Columns(
            [(len(b[0]) + 4, w) for b, w in zip(buttons, button_widgets)],
            dividechars=2
        )
        button_row = urwid.Padding(button_row, align="center", width="pack")

        # Combine
        pile = urwid.Pile([
            title_widget,
            urwid.Divider(),
            body,
            urwid.Divider(),
            button_row,
        ])

        # Add border
        lined = urwid.LineBox(pile)
        widget = urwid.AttrMap(lined, "dialog")

        super().__init__(widget)
