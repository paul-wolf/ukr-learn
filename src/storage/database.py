"""SQLite database for vocabulary and metadata storage."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.models import Word, WordStage, TextProgress


class Database:
    """SQLite database manager for vocabulary and progress tracking."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS words (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT UNIQUE NOT NULL,
                    translation TEXT,
                    notes TEXT,
                    stage TEXT NOT NULL DEFAULT 'new',
                    added_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_words_stage ON words(stage);
                CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);

                CREATE TABLE IF NOT EXISTS text_progress (
                    text_id TEXT PRIMARY KEY,
                    last_read TIMESTAMP NOT NULL,
                    times_read INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS word_info_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lookup_key TEXT UNIQUE NOT NULL,
                    info_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_word_info_key ON word_info_cache(lookup_key);
            """)

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(
            self.db_path,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # Word operations

    def get_word(self, word: str) -> Optional[Word]:
        """Get a word by its text."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM words WHERE word = ? COLLATE NOCASE",
                (word.lower(),)
            ).fetchone()

            if row:
                return self._row_to_word(row)
            return None

    def get_words_by_stage(self, stage: WordStage) -> list[Word]:
        """Get all words with a specific stage."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM words WHERE stage = ? ORDER BY updated_at DESC",
                (stage.value,)
            ).fetchall()
            return [self._row_to_word(row) for row in rows]

    def get_all_words(self) -> list[Word]:
        """Get all words in the vocabulary."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT * FROM words ORDER BY updated_at DESC"
            ).fetchall()
            return [self._row_to_word(row) for row in rows]

    def get_known_words_set(self) -> set[str]:
        """Get set of known word strings for fast lookup."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT word FROM words WHERE stage = ?",
                (WordStage.KNOWN.value,)
            ).fetchall()
            return {row["word"] for row in rows}

    def get_learning_words_set(self) -> set[str]:
        """Get set of learning word strings for fast lookup."""
        with self._connection() as conn:
            rows = conn.execute(
                "SELECT word FROM words WHERE stage = ?",
                (WordStage.LEARNING.value,)
            ).fetchall()
            return {row["word"] for row in rows}

    def save_word(self, word: Word) -> None:
        """Insert or update a word."""
        now = datetime.now()
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO words (word, translation, notes, stage, added_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    translation = COALESCE(excluded.translation, translation),
                    notes = COALESCE(excluded.notes, notes),
                    stage = excluded.stage,
                    updated_at = excluded.updated_at
            """, (
                word.word.lower(),
                word.translation,
                word.notes,
                word.stage.value,
                word.added_at,
                now,
            ))

    def set_word_stage(self, word: str, stage: WordStage) -> None:
        """Set the stage for a word, creating it if needed."""
        now = datetime.now()
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO words (word, stage, added_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    stage = excluded.stage,
                    updated_at = excluded.updated_at
            """, (word.lower(), stage.value, now, now))

    def bulk_set_stage(self, words: list[str], stage: WordStage) -> None:
        """Set stage for multiple words at once."""
        now = datetime.now()
        with self._connection() as conn:
            for word in words:
                conn.execute("""
                    INSERT INTO words (word, stage, added_at, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(word) DO UPDATE SET
                        stage = excluded.stage,
                        updated_at = excluded.updated_at
                """, (word.lower(), stage.value, now, now))

    def set_word_translation(
        self, word: str, translation: str, notes: Optional[str] = None
    ) -> None:
        """Set translation for a word."""
        now = datetime.now()
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO words (word, translation, notes, stage, added_at, updated_at)
                VALUES (?, ?, ?, 'new', ?, ?)
                ON CONFLICT(word) DO UPDATE SET
                    translation = excluded.translation,
                    notes = COALESCE(excluded.notes, notes),
                    updated_at = excluded.updated_at
            """, (word.lower(), translation, notes, now, now))

    def delete_word(self, word: str) -> bool:
        """Delete a word from vocabulary."""
        with self._connection() as conn:
            cursor = conn.execute(
                "DELETE FROM words WHERE word = ? COLLATE NOCASE",
                (word.lower(),)
            )
            return cursor.rowcount > 0

    def _row_to_word(self, row: sqlite3.Row) -> Word:
        """Convert database row to Word object."""
        return Word(
            word=row["word"],
            translation=row["translation"],
            notes=row["notes"],
            stage=WordStage(row["stage"]),
            added_at=row["added_at"] if isinstance(row["added_at"], datetime)
                     else datetime.fromisoformat(row["added_at"]),
            updated_at=row["updated_at"] if isinstance(row["updated_at"], datetime)
                       else datetime.fromisoformat(row["updated_at"]),
        )

    # Text progress operations

    def get_text_progress(self, text_id: str) -> Optional[TextProgress]:
        """Get reading progress for a text."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT * FROM text_progress WHERE text_id = ?",
                (text_id,)
            ).fetchone()

            if row:
                return TextProgress(
                    text_id=row["text_id"],
                    last_read=row["last_read"] if isinstance(row["last_read"], datetime)
                              else datetime.fromisoformat(row["last_read"]),
                    times_read=row["times_read"],
                )
            return None

    def record_text_read(self, text_id: str) -> None:
        """Record that a text was read."""
        now = datetime.now()
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO text_progress (text_id, last_read, times_read)
                VALUES (?, ?, 1)
                ON CONFLICT(text_id) DO UPDATE SET
                    last_read = excluded.last_read,
                    times_read = times_read + 1
            """, (text_id, now))

    # Statistics

    def get_vocabulary_stats(self) -> dict[str, int]:
        """Get counts by word stage."""
        with self._connection() as conn:
            rows = conn.execute("""
                SELECT stage, COUNT(*) as count
                FROM words
                GROUP BY stage
            """).fetchall()

            stats = {stage.value: 0 for stage in WordStage}
            for row in rows:
                stats[row["stage"]] = row["count"]
            return stats

    # Word info cache operations

    def get_word_info(self, word_or_phrase: str) -> Optional[str]:
        """Get cached word/phrase info if available."""
        lookup_key = word_or_phrase.lower().strip()
        with self._connection() as conn:
            row = conn.execute(
                "SELECT content FROM word_info_cache WHERE lookup_key = ?",
                (lookup_key,)
            ).fetchone()
            if row:
                return row["content"]
            return None

    def save_word_info(self, word_or_phrase: str, info_type: str, content: str) -> None:
        """Cache word/phrase info.

        Args:
            word_or_phrase: The word or phrase (used as lookup key)
            info_type: 'word' or 'phrase'
            content: The detailed info content
        """
        lookup_key = word_or_phrase.lower().strip()
        now = datetime.now()
        with self._connection() as conn:
            conn.execute("""
                INSERT INTO word_info_cache (lookup_key, info_type, content, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(lookup_key) DO UPDATE SET
                    info_type = excluded.info_type,
                    content = excluded.content,
                    created_at = excluded.created_at
            """, (lookup_key, info_type, content, now))

    def clear_word_info_cache(self) -> int:
        """Clear all cached word info. Returns number of entries cleared."""
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM word_info_cache")
            return cursor.rowcount
