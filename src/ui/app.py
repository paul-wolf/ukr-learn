"""Main application entry point."""

import os
import sys
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
            if selected:
                # Show translation(s) for selected words
                if len(selected) == 1:
                    word = list(selected)[0]
                    translation = self.lookup_translation(word)
                    if translation:
                        trans_text = f'"{word}" = {translation}'
                    else:
                        trans_text = f'"{word}" (no translation)'
                else:
                    # Multiple words - show translations for up to 3
                    trans_parts = []
                    for w in list(selected)[:3]:
                        t = self.lookup_translation(w)
                        trans_parts.append(f"{w}={t}" if t else f"{w}=?")
                    trans_text = ", ".join(trans_parts)
                    if len(selected) > 3:
                        trans_text += f" (+{len(selected)-3} more)"

                hint = f" | {trans_text} | [k]nown [l]earning [t]ranslate [Esc]clear"
            else:
                hint = " | Click words to select | [q]uit"
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
