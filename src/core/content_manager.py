"""Content management for texts, word lists, and grammar notes."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.core.models import Text, WordList, GrammarNote, WordEntry
from src.storage.files import TextStorage, WordListStorage, GrammarStorage
from src.storage.database import Database


@dataclass
class ContentSummary:
    """Summary of content item for display in lists."""
    id: str
    title: str
    subtitle: str  # e.g., difficulty, theme, tag count


class ContentManager:
    """Unified manager for all content types."""

    def __init__(
        self,
        texts_dir: str | Path,
        wordlists_dir: str | Path,
        grammar_dir: str | Path,
        database: Database,
    ):
        self.texts = TextStorage(texts_dir)
        self.wordlists = WordListStorage(wordlists_dir)
        self.grammar = GrammarStorage(grammar_dir)
        self.db = database

    # Text operations

    def list_texts(self) -> list[ContentSummary]:
        """List all texts with summaries."""
        return [
            ContentSummary(
                id=t.id,
                title=t.title,
                subtitle=t.difficulty,
            )
            for t in self.texts.list_all()
        ]

    def get_text(self, id: str) -> Optional[Text]:
        """Get a text by ID."""
        return self.texts.get(id)

    def save_text(self, text: Text) -> None:
        """Save a text."""
        self.texts.save(text)

    def delete_text(self, id: str) -> bool:
        """Delete a text."""
        return self.texts.delete(id)

    def record_text_read(self, text_id: str) -> None:
        """Record that a text was read."""
        self.db.record_text_read(text_id)

    # Word list operations

    def list_wordlists(self) -> list[ContentSummary]:
        """List all word lists with summaries."""
        return [
            ContentSummary(
                id=w.id,
                title=w.title,
                subtitle=f"{w.theme} ({len(w.words)} words)",
            )
            for w in self.wordlists.list_all()
        ]

    def get_wordlist(self, id: str) -> Optional[WordList]:
        """Get a word list by ID."""
        return self.wordlists.get(id)

    def save_wordlist(self, wordlist: WordList) -> None:
        """Save a word list."""
        self.wordlists.save(wordlist)

    def delete_wordlist(self, id: str) -> bool:
        """Delete a word list."""
        return self.wordlists.delete(id)

    def add_word_to_list(
        self,
        wordlist_id: str,
        word: str,
        translation: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Add a word to an existing word list."""
        wordlist = self.wordlists.get(wordlist_id)
        if not wordlist:
            return False

        # Check if word already exists
        if any(w.word.lower() == word.lower() for w in wordlist.words):
            return False

        wordlist.words.append(WordEntry(word=word, translation=translation, notes=notes))
        self.wordlists.save(wordlist)
        return True

    # Grammar operations

    def list_grammar(self) -> list[ContentSummary]:
        """List all grammar notes with summaries."""
        return [
            ContentSummary(
                id=g.id,
                title=g.title,
                subtitle=", ".join(g.tags[:3]) if g.tags else "no tags",
            )
            for g in self.grammar.list_all()
        ]

    def get_grammar(self, id: str) -> Optional[GrammarNote]:
        """Get a grammar note by ID."""
        return self.grammar.get(id)

    def save_grammar(self, grammar: GrammarNote) -> None:
        """Save a grammar note."""
        self.grammar.save(grammar)

    def delete_grammar(self, id: str) -> bool:
        """Delete a grammar note."""
        return self.grammar.delete(id)

    # Import from word lists to vocabulary

    def import_wordlist_to_vocabulary(
        self,
        wordlist_id: str,
        vocabulary,  # VocabularyManager - avoiding circular import
    ) -> int:
        """Import all words from a word list to vocabulary. Returns count."""
        wordlist = self.wordlists.get(wordlist_id)
        if not wordlist:
            return 0

        count = 0
        for entry in wordlist.words:
            vocabulary.set_translation(entry.word, entry.translation, entry.notes)
            count += 1

        return count

    # Translation lookup

    def lookup_translation(self, word: str) -> Optional[str]:
        """
        Look up translation for a word from word lists.
        Returns translation string or None if not found.
        """
        word_lower = word.lower()
        for wordlist in self.wordlists.list_all():
            for entry in wordlist.words:
                if entry.word.lower() == word_lower:
                    return entry.translation
        return None
