"""Custom urwid widgets for the language learning app."""

import urwid

from src.core.models import WordStage
from src.core.text_processor import TextProcessor, AnnotatedToken
from src.ui.theme import get_stage_attr


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


class SelectableLine(urwid.WidgetWrap):
    """A line of text with clickable words."""

    def __init__(self, tokens: list[AnnotatedToken], selected_words: set[str], on_word_click):
        self.tokens = tokens
        self.selected_words = selected_words
        self.on_word_click = on_word_click

        # Build markup for urwid.Text
        markup = self._build_markup()
        self.text_widget = urwid.Text(markup)
        super().__init__(self.text_widget)

    def _build_markup(self):
        """Build urwid text markup with colors."""
        markup = []
        for token in self.tokens:
            if token.normalized in self.selected_words:
                attr = "selected"
            elif token.is_word:
                attr = get_stage_attr(token.stage)
            else:
                attr = None

            if attr:
                markup.append((attr, token.text))
            else:
                markup.append(token.text)
        return markup

    def update_selection(self, selected_words: set[str]):
        """Update the selection and redraw."""
        self.selected_words = selected_words
        self.text_widget.set_text(self._build_markup())

    def selectable(self):
        return True

    def keypress(self, size, key):
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1:
            # Find which word was clicked
            pos = 0
            for token in self.tokens:
                token_end = pos + len(token.text)
                if pos <= col < token_end and token.is_word:
                    if self.on_word_click:
                        self.on_word_click(token.normalized)
                    return True
                pos = token_end
        return False


class AnnotatedTextViewer(urwid.WidgetWrap):
    """Display annotated text with word highlighting and selection."""

    def __init__(self, on_word_click=None):
        self.on_word_click = on_word_click
        self.processor = TextProcessor()
        self.selected_words: set[str] = set()
        self.lines: list[SelectableLine] = []
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
        self.selected_words.clear()
        self._rebuild()

    def _rebuild(self):
        """Rebuild the display."""
        self.walker.clear()
        self.lines.clear()

        for line_tokens in self.processor.iter_lines_annotated(
            self._text, self._known_words, self._learning_words
        ):
            line = SelectableLine(
                line_tokens,
                self.selected_words,
                self._on_word_click,
            )
            self.lines.append(line)
            self.walker.append(line)

    def _on_word_click(self, word: str):
        """Handle click on a word."""
        if word in self.selected_words:
            self.selected_words.remove(word)
        else:
            self.selected_words.add(word)

        # Update all lines to show new selection
        for line in self.lines:
            line.update_selection(self.selected_words)

        if self.on_word_click:
            self.on_word_click(word, word in self.selected_words)

    def get_selected_words(self) -> set[str]:
        """Get currently selected words."""
        return self.selected_words.copy()

    def clear_selection(self):
        """Clear all selected words."""
        self.selected_words.clear()
        for line in self.lines:
            line.update_selection(self.selected_words)


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
