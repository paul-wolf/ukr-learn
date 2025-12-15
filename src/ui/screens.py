"""Screen compositions for different app views."""

import urwid

from src.core.models import Text, WordList, GrammarNote, WordStage
from src.core.text_processor import TextProcessor
from src.ui.widgets import ListBrowser, TabBar, StatusBar, AnnotatedTextViewer
from src.ui.theme import get_stage_attr


class TextScreen(urwid.WidgetWrap):
    """Screen for viewing reading texts."""

    def __init__(self, app):
        self.app = app
        self.current_text: Text | None = None

        # List browser for texts
        self.list_browser = ListBrowser(on_select=self._on_text_select)

        # Text viewer
        self.text_viewer = AnnotatedTextViewer(on_word_click=self._on_word_click)

        # Build layout
        self.list_box = urwid.LineBox(self.list_browser, title="Texts")
        self.content_box = urwid.LineBox(self.text_viewer, title="Content")

        pile = urwid.Pile([
            ("weight", 1, self.list_box),
            ("weight", 2, self.content_box),
        ])

        super().__init__(pile)

    def refresh_list(self):
        """Refresh the text list."""
        summaries = self.app.content.list_texts()
        items = [(s.id, s.title, s.subtitle) for s in summaries]
        self.list_browser.set_items(items)

    def _on_text_select(self, text_id: str):
        """Handle text selection."""
        text = self.app.content.get_text(text_id)
        if text:
            self.current_text = text
            self._show_text(text)

    def _show_text(self, text: Text):
        """Display a text with vocabulary highlighting."""
        known = self.app.vocabulary.get_known_words()
        learning = self.app.vocabulary.get_learning_words()

        self.text_viewer.set_text(text.content, known, learning)
        self.content_box.set_title(text.title)

    def _on_word_click(self, word: str, selected: bool):
        """Handle word click in text - just update status."""
        self.app.update_status()

    def get_selected_words(self) -> set[str]:
        """Get selected words from the text viewer."""
        return self.text_viewer.get_selected_words()

    def clear_selection(self):
        """Clear word selection."""
        self.text_viewer.clear_selection()

    def keypress(self, size, key):
        selected = self.get_selected_words()
        if key == "k" and selected:
            # Toggle: if all are known, set to new; otherwise set to known
            all_known = all(
                self.app.vocabulary.get_stage(w) == WordStage.KNOWN
                for w in selected
            )
            if all_known:
                self.app.vocabulary.bulk_set_stage(list(selected), WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(list(selected), WordStage.KNOWN)
                self.app.show_message("Marked as known")
            self.clear_selection()
            if self.current_text:
                self._show_text(self.current_text)
            return None
        elif key == "l" and selected:
            # Toggle: if all are learning, set to new; otherwise set to learning
            all_learning = all(
                self.app.vocabulary.get_stage(w) == WordStage.LEARNING
                for w in selected
            )
            if all_learning:
                self.app.vocabulary.bulk_set_stage(list(selected), WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(list(selected), WordStage.LEARNING)
                self.app.show_message("Marked as learning")
            self.clear_selection()
            if self.current_text:
                self._show_text(self.current_text)
            return None
        elif key == "t" and selected:
            # Translate selected words via AI
            self._translate_selected(selected)
            return None
        elif key == "esc":
            self.clear_selection()
            self.app.update_status()
            return None

        return super().keypress(size, key)

    def _translate_selected(self, selected: set[str]):
        """Translate selected words using AI."""
        if not self.app.generator:
            self.app.show_message("AI not configured - set API key in config")
            return

        # Translate words that don't have translations
        translated = 0
        for word in selected:
            existing = self.app.lookup_translation(word)
            if not existing:
                try:
                    self.app.show_message(f"Translating '{word}'...")
                    translation = self.app.generator.translate_word(word)
                    self.app.vocabulary.set_translation(word, translation)
                    translated += 1
                except Exception as e:
                    self.app.show_message(f"Error translating: {e}")
                    return

        if translated > 0:
            self.app.show_message(f"Translated {translated} word(s)")
        else:
            self.app.show_message("All words already have translations")
        self.app.update_status()


class WordListScreen(urwid.WidgetWrap):
    """Screen for viewing word lists."""

    def __init__(self, app):
        self.app = app
        self.current_list: WordList | None = None

        # List browser for word lists
        self.list_browser = ListBrowser(on_select=self._on_list_select)

        # Word display
        self.word_walker = urwid.SimpleFocusListWalker([])
        self.word_listbox = urwid.ListBox(self.word_walker)

        # Build layout
        self.list_box = urwid.LineBox(self.list_browser, title="Word Lists")
        self.content_box = urwid.LineBox(self.word_listbox, title="Words")

        pile = urwid.Pile([
            ("weight", 1, self.list_box),
            ("weight", 2, self.content_box),
        ])

        super().__init__(pile)

    def refresh_list(self):
        """Refresh the word list list."""
        summaries = self.app.content.list_wordlists()
        items = [(s.id, s.title, s.subtitle) for s in summaries]
        self.list_browser.set_items(items)

    def _on_list_select(self, list_id: str):
        """Handle word list selection."""
        wordlist = self.app.content.get_wordlist(list_id)
        if wordlist:
            self.current_list = wordlist
            self._show_wordlist(wordlist)

    def _show_wordlist(self, wordlist: WordList):
        """Display a word list."""
        self.word_walker.clear()
        self.content_box.set_title(wordlist.title)

        known = self.app.vocabulary.get_known_words()
        learning = self.app.vocabulary.get_learning_words()

        for entry in wordlist.words:
            word_lower = entry.word.lower()
            if word_lower in known:
                stage_attr = "known"
                stage_text = "[K]"
            elif word_lower in learning:
                stage_attr = "learning"
                stage_text = "[L]"
            else:
                stage_attr = "new"
                stage_text = "[ ]"

            # Format: [stage] word - translation (notes)
            text = f"{stage_text} {entry.word} - {entry.translation}"
            if entry.notes:
                text += f" ({entry.notes})"

            widget = urwid.Text(text)
            widget = urwid.AttrMap(widget, stage_attr)
            self.word_walker.append(widget)

    def keypress(self, size, key):
        if key == "i" and self.current_list:
            # Import word list to vocabulary
            count = self.app.content.import_wordlist_to_vocabulary(
                self.current_list.id,
                self.app.vocabulary,
            )
            self.app.show_message(f"Imported {count} words to vocabulary")
            return None

        return super().keypress(size, key)


class GrammarScreen(urwid.WidgetWrap):
    """Screen for viewing grammar notes."""

    def __init__(self, app):
        self.app = app
        self.current_note: GrammarNote | None = None

        # List browser for grammar notes
        self.list_browser = ListBrowser(on_select=self._on_note_select)

        # Content display
        self.content_text = urwid.Text("")
        self.content_walker = urwid.SimpleFocusListWalker([self.content_text])
        self.content_listbox = urwid.ListBox(self.content_walker)

        # Build layout
        self.list_box = urwid.LineBox(self.list_browser, title="Grammar Notes")
        self.content_box = urwid.LineBox(self.content_listbox, title="Content")

        pile = urwid.Pile([
            ("weight", 1, self.list_box),
            ("weight", 2, self.content_box),
        ])

        super().__init__(pile)

    def refresh_list(self):
        """Refresh the grammar note list."""
        summaries = self.app.content.list_grammar()
        items = [(s.id, s.title, s.subtitle) for s in summaries]
        self.list_browser.set_items(items)

    def _on_note_select(self, note_id: str):
        """Handle grammar note selection."""
        note = self.app.content.get_grammar(note_id)
        if note:
            self.current_note = note
            self._show_note(note)

    def _show_note(self, note: GrammarNote):
        """Display a grammar note."""
        self.content_box.set_title(note.title)
        self.content_text.set_text(note.content)


class QuizScreen(urwid.WidgetWrap):
    """Screen for flashcard quiz."""

    def __init__(self, app):
        self.app = app
        self.words = []
        self.current_index = 0
        self.revealed = False

        # Quiz display
        self.word_text = urwid.Text("", align="center")
        self.word_display = urwid.AttrMap(self.word_text, "quiz_word")

        self.hint_text = urwid.Text("[Space] to reveal", align="center")
        self.hint_display = urwid.AttrMap(self.hint_text, "quiz_hint")

        self.translation_text = urwid.Text("", align="center")
        self.translation_display = urwid.AttrMap(self.translation_text, "quiz_translation")

        self.progress_text = urwid.Text("", align="center")

        # Layout
        pile = urwid.Pile([
            urwid.Divider(),
            urwid.Divider(),
            self.word_display,
            urwid.Divider(),
            self.hint_display,
            urwid.Divider(),
            self.translation_display,
            urwid.Divider(),
            urwid.Divider(),
            self.progress_text,
        ])

        filler = urwid.Filler(pile, valign="middle")
        box = urwid.LineBox(filler, title="Quiz")

        super().__init__(box)

    def start_quiz(self, count: int = 10):
        """Start a new quiz session."""
        self.words = self.app.vocabulary.get_quiz_words(count)
        self.current_index = 0
        self.revealed = False

        if not self.words:
            self.word_text.set_text("No words to quiz!")
            self.hint_text.set_text("Add words with translations first")
            self.translation_text.set_text("")
            self.progress_text.set_text("")
        else:
            self._show_current()

    def _show_current(self):
        """Show the current word."""
        if self.current_index >= len(self.words):
            self._show_complete()
            return

        word = self.words[self.current_index]
        self.word_text.set_text(word.word)

        if self.revealed:
            self.translation_text.set_text(word.translation or "?")
            self.hint_text.set_text("[k]now it  [a]gain  [n]ext  [q]uit")
        else:
            self.translation_text.set_text("")
            self.hint_text.set_text("[Space] to reveal")

        self.progress_text.set_text(f"{self.current_index + 1} / {len(self.words)}")

    def _show_complete(self):
        """Show quiz completion."""
        self.word_text.set_text("Quiz Complete!")
        self.hint_text.set_text("[r]estart  [q]uit")
        self.translation_text.set_text("")
        self.progress_text.set_text(f"Reviewed {len(self.words)} words")

    def keypress(self, size, key):
        if not self.words:
            if key == "q":
                self.app.switch_tab(0)  # Back to texts
                return None
            return key

        if self.current_index >= len(self.words):
            # Quiz complete
            if key == "r":
                self.start_quiz()
                return None
            elif key == "q":
                self.app.switch_tab(0)
                return None
            return key

        if not self.revealed:
            if key == " ":
                self.revealed = True
                self._show_current()
                return None
        else:
            word = self.words[self.current_index]
            if key == "k":
                # Mark as known, move to next
                self.app.vocabulary.mark_known(word.word)
                self._next_word()
                return None
            elif key == "a":
                # Again - demote if known, keep if learning
                if word.stage == WordStage.KNOWN:
                    self.app.vocabulary.mark_learning(word.word)
                self._next_word()
                return None
            elif key == "n":
                # Just move to next
                self._next_word()
                return None

        if key == "q":
            self.app.switch_tab(0)
            return None

        return key

    def _next_word(self):
        """Move to the next word."""
        self.current_index += 1
        self.revealed = False
        self._show_current()


class GenerateScreen(urwid.WidgetWrap):
    """Screen for AI content generation."""

    def __init__(self, app):
        self.app = app

        # Options
        self.content_type = "text"  # text, wordlist, grammar
        self.topic_edit = urwid.Edit("Topic: ")
        self.status_text = urwid.Text("")

        # Type buttons
        text_btn = urwid.Button("Text")
        wordlist_btn = urwid.Button("Word List")
        grammar_btn = urwid.Button("Grammar")

        urwid.connect_signal(text_btn, "click", lambda b: self._set_type("text"))
        urwid.connect_signal(wordlist_btn, "click", lambda b: self._set_type("wordlist"))
        urwid.connect_signal(grammar_btn, "click", lambda b: self._set_type("grammar"))

        type_row = urwid.Columns([
            urwid.AttrMap(text_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(wordlist_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(grammar_btn, "button", focus_map="button_focus"),
        ], dividechars=2)

        # Generate button
        gen_btn = urwid.Button("Generate [Enter]")
        urwid.connect_signal(gen_btn, "click", lambda b: self._generate())

        # Layout
        pile = urwid.Pile([
            urwid.Text("Generate Content", align="center"),
            urwid.Divider(),
            urwid.Text("Content Type:"),
            type_row,
            urwid.Divider(),
            self.topic_edit,
            urwid.Divider(),
            urwid.AttrMap(gen_btn, "button", focus_map="button_focus"),
            urwid.Divider(),
            self.status_text,
        ])

        filler = urwid.Filler(pile, valign="top")
        box = urwid.LineBox(filler, title="Generate")

        super().__init__(box)

    def _set_type(self, content_type: str):
        """Set the content type to generate."""
        self.content_type = content_type
        self.status_text.set_text(f"Selected: {content_type}")

    def _generate(self):
        """Generate content."""
        topic = self.topic_edit.edit_text.strip()
        if not topic:
            self.status_text.set_text("Please enter a topic")
            return

        if not self.app.generator:
            self.status_text.set_text("AI not configured - check config.yaml")
            return

        self.status_text.set_text("Generating...")

        try:
            if self.content_type == "text":
                content = self.app.generator.generate_text(topic)
                self.app.content.save_text(content)
                self.status_text.set_text(f"Created text: {content.title}")
            elif self.content_type == "wordlist":
                content = self.app.generator.generate_wordlist(topic)
                self.app.content.save_wordlist(content)
                self.status_text.set_text(f"Created word list: {content.title}")
            elif self.content_type == "grammar":
                content = self.app.generator.generate_grammar_note(topic)
                self.app.content.save_grammar(content)
                self.status_text.set_text(f"Created grammar note: {content.title}")

            self.topic_edit.edit_text = ""

        except Exception as e:
            self.status_text.set_text(f"Error: {str(e)}")

    def keypress(self, size, key):
        if key == "enter":
            self._generate()
            return None
        return super().keypress(size, key)
