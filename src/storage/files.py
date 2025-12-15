"""JSON file storage for texts, word lists, and grammar notes."""

import json
from pathlib import Path
from typing import TypeVar, Generic, Callable

from src.core.models import Text, WordList, GrammarNote


T = TypeVar("T", Text, WordList, GrammarNote)


class FileStorage(Generic[T]):
    """Generic JSON file storage for content types."""

    def __init__(
        self,
        directory: str | Path,
        from_dict: Callable[[dict], T],
        to_dict: Callable[[T], dict],
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._from_dict = from_dict
        self._to_dict = to_dict

    def _get_path(self, id: str) -> Path:
        """Get file path for an item."""
        return self.directory / f"{id}.json"

    def list_all(self) -> list[T]:
        """List all items in storage."""
        items = []
        for path in self.directory.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    items.append(self._from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Warning: Could not load {path}: {e}")
        return sorted(items, key=lambda x: x.created_at, reverse=True)

    def get(self, id: str) -> T | None:
        """Get an item by ID."""
        path = self._get_path(id)
        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return self._from_dict(data)
        except (json.JSONDecodeError, KeyError):
            return None

    def save(self, item: T) -> None:
        """Save an item to storage."""
        path = self._get_path(item.id)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._to_dict(item), f, ensure_ascii=False, indent=2)

    def delete(self, id: str) -> bool:
        """Delete an item by ID."""
        path = self._get_path(id)
        if path.exists():
            path.unlink()
            return True
        return False

    def exists(self, id: str) -> bool:
        """Check if an item exists."""
        return self._get_path(id).exists()


class TextStorage(FileStorage[Text]):
    """Storage for reading texts."""

    def __init__(self, directory: str | Path):
        super().__init__(
            directory,
            from_dict=Text.from_dict,
            to_dict=lambda t: t.to_dict(),
        )

    def list_by_difficulty(self, difficulty: str) -> list[Text]:
        """List texts filtered by difficulty."""
        return [t for t in self.list_all() if t.difficulty == difficulty]

    def list_by_tag(self, tag: str) -> list[Text]:
        """List texts that have a specific tag."""
        return [t for t in self.list_all() if tag in t.tags]


class WordListStorage(FileStorage[WordList]):
    """Storage for word lists."""

    def __init__(self, directory: str | Path):
        super().__init__(
            directory,
            from_dict=WordList.from_dict,
            to_dict=lambda w: w.to_dict(),
        )

    def list_by_theme(self, theme: str) -> list[WordList]:
        """List word lists filtered by theme."""
        return [w for w in self.list_all() if w.theme == theme]


class GrammarStorage(FileStorage[GrammarNote]):
    """Storage for grammar notes."""

    def __init__(self, directory: str | Path):
        super().__init__(
            directory,
            from_dict=GrammarNote.from_dict,
            to_dict=lambda g: g.to_dict(),
        )

    def list_by_tag(self, tag: str) -> list[GrammarNote]:
        """List grammar notes that have a specific tag."""
        return [g for g in self.list_all() if tag in g.tags]
