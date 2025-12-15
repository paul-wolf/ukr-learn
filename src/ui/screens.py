"""Screen compositions for different app views."""

import urwid

from src.core.models import Text, WordList, GrammarNote, WordStage
from src.core.tts import get_tts, TTSError
from src.ui.widgets import ListBrowser, AnnotatedTextViewer


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

    def get_selected_words(self) -> list[str]:
        """Get selected words from the text viewer in document order."""
        return self.text_viewer.get_selected_words()

    def get_current_word(self) -> str | None:
        """Get the current word under cursor."""
        return self.text_viewer.get_current_word()

    def clear_selection(self):
        """Clear word selection."""
        self.text_viewer.clear_selection()

    def keypress(self, size, key):
        selected = self.get_selected_words()
        current = self.get_current_word()

        # Note: Navigation keys (arrows, ctrl+f/b/n/p/a/e, space) are handled
        # by App._input_filter() to bypass ListBox key consumption

        if key == "k" and selected:
            # Toggle: if all are known, set to new; otherwise set to known
            all_known = all(
                self.app.vocabulary.get_stage(w) == WordStage.KNOWN
                for w in selected
            )
            if all_known:
                self.app.vocabulary.bulk_set_stage(selected, WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(selected, WordStage.KNOWN)
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
                self.app.vocabulary.bulk_set_stage(selected, WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(selected, WordStage.LEARNING)
                self.app.show_message("Marked as learning")
            self.clear_selection()
            if self.current_text:
                self._show_text(self.current_text)
            return None
        elif key == "t" and selected:
            # Translate selected words via AI
            self._translate_selected(selected)
            return None
        elif key == "p":
            # Pronounce selected words (or current word if none selected)
            words = selected if selected else ([current] if current else [])
            if words:
                self._pronounce_words(words)
            return None
        elif key == "P":
            # Pronounce slowly
            words = selected if selected else ([current] if current else [])
            if words:
                self._pronounce_words(words, slow=True)
            return None
        elif key == "i":
            # Show detailed info for selected/current word(s)
            self._show_word_info()
            return None
        elif key == "n":
            # Add new text (paste)
            self.app.show_add_text_dialog()
            return None
        elif key == "e":
            # Edit current text
            if self.current_text:
                self.app.show_edit_text_dialog(self.current_text)
            else:
                self.app.show_message("No text selected to edit")
            return None
        elif key == "v":
            # Show vocabulary for current text
            if self.current_text:
                self.app.show_text_vocabulary(self.current_text)
            else:
                self.app.show_message("No text selected")
            return None
        elif key == "V":
            # Force refresh vocabulary analysis
            if self.current_text:
                self.app.show_text_vocabulary(self.current_text, force_refresh=True)
            else:
                self.app.show_message("No text selected")
            return None
        elif key == "esc":
            self.clear_selection()
            self.app.update_status()
            return None

        return super().keypress(size, key)

    def _pronounce_words(self, words: list[str], slow: bool = False):
        """Pronounce words using TTS (already in document order)."""
        try:
            tts = get_tts()
            if not tts.is_available():
                self.app.show_message("TTS not available - install gTTS")
                return

            # Words are already in document order
            text = " ".join(words)
            self.app.show_message(f"Speaking: {text}")

            if slow:
                tts.speak_slow(text)
            else:
                tts.speak(text)

        except TTSError as e:
            self.app.show_message(f"TTS error: {e}")

    def _translate_selected(self, selected: list[str]):
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

    def _show_word_info(self):
        """Show detailed info for selected or current word(s)."""
        # Check for contiguous phrase first
        phrase = self.text_viewer.get_selection_as_phrase()
        if phrase and len(phrase.split()) > 1:
            # Multiple contiguous words = phrase
            self.app.show_word_info(phrase, is_phrase=True)
            return

        # Single selected word or current word
        selected = self.text_viewer.get_selected_words_original()
        if selected:
            # Use first selected word
            word = selected[0]
        else:
            # Use current word under cursor
            word = self.text_viewer.get_current_word_original()

        if word:
            self.app.show_word_info(word, is_phrase=False)
        else:
            self.app.show_message("No word selected")


class WordEntryItem(urwid.WidgetWrap):
    """A selectable word entry in a word list."""

    def __init__(self, word: str, translation: str, notes: str | None, stage: WordStage, on_select=None):
        self.word = word
        self.translation = translation
        self.notes = notes
        self.stage = stage
        self.on_select = on_select
        self.selected = False

        self._build()

    def _build(self):
        """Build the widget display."""
        if self.stage == WordStage.KNOWN:
            stage_text = "[K]"
            attr = "known"
        elif self.stage == WordStage.LEARNING:
            stage_text = "[L]"
            attr = "learning"
        else:
            stage_text = "[ ]"
            attr = "new"

        text = f"{stage_text} {self.word} - {self.translation}"
        if self.notes:
            text += f" ({self.notes})"

        if self.selected:
            attr = "selected"

        self.text_widget = urwid.Text(text)
        self._w = urwid.AttrMap(self.text_widget, attr, focus_map="list_item_focus")

    def set_stage(self, stage: WordStage):
        """Update the stage and rebuild."""
        self.stage = stage
        self._build()

    def toggle_selected(self):
        """Toggle selection state."""
        self.selected = not self.selected
        self._build()

    def selectable(self):
        return True

    def keypress(self, size, key):
        if key in (" ", "enter") and self.on_select:
            self.on_select(self)
            return None
        return key

    def mouse_event(self, size, event, button, col, row, focus):
        if event == "mouse press" and button == 1 and self.on_select:
            self.on_select(self)
            return True
        return False


class WordListScreen(urwid.WidgetWrap):
    """Screen for viewing word lists."""

    def __init__(self, app):
        self.app = app
        self.current_list: WordList | None = None
        self.word_items: list[WordEntryItem] = []
        self.selected_words: set[str] = set()

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
            self.selected_words.clear()
            self._show_wordlist(wordlist)

    def _show_wordlist(self, wordlist: WordList):
        """Display a word list."""
        self.word_walker.clear()
        self.word_items.clear()
        self.content_box.set_title(wordlist.title)

        known = self.app.vocabulary.get_known_words()
        learning = self.app.vocabulary.get_learning_words()

        for entry in wordlist.words:
            word_lower = entry.word.lower()
            if word_lower in known:
                stage = WordStage.KNOWN
            elif word_lower in learning:
                stage = WordStage.LEARNING
            else:
                stage = WordStage.NEW

            item = WordEntryItem(
                word=entry.word,
                translation=entry.translation,
                notes=entry.notes,
                stage=stage,
                on_select=self._on_word_select,
            )
            self.word_items.append(item)
            self.word_walker.append(item)

        self.app.update_status()

    def _on_word_select(self, item: WordEntryItem):
        """Handle word entry selection."""
        item.toggle_selected()
        if item.selected:
            self.selected_words.add(item.word.lower())
        else:
            self.selected_words.discard(item.word.lower())
        self.app.update_status()

    def _refresh_stages(self):
        """Refresh stage display for all items."""
        known = self.app.vocabulary.get_known_words()
        learning = self.app.vocabulary.get_learning_words()

        for item in self.word_items:
            word_lower = item.word.lower()
            if word_lower in known:
                item.set_stage(WordStage.KNOWN)
            elif word_lower in learning:
                item.set_stage(WordStage.LEARNING)
            else:
                item.set_stage(WordStage.NEW)

    def keypress(self, size, key):
        if key == "i" and self.current_list:
            # Import word list to vocabulary
            count = self.app.content.import_wordlist_to_vocabulary(
                self.current_list.id,
                self.app.vocabulary,
            )
            self._refresh_stages()
            self.app.show_message(f"Imported {count} words to vocabulary")
            return None

        if key == "k" and self.selected_words:
            # Toggle known
            all_known = all(
                self.app.vocabulary.get_stage(w) == WordStage.KNOWN
                for w in self.selected_words
            )
            if all_known:
                self.app.vocabulary.bulk_set_stage(list(self.selected_words), WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(list(self.selected_words), WordStage.KNOWN)
                self.app.show_message("Marked as known")
            self._clear_selection()
            self._refresh_stages()
            return None

        if key == "l" and self.selected_words:
            # Toggle learning
            all_learning = all(
                self.app.vocabulary.get_stage(w) == WordStage.LEARNING
                for w in self.selected_words
            )
            if all_learning:
                self.app.vocabulary.bulk_set_stage(list(self.selected_words), WordStage.NEW)
                self.app.show_message("Unmarked (set to new)")
            else:
                self.app.vocabulary.bulk_set_stage(list(self.selected_words), WordStage.LEARNING)
                self.app.show_message("Marked as learning")
            self._clear_selection()
            self._refresh_stages()
            return None

        if key == "p" and self.selected_words:
            # Pronounce selected words
            self._pronounce_selected(slow=False)
            return None

        if key == "P" and self.selected_words:
            # Pronounce slowly
            self._pronounce_selected(slow=True)
            return None

        if key == "esc":
            self._clear_selection()
            return None

        return super().keypress(size, key)

    def _pronounce_selected(self, slow: bool = False):
        """Pronounce selected words using TTS."""
        try:
            tts = get_tts()
            if not tts.is_available():
                self.app.show_message("TTS not available - install gTTS")
                return

            # Get the actual words (not lowercased)
            words_to_speak = []
            for item in self.word_items:
                if item.word.lower() in self.selected_words:
                    words_to_speak.append(item.word)

            text = " ".join(words_to_speak)
            self.app.show_message(f"Speaking: {text}")

            if slow:
                tts.speak_slow(text)
            else:
                tts.speak(text)

        except TTSError as e:
            self.app.show_message(f"TTS error: {e}")

    def _clear_selection(self):
        """Clear all selections."""
        for item in self.word_items:
            if item.selected:
                item.toggle_selected()
        self.selected_words.clear()
        self.app.update_status()


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
            self.hint_text.set_text("[k]now it  [a]gain  [n]ext  [p]ronounce  [q]uit")
        else:
            self.translation_text.set_text("")
            self.hint_text.set_text("[Space] to reveal  [p]ronounce")

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

        # Pronounce current word - works whether revealed or not
        if key == "p":
            self._pronounce_current(slow=False)
            return None
        elif key == "P":
            self._pronounce_current(slow=True)
            return None

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

    def _pronounce_current(self, slow: bool = False):
        """Pronounce the current quiz word."""
        if self.current_index >= len(self.words):
            return

        word = self.words[self.current_index]
        try:
            tts = get_tts()
            if not tts.is_available():
                self.app.show_message("TTS not available - install gTTS")
                return

            if slow:
                tts.speak_slow(word.word)
            else:
                tts.speak(word.word)

        except TTSError as e:
            self.app.show_message(f"TTS error: {e}")


class GenerateScreen(urwid.WidgetWrap):
    """Screen for AI content generation."""

    TYPES = ["text", "wordlist", "grammar"]
    TYPE_NAMES = {"text": "Text", "wordlist": "Word List", "grammar": "Grammar"}

    def __init__(self, app):
        self.app = app

        # Options
        self.content_type = "wordlist"  # text, wordlist, grammar
        self.topic_edit = urwid.Edit("Topic: ")
        self.status_text = urwid.Text("")
        self.type_text = urwid.Text("")

        self._update_type_display()
        self._update_status()

        # Simple layout
        pile = urwid.Pile([
            urwid.Text("GENERATE CONTENT", align="center"),
            urwid.Divider(),
            self.type_text,
            urwid.Divider(),
            urwid.AttrMap(self.topic_edit, "list_item_focus"),
            urwid.Divider(),
            self.status_text,
        ])

        filler = urwid.Filler(pile, valign="top")
        box = urwid.LineBox(filler, title="Generate")

        super().__init__(box)

    def _update_type_display(self):
        """Update the type selection display."""
        parts = []
        for t in self.TYPES:
            name = self.TYPE_NAMES[t]
            if t == self.content_type:
                parts.append(f"[{name}]")
            else:
                parts.append(name)
        self.type_text.set_text(f"Type (Tab to change): {' | '.join(parts)}")

    def _update_status(self):
        """Update status text."""
        ai_status = "ready" if self.app.generator else "NOT CONFIGURED"
        self.status_text.set_text(f"AI: {ai_status} | Tab=change type | Enter=generate")

    def _cycle_type(self):
        """Cycle to next content type."""
        idx = self.TYPES.index(self.content_type)
        self.content_type = self.TYPES[(idx + 1) % len(self.TYPES)]
        self._update_type_display()

    def _generate(self):
        """Generate content."""
        topic = self.topic_edit.edit_text.strip()
        # Remove "Topic: " prefix if present
        if topic.startswith("Topic: "):
            topic = topic[7:]
        topic = topic.strip()

        if not topic:
            self.status_text.set_text("ERROR: Please enter a topic first")
            return

        if not self.app.generator:
            self.status_text.set_text("ERROR: AI not configured - set API key")
            return

        type_name = self.TYPE_NAMES[self.content_type]
        self.status_text.set_text(f"Generating {type_name}...")

        try:
            if self.content_type == "text":
                content = self.app.generator.generate_text(topic)
                self.app.content.save_text(content)
                self.status_text.set_text(f"Created: {content.title}")
            elif self.content_type == "wordlist":
                content = self.app.generator.generate_wordlist(topic)
                self.app.content.save_wordlist(content)
                self.status_text.set_text(f"Created: {content.title}")
            elif self.content_type == "grammar":
                content = self.app.generator.generate_grammar_note(topic)
                self.app.content.save_grammar(content)
                self.status_text.set_text(f"Created: {content.title}")

            self.topic_edit.edit_text = "Topic: "

        except Exception as e:
            self.status_text.set_text(f"Error: {str(e)}")

    def keypress(self, size, key):
        # Tab cycles content type
        if key == "tab":
            self._cycle_type()
            return None

        # Enter generates
        if key == "enter":
            self._generate()
            return None

        # Forward other keys to the edit widget
        if len(key) == 1 or key in ('backspace', 'delete', 'left', 'right', 'home', 'end'):
            self.topic_edit.keypress((size[0],), key)
            return None

        return super().keypress(size, key)
