"""Main application entry point."""

import os
from pathlib import Path
from typing import Optional

import urwid
import yaml

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from src.core.vocabulary import VocabularyManager
from src.core.content_manager import ContentManager
from src.storage.database import Database
from src.ai.base import AIProvider
from src.ai.anthropic import AnthropicProvider
from src.ai.openai import OpenAIProvider
from src.ai.generator import ContentGenerator
from src.ui.theme import PALETTE
from src.ui.widgets import TabBar, StatusBar
from src.ui.screens import TextScreen, WordListScreen, GrammarScreen, QuizScreen, GenerateScreen


class App:
    """Main application class."""

    TAB_NAMES = ["Texts", "Words", "Grammar", "Quiz", "Generate"]

    def __init__(self, config_path: Optional[str] = None):
        # Load config
        self.config = self._load_config(config_path)

        # Initialize storage
        data_config = self.config.get("data", {})
        base_path = Path(data_config.get("base_path", "data"))

        self.db = Database(base_path / data_config.get("database", "ukr.db"))

        # Initialize core services
        self.vocabulary = VocabularyManager(self.db)
        self.content = ContentManager(
            texts_dir=base_path / data_config.get("texts_dir", "texts"),
            wordlists_dir=base_path / data_config.get("wordlists_dir", "wordlists"),
            grammar_dir=base_path / data_config.get("grammar_dir", "grammar"),
            database=self.db,
        )

        # Initialize AI (optional)
        self.generator = self._init_generator()

        # Initialize UI
        self._init_ui()

    def _load_config(self, config_path: Optional[str]) -> dict:
        """Load configuration from file."""
        paths_to_try = [
            config_path,
            "config.yaml",
            os.path.expanduser("~/.config/ukr/config.yaml"),
        ]

        for path in paths_to_try:
            if path and os.path.exists(path):
                with open(path, "r") as f:
                    return yaml.safe_load(f) or {}

        # Return defaults
        return {
            "data": {
                "base_path": "data",
                "texts_dir": "texts",
                "wordlists_dir": "wordlists",
                "grammar_dir": "grammar",
                "database": "ukr.db",
            }
        }

    def _init_generator(self) -> Optional[ContentGenerator]:
        """Initialize AI content generator if configured."""
        ai_config = self.config.get("ai", {})
        default_provider = ai_config.get("default_provider")

        provider: Optional[AIProvider] = None

        # Try to initialize based on config or auto-detect from env vars
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
        openai_key = os.environ.get("OPENAI_API_KEY")

        # Check config overrides
        anthropic_config = ai_config.get("anthropic", {})
        if anthropic_config.get("api_key"):
            anthropic_key = anthropic_config["api_key"]

        openai_config = ai_config.get("openai", {})
        if openai_config.get("api_key"):
            openai_key = openai_config["api_key"]

        # Filter out placeholder values
        if anthropic_key == "your-anthropic-api-key-here":
            anthropic_key = None
        if openai_key == "your-openai-api-key-here":
            openai_key = None

        # Use configured default, or auto-detect
        if default_provider == "anthropic" and anthropic_key:
            provider = AnthropicProvider(
                api_key=anthropic_key,
                model=anthropic_config.get("model", "claude-3-haiku-20240307"),
            )
        elif default_provider == "openai" and openai_key:
            provider = OpenAIProvider(
                api_key=openai_key,
                model=openai_config.get("model", "gpt-4o-mini"),
            )
        elif anthropic_key:
            # Auto-detect: prefer Anthropic if available
            provider = AnthropicProvider(
                api_key=anthropic_key,
                model=anthropic_config.get("model", "claude-3-haiku-20240307"),
            )
        elif openai_key:
            # Fall back to OpenAI
            provider = OpenAIProvider(
                api_key=openai_key,
                model=openai_config.get("model", "gpt-4o-mini"),
            )

        if provider and provider.is_available():
            return ContentGenerator(provider)
        return None

    def _init_ui(self):
        """Initialize the UI components."""
        # Tab bar
        self.tab_bar = TabBar(self.TAB_NAMES, on_tab_change=self._on_tab_change)

        # Screens
        self.text_screen = TextScreen(self)
        self.wordlist_screen = WordListScreen(self)
        self.grammar_screen = GrammarScreen(self)
        self.quiz_screen = QuizScreen(self)
        self.generate_screen = GenerateScreen(self)

        self.screens = [
            self.text_screen,
            self.wordlist_screen,
            self.grammar_screen,
            self.quiz_screen,
            self.generate_screen,
        ]

        # Status bar
        self.status_bar = StatusBar()

        # Main layout
        self.body = urwid.WidgetPlaceholder(self.screens[0])
        self.update_status()

        self.frame = urwid.Frame(
            header=self.tab_bar,
            body=self.body,
            footer=self.status_bar,
        )

        # Refresh initial data
        self._refresh_current_screen()

    def _on_tab_change(self, index: int):
        """Handle tab change."""
        self.body.original_widget = self.screens[index]
        self._refresh_current_screen()
        self.update_status()

    def _refresh_current_screen(self):
        """Refresh data for the current screen."""
        current = self.body.original_widget

        if current == self.text_screen:
            self.text_screen.refresh_list()
        elif current == self.wordlist_screen:
            self.wordlist_screen.refresh_list()
        elif current == self.grammar_screen:
            self.grammar_screen.refresh_list()
        elif current == self.quiz_screen:
            self.quiz_screen.start_quiz()

    def switch_tab(self, index: int):
        """Switch to a specific tab."""
        self.tab_bar.set_active(index)

    def lookup_translation(self, word: str) -> Optional[str]:
        """Look up translation for a word from vocabulary DB or word lists."""
        # First check vocabulary database
        vocab_word = self.vocabulary.get_word(word)
        if vocab_word and vocab_word.translation:
            return vocab_word.translation

        # Fall back to word lists
        return self.content.lookup_translation(word)

    def update_status(self):
        """Update the status bar based on current state."""
        current = self.body.original_widget
        stats = self.vocabulary.get_stats()

        base_status = f"Known: {stats.get('known', 0)} | Learning: {stats.get('learning', 0)}"

        if current == self.text_screen:
            selected = self.text_screen.get_selected_words()
            current_word = self.text_screen.get_current_word()

            if selected:
                # Show translation(s) for selected words
                if len(selected) == 1:
                    word = selected[0]
                    translation = self.lookup_translation(word)
                    if translation:
                        trans_text = f'"{word}" = {translation}'
                    else:
                        trans_text = f'"{word}" (no translation)'
                else:
                    # Multiple words - show translations for up to 3
                    trans_parts = []
                    for w in selected[:3]:
                        t = self.lookup_translation(w)
                        trans_parts.append(f"{w}={t}" if t else f"{w}=?")
                    trans_text = ", ".join(trans_parts)
                    if len(selected) > 3:
                        trans_text += f" (+{len(selected)-3} more)"

                hint = f" | {trans_text} | [k]nown [l]earning [t]ranslate [p]ronounce [Esc]clear"
            elif current_word:
                # Show current word under cursor
                translation = self.lookup_translation(current_word)
                if translation:
                    trans_text = f'"{current_word}" = {translation}'
                else:
                    trans_text = f'"{current_word}"'
                hint = f" | {trans_text} | [Space]select [p]ronounce | arrows/C-f/b/n/p to navigate"
            else:
                hint = " | arrows/C-f/b/n/p to navigate | [Space]select | [q]uit"
            self.status_bar.set_text(base_status + hint)

        elif current == self.wordlist_screen:
            selected = self.wordlist_screen.selected_words
            if selected:
                hint = f" | Selected: {len(selected)} | [k]nown [l]earning [i]mport all [Esc]clear"
            else:
                hint = " | Space/click to select | [i]mport all to vocabulary | [q]uit"
            self.status_bar.set_text(base_status + hint)

        elif current == self.grammar_screen:
            self.status_bar.set_text(base_status + " | [q]uit")

        elif current == self.quiz_screen:
            self.status_bar.set_text("[Space]reveal [k]now [a]gain [n]ext [q]uit")

        elif current == self.generate_screen:
            ai_status = "AI: ready" if self.generator else "AI: not configured"
            self.status_bar.set_text(f"{base_status} | {ai_status} | [Enter]generate [q]uit")

    def show_message(self, message: str):
        """Show a temporary message in the status bar."""
        self.status_bar.set_text(message)

    def handle_input(self, key):
        """Handle global key input."""

        # Handle tuple keys (special keys) - ignore them
        if not isinstance(key, str):
            return

        if key in ("q", "Q"):
            raise urwid.ExitMainLoop()

        # Number keys for tab switching
        if key in "12345":
            self.switch_tab(int(key) - 1)
            return

        # Tab key cycles through tabs
        if key == "tab":
            current = self.tab_bar.active_tab
            self.switch_tab((current + 1) % len(self.TAB_NAMES))
            return

        # ? for help
        if key == "?":
            self._show_help()
            return

    def _show_help(self):
        """Show help overlay."""
        help_text = """
Ukrainian Language Learning App

Navigation:
  1-5, Tab    Switch between tabs
  ↑/↓         Navigate lists
  Enter       Select item
  q           Quit

Text View:
  Click/Space Select words
  k           Mark selected as Known
  l           Mark selected as Learning
  t           Translate selected words
  p/P         Pronounce (normal/slow)
  i           Show detailed word info
  v           Show text vocabulary
  n           Add new text (paste)
  e           Edit current text
  Esc         Clear selection

Word Lists:
  i           Import list to vocabulary

Quiz:
  Space       Reveal translation
  k           Know it (promote to Known)
  a           Again (keep/demote)
  n           Next word

Press any key to close...
"""
        text = urwid.Text(help_text)
        filler = urwid.Filler(text, valign="top")
        box = urwid.LineBox(filler, title="Help")
        overlay = urwid.Overlay(
            box,
            self.frame,
            align="center",
            width=60,
            valign="middle",
            height=25,
        )

        def close_help(key):
            self.loop.widget = self.frame
            return True

        self.loop.widget = overlay
        self.loop.unhandled_input = close_help

    def show_word_info(self, word_or_phrase: str, is_phrase: bool = False):
        """Show detailed word/phrase info in an overlay.

        Checks cache first, falls back to AI generation.
        """
        # Check cache first
        cached = self.db.get_word_info(word_or_phrase)

        if cached:
            content = cached
        elif self.generator:
            # Generate via AI
            self.show_message(f"Looking up '{word_or_phrase}'...")
            try:
                if is_phrase:
                    content = self.generator.get_phrase_info(word_or_phrase)
                else:
                    content = self.generator.get_word_info(word_or_phrase)

                # Cache the result
                info_type = "phrase" if is_phrase else "word"
                self.db.save_word_info(word_or_phrase, info_type, content)
            except Exception as e:
                self.show_message(f"Error: {e}")
                return
        else:
            self.show_message("AI not configured - cannot look up word info")
            return

        # Display in overlay
        text = urwid.Text(content)
        walker = urwid.SimpleFocusListWalker([text])
        listbox = urwid.ListBox(walker)
        box = urwid.LineBox(listbox, title=f"Info: {word_or_phrase}")

        overlay = urwid.Overlay(
            box,
            self.frame,
            align="center",
            width=("relative", 80),
            valign="middle",
            height=("relative", 80),
        )

        def close_info(key):
            if key in ("q", "Q", "esc", "escape"):
                self.loop.widget = self.frame
                self.loop.unhandled_input = self.handle_input
                self.update_status()
                return True
            return False

        self.loop.widget = overlay
        self.loop.unhandled_input = close_info

    def show_add_text_dialog(self):
        """Show dialog to paste and add a new text."""
        # Input fields
        title_edit = urwid.Edit("Title: ")
        content_edit = urwid.Edit("", multiline=True)
        difficulty_text = urwid.Text("Difficulty: beginner")

        difficulties = ["beginner", "intermediate", "advanced"]
        current_difficulty = [0]  # Use list to allow mutation in nested function

        def do_save(button=None):
            title = title_edit.edit_text.strip()
            content = content_edit.edit_text.strip()

            if not title:
                self.show_message("Title is required")
                return

            if not content:
                self.show_message("Content is required")
                return

            # Create and save the text
            from src.core.models import Text
            text = Text.create(
                title=title,
                content=content,
                difficulty=difficulties[current_difficulty[0]],
                tags=["imported"],
                source="pasted",
            )
            self.content.save_text(text)

            # Close dialog and refresh
            self.loop.widget = self.frame
            self.loop.unhandled_input = self.handle_input
            self.text_screen.refresh_list()
            self.show_message(f"Added: {title}")

        def do_cancel(button=None):
            self.loop.widget = self.frame
            self.loop.unhandled_input = self.handle_input
            self.update_status()

        def cycle_difficulty(button=None):
            current_difficulty[0] = (current_difficulty[0] + 1) % len(difficulties)
            difficulty_text.set_text(f"Difficulty: {difficulties[current_difficulty[0]]}")

        # Buttons
        save_btn = urwid.Button("Save", on_press=do_save)
        cancel_btn = urwid.Button("Cancel", on_press=do_cancel)
        diff_btn = urwid.Button("Cycle Difficulty", on_press=cycle_difficulty)

        buttons = urwid.Columns([
            urwid.AttrMap(save_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(diff_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(cancel_btn, "button", focus_map="button_focus"),
        ], dividechars=2)

        # Layout
        pile = urwid.Pile([
            urwid.Text("Paste Ukrainian text. Use Tab to move between fields.", align="center"),
            urwid.Divider(),
            urwid.Text("Title:"),
            urwid.AttrMap(title_edit, "list_item_focus"),
            urwid.Divider(),
            difficulty_text,
            urwid.Divider(),
            urwid.Text("Content:"),
            urwid.BoxAdapter(urwid.Filler(urwid.AttrMap(content_edit, "list_item_focus"), valign="top"), height=15),
            urwid.Divider(),
            buttons,
        ])

        box = urwid.LineBox(urwid.Padding(pile, left=1, right=1), title="Add New Text")

        overlay = urwid.Overlay(
            box,
            self.frame,
            align="center",
            width=("relative", 85),
            valign="middle",
            height=("relative", 80),
        )

        def handle_input(key):
            if key == "esc":
                do_cancel()
                return True
            return False

        self.loop.widget = overlay
        self.loop.unhandled_input = handle_input

    def show_edit_text_dialog(self, text):
        """Show dialog to edit an existing text."""
        from src.core.models import Text

        # Input fields - pre-populated with existing data
        title_edit = urwid.Edit("", text.title)
        content_edit = urwid.Edit("", text.content, multiline=True)

        difficulties = ["beginner", "intermediate", "advanced"]
        try:
            current_difficulty = [difficulties.index(text.difficulty)]
        except ValueError:
            current_difficulty = [0]

        difficulty_text = urwid.Text(f"Difficulty: {difficulties[current_difficulty[0]]}")

        def do_save(button=None):
            title = title_edit.edit_text.strip()
            content = content_edit.edit_text.strip()

            if not title:
                self.show_message("Title is required")
                return

            if not content:
                self.show_message("Content is required")
                return

            # Update the text (preserve ID, created_at, source)
            updated_text = Text(
                id=text.id,
                title=title,
                content=content,
                difficulty=difficulties[current_difficulty[0]],
                tags=text.tags,
                created_at=text.created_at,
                source=text.source,
            )
            self.content.save_text(updated_text)

            # Close dialog and refresh
            self.loop.widget = self.frame
            self.loop.unhandled_input = self.handle_input
            self.text_screen.refresh_list()
            # Re-select the text to show updated content
            self.text_screen._on_text_select(text.id)
            self.show_message(f"Updated: {title}")

        def do_cancel(button=None):
            self.loop.widget = self.frame
            self.loop.unhandled_input = self.handle_input
            self.update_status()

        def cycle_difficulty(button=None):
            current_difficulty[0] = (current_difficulty[0] + 1) % len(difficulties)
            difficulty_text.set_text(f"Difficulty: {difficulties[current_difficulty[0]]}")

        # Buttons
        save_btn = urwid.Button("Save", on_press=do_save)
        cancel_btn = urwid.Button("Cancel", on_press=do_cancel)
        diff_btn = urwid.Button("Cycle Difficulty", on_press=cycle_difficulty)

        buttons = urwid.Columns([
            urwid.AttrMap(save_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(diff_btn, "button", focus_map="button_focus"),
            urwid.AttrMap(cancel_btn, "button", focus_map="button_focus"),
        ], dividechars=2)

        # Layout
        pile = urwid.Pile([
            urwid.Text("Edit text. Paste to add content. Use Tab to move.", align="center"),
            urwid.Divider(),
            urwid.Text("Title:"),
            urwid.AttrMap(title_edit, "list_item_focus"),
            urwid.Divider(),
            difficulty_text,
            urwid.Divider(),
            urwid.Text("Content:"),
            urwid.BoxAdapter(urwid.Filler(urwid.AttrMap(content_edit, "list_item_focus"), valign="top"), height=15),
            urwid.Divider(),
            buttons,
        ])

        box = urwid.LineBox(urwid.Padding(pile, left=1, right=1), title=f"Edit: {text.title[:40]}")

        overlay = urwid.Overlay(
            box,
            self.frame,
            align="center",
            width=("relative", 85),
            valign="middle",
            height=("relative", 80),
        )

        def handle_input(key):
            if key == "esc":
                do_cancel()
                return True
            return False

        self.loop.widget = overlay
        self.loop.unhandled_input = handle_input

    def show_text_vocabulary(self, text):
        """Show vocabulary list for a text with translations.

        Uses AI analysis to group inflected forms under lemmas.
        Results are cached per text.
        """
        from src.core.text_processor import TextProcessor

        processor = TextProcessor()
        # Get unique words
        words = sorted(set(processor.extract_words(text.content)))

        if not words:
            self.show_message("No words found in text")
            return

        # Check cache first
        cache_key = f"text_vocab:{text.id}"
        cached = self.db.get_word_info(cache_key)

        if cached:
            # Use cached analysis
            content = self._format_vocab_display(cached, words)
        elif self.generator:
            # Generate via AI
            self.show_message(f"Analyzing vocabulary ({len(words)} words)...")
            try:
                analysis = self.generator.analyze_text_vocabulary(words)
                # Cache the result
                self.db.save_word_info(cache_key, "text_vocab", analysis)
                content = self._format_vocab_display(analysis, words)
            except Exception as e:
                self.show_message(f"Error: {e}")
                return
        else:
            # No AI - fall back to simple list
            content = self._format_simple_vocab(words)

        # Display in scrollable overlay
        text_widget = urwid.Text(content)
        walker = urwid.SimpleFocusListWalker([text_widget])
        listbox = urwid.ListBox(walker)
        box = urwid.LineBox(listbox, title=f"Vocabulary: {text.title[:40]}")

        overlay = urwid.Overlay(
            box,
            self.frame,
            align="center",
            width=("relative", 80),
            valign="middle",
            height=("relative", 85),
        )

        def close_vocab(key):
            if key in ("q", "Q", "esc", "escape", "v"):
                self.loop.widget = self.frame
                self.loop.unhandled_input = self.handle_input
                self.update_status()
                return True
            return False

        self.loop.widget = overlay
        self.loop.unhandled_input = close_vocab

    def _format_vocab_display(self, analysis: str, words: list[str]) -> str:
        """Format AI vocabulary analysis for display with stage markers."""
        known_words = self.vocabulary.get_known_words()
        learning_words = self.vocabulary.get_learning_words()

        # Count unique lemmas and words
        lemma_count = 0
        lines = []

        for line in analysis.strip().split("\n"):
            line = line.strip()
            if not line or "|" not in line:
                continue

            lemma_count += 1
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                lemma = parts[0]
                translation = parts[1]
                pos = parts[2]
                forms = parts[3] if len(parts) > 3 else ""

                # Determine stage based on lemma (normalized)
                lemma_lower = lemma.lower()
                if lemma_lower in known_words:
                    stage_mark = "[K]"
                elif lemma_lower in learning_words:
                    stage_mark = "[L]"
                else:
                    stage_mark = "[N]"

                # Format: [K] кіт (noun m) — cat
                #         forms: кота, коти, коту
                entry = f"{stage_mark} {lemma} ({pos}) — {translation}"
                if forms:
                    # Clean up "forms:" prefix if present
                    forms = forms.replace("forms:", "").strip()
                    if forms:
                        entry += f"\n    └ {forms}"
                lines.append(entry)

        # Count stats based on lemmas in the analysis
        known_count = sum(1 for line in lines if line.startswith("[K]"))
        learning_count = sum(1 for line in lines if line.startswith("[L]"))
        new_count = lemma_count - known_count - learning_count

        header = f"Lemmas: {lemma_count} | Known: {known_count} | Learning: {learning_count} | New: {new_count}\n"
        header += f"(from {len(words)} word forms in text)\n"
        header += "─" * 55 + "\n\n"

        return header + "\n".join(lines)

    def _format_simple_vocab(self, words: list[str]) -> str:
        """Format simple vocabulary list without AI analysis."""
        known_words = self.vocabulary.get_known_words()
        learning_words = self.vocabulary.get_learning_words()

        lines = []
        for word in words:
            translation = self.lookup_translation(word)
            trans_str = translation if translation else "?"

            if word in known_words:
                stage_mark = "[K]"
            elif word in learning_words:
                stage_mark = "[L]"
            else:
                stage_mark = "[N]"

            lines.append(f"{stage_mark} {word} — {trans_str}")

        known_count = sum(1 for w in words if w in known_words)
        learning_count = sum(1 for w in words if w in learning_words)
        new_count = len(words) - known_count - learning_count

        header = f"Words: {len(words)} | Known: {known_count} | Learning: {learning_count} | New: {new_count}\n"
        header += "(AI not configured - showing raw word forms)\n"
        header += "─" * 50 + "\n\n"

        return header + "\n".join(lines)

    def run(self):
        """Run the application."""
        self.loop = urwid.MainLoop(
            self.frame,
            palette=PALETTE,
            unhandled_input=self.handle_input,
            handle_mouse=True,
        )

        try:
            self.loop.run()
        except KeyboardInterrupt:
            pass


def main():
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Ukrainian Language Learning App")
    parser.add_argument(
        "-c", "--config",
        help="Path to config file",
        default=None,
    )
    args = parser.parse_args()

    app = App(config_path=args.config)
    app.run()


if __name__ == "__main__":
    main()
