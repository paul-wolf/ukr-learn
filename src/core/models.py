"""Data models for the language learning app."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


class WordStage(Enum):
    """Learning stage for a word."""
    NEW = "new"
    LEARNING = "learning"
    KNOWN = "known"


@dataclass
class Word:
    """A word in the user's vocabulary."""
    word: str
    stage: WordStage = WordStage.NEW
    translation: Optional[str] = None
    notes: Optional[str] = None
    added_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __hash__(self):
        return hash(self.word.lower())

    def __eq__(self, other):
        if isinstance(other, Word):
            return self.word.lower() == other.word.lower()
        if isinstance(other, str):
            return self.word.lower() == other.lower()
        return False


@dataclass
class WordEntry:
    """A word entry in a word list (with translation)."""
    word: str
    translation: str
    notes: Optional[str] = None


@dataclass
class Text:
    """A reading text."""
    id: str
    title: str
    content: str
    difficulty: str = "beginner"
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    source: str = "manual"

    @classmethod
    def create(cls, title: str, content: str, **kwargs) -> "Text":
        """Create a new text with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            **kwargs
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "difficulty": self.difficulty,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Text":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            difficulty=data.get("difficulty", "beginner"),
            tags=data.get("tags", []),
            created_at=created_at,
            source=data.get("source", "manual"),
        )


@dataclass
class WordList:
    """A themed list of words."""
    id: str
    title: str
    theme: str
    words: list[WordEntry] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, title: str, theme: str, **kwargs) -> "WordList":
        """Create a new word list with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            theme=theme,
            **kwargs
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "theme": self.theme,
            "words": [
                {"word": w.word, "translation": w.translation, "notes": w.notes}
                for w in self.words
            ],
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordList":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        words = [
            WordEntry(
                word=w["word"],
                translation=w["translation"],
                notes=w.get("notes"),
            )
            for w in data.get("words", [])
        ]

        return cls(
            id=data["id"],
            title=data["title"],
            theme=data.get("theme", "general"),
            words=words,
            created_at=created_at,
        )


@dataclass
class GrammarNote:
    """A grammar explanation note."""
    id: str
    title: str
    content: str
    tags: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def create(cls, title: str, content: str, **kwargs) -> "GrammarNote":
        """Create a new grammar note with generated ID."""
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            content=content,
            **kwargs
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "tags": self.tags,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "GrammarNote":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        return cls(
            id=data["id"],
            title=data["title"],
            content=data["content"],
            tags=data.get("tags", []),
            created_at=created_at,
        )


@dataclass
class TextProgress:
    """Track reading progress for a text."""
    text_id: str
    last_read: datetime = field(default_factory=datetime.now)
    times_read: int = 1
