"""Text processing and Ukrainian tokenization."""

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterator

from src.core.models import WordStage


def strip_accents(text: str) -> str:
    """Remove combining diacritical marks (stress accents) from text.

    Ukrainian learning materials often include stress marks (combining acute accent)
    like "ме́не" which should normalize to "мене" for word matching.
    """
    # Normalize to NFD (decomposed form) so combining marks are separate
    normalized = unicodedata.normalize('NFD', text)
    # Remove combining diacritical marks (category 'Mn' = Mark, Nonspacing)
    stripped = ''.join(c for c in normalized if unicodedata.category(c) != 'Mn')
    # Normalize back to NFC
    return unicodedata.normalize('NFC', stripped)


@dataclass
class Token:
    """A token from text with position information."""
    text: str
    start: int
    end: int
    is_word: bool

    @property
    def normalized(self) -> str:
        """Get normalized (lowercase, accent-stripped) form for lookup."""
        return strip_accents(self.text.lower())


@dataclass
class AnnotatedToken(Token):
    """A token with vocabulary stage annotation."""
    stage: WordStage = WordStage.NEW


@dataclass
class AnnotatedText:
    """Text with annotated tokens."""
    original: str
    tokens: list[AnnotatedToken]

    def get_words(self) -> list[AnnotatedToken]:
        """Get only word tokens."""
        return [t for t in self.tokens if t.is_word]

    def get_unique_words(self) -> set[str]:
        """Get unique normalized words."""
        return {t.normalized for t in self.tokens if t.is_word}


class TextProcessor:
    """Process and tokenize Ukrainian text."""

    # Ukrainian word pattern - includes apostrophe (') and soft sign (ь)
    # Ukrainian alphabet: а-яіїєґ plus apostrophe within words
    # Also includes combining diacritical marks (U+0300-U+036F) for stress accents
    WORD_PATTERN = re.compile(
        r"[а-яіїєґА-ЯІЇЄҐ][а-яіїєґА-ЯІЇЄҐ'ʼ\u0300-\u036f]*",
        re.UNICODE
    )

    def __init__(self):
        pass

    def tokenize(self, text: str) -> list[Token]:
        """
        Tokenize text into words and non-words.

        Returns a list of tokens that, when concatenated, reconstruct
        the original text exactly.
        """
        tokens = []
        last_end = 0

        for match in self.WORD_PATTERN.finditer(text):
            # Add any non-word text before this match
            if match.start() > last_end:
                non_word = text[last_end:match.start()]
                tokens.append(Token(
                    text=non_word,
                    start=last_end,
                    end=match.start(),
                    is_word=False,
                ))

            # Add the word
            tokens.append(Token(
                text=match.group(),
                start=match.start(),
                end=match.end(),
                is_word=True,
            ))
            last_end = match.end()

        # Add any remaining non-word text
        if last_end < len(text):
            tokens.append(Token(
                text=text[last_end:],
                start=last_end,
                end=len(text),
                is_word=False,
            ))

        return tokens

    def annotate(
        self,
        text: str,
        known_words: set[str],
        learning_words: set[str],
    ) -> AnnotatedText:
        """
        Annotate text with vocabulary stages.

        Args:
            text: The text to annotate
            known_words: Set of known words (lowercase)
            learning_words: Set of learning words (lowercase)

        Returns:
            AnnotatedText with stage information for each token
        """
        tokens = self.tokenize(text)
        annotated = []

        for token in tokens:
            if token.is_word:
                normalized = token.normalized
                if normalized in known_words:
                    stage = WordStage.KNOWN
                elif normalized in learning_words:
                    stage = WordStage.LEARNING
                else:
                    stage = WordStage.NEW
            else:
                stage = WordStage.NEW  # Non-words get NEW (neutral)

            annotated.append(AnnotatedToken(
                text=token.text,
                start=token.start,
                end=token.end,
                is_word=token.is_word,
                stage=stage,
            ))

        return AnnotatedText(original=text, tokens=annotated)

    def extract_words(self, text: str) -> list[str]:
        """Extract just the words from text (lowercase, accent-stripped)."""
        return [strip_accents(m.group().lower()) for m in self.WORD_PATTERN.finditer(text)]

    def count_words(self, text: str) -> int:
        """Count words in text."""
        return len(list(self.WORD_PATTERN.finditer(text)))

    def calculate_known_percentage(
        self,
        text: str,
        known_words: set[str],
    ) -> float:
        """Calculate what percentage of words in text are known."""
        words = self.extract_words(text)
        if not words:
            return 0.0

        known_count = sum(1 for w in words if w in known_words)
        return (known_count / len(words)) * 100

    def get_unknown_words(
        self,
        text: str,
        known_words: set[str],
        learning_words: set[str],
    ) -> list[str]:
        """Get list of unique unknown words in text."""
        words = set(self.extract_words(text))
        unknown = words - known_words - learning_words
        return sorted(unknown)

    def iter_lines_annotated(
        self,
        text: str,
        known_words: set[str],
        learning_words: set[str],
    ) -> Iterator[list[AnnotatedToken]]:
        """
        Iterate over text line by line with annotations.

        Useful for rendering text in a TUI line by line.
        """
        lines = text.split('\n')
        offset = 0

        for line in lines:
            annotated = self.annotate(line, known_words, learning_words)
            # Adjust offsets for the full text
            for token in annotated.tokens:
                token.start += offset
                token.end += offset
            yield annotated.tokens
            offset += len(line) + 1  # +1 for newline
