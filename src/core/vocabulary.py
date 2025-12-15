"""Vocabulary management for tracking learned words."""

from typing import Optional

from src.core.models import Word, WordStage
from src.storage.database import Database


class VocabularyManager:
    """Manages user's vocabulary with word stages."""

    def __init__(self, database: Database):
        self.db = database
        # Cache known and learning words for fast lookup
        self._known_cache: set[str] | None = None
        self._learning_cache: set[str] | None = None

    def _invalidate_cache(self):
        """Invalidate the word caches."""
        self._known_cache = None
        self._learning_cache = None

    def get_known_words(self) -> set[str]:
        """Get set of known words (cached for performance)."""
        if self._known_cache is None:
            self._known_cache = self.db.get_known_words_set()
        return self._known_cache

    def get_learning_words(self) -> set[str]:
        """Get set of learning words (cached for performance)."""
        if self._learning_cache is None:
            self._learning_cache = self.db.get_learning_words_set()
        return self._learning_cache

    def get_stage(self, word: str) -> WordStage:
        """Get the learning stage for a word."""
        word_lower = word.lower()
        if word_lower in self.get_known_words():
            return WordStage.KNOWN
        if word_lower in self.get_learning_words():
            return WordStage.LEARNING
        return WordStage.NEW

    def get_word(self, word: str) -> Optional[Word]:
        """Get full word data including translation."""
        return self.db.get_word(word)

    def set_stage(self, word: str, stage: WordStage) -> None:
        """Set the learning stage for a word."""
        self.db.set_word_stage(word, stage)
        self._invalidate_cache()

    def bulk_set_stage(self, words: list[str], stage: WordStage) -> None:
        """Set stage for multiple words at once."""
        self.db.bulk_set_stage(words, stage)
        self._invalidate_cache()

    def mark_known(self, word: str) -> None:
        """Mark a word as known."""
        self.set_stage(word, WordStage.KNOWN)

    def mark_learning(self, word: str) -> None:
        """Mark a word as learning."""
        self.set_stage(word, WordStage.LEARNING)

    def set_translation(
        self, word: str, translation: str, notes: Optional[str] = None
    ) -> None:
        """Set translation for a word."""
        self.db.set_word_translation(word, translation, notes)

    def add_word(self, word: Word) -> None:
        """Add a word with full details."""
        self.db.save_word(word)
        self._invalidate_cache()

    def get_words_by_stage(self, stage: WordStage) -> list[Word]:
        """Get all words with a specific stage."""
        return self.db.get_words_by_stage(stage)

    def get_all_words(self) -> list[Word]:
        """Get all words in vocabulary."""
        return self.db.get_all_words()

    def get_quiz_words(self, count: int = 10) -> list[Word]:
        """Get words for quiz, prioritizing learning stage."""
        learning = self.db.get_words_by_stage(WordStage.LEARNING)
        known = self.db.get_words_by_stage(WordStage.KNOWN)

        # Filter to words that have translations
        learning = [w for w in learning if w.translation]
        known = [w for w in known if w.translation]

        # Prioritize learning words, fill with known for review
        result = learning[:count]
        if len(result) < count:
            result.extend(known[:count - len(result)])

        return result

    def get_stats(self) -> dict[str, int]:
        """Get vocabulary statistics."""
        return self.db.get_vocabulary_stats()

    def delete_word(self, word: str) -> bool:
        """Remove a word from vocabulary."""
        result = self.db.delete_word(word)
        if result:
            self._invalidate_cache()
        return result
