"""Simple unit tests for core functionality."""

import tempfile
from pathlib import Path

# Models
from src.core.models import WordStage, Text, WordList, WordEntry, GrammarNote

# Text processor
from src.core.text_processor import TextProcessor, strip_accents

# Theme
from src.ui.theme import get_stage_attr, get_cursor_attr

# Database
from src.storage.database import Database


class TestWordStage:
    """Test WordStage enum."""

    def test_stages_exist(self):
        assert WordStage.NEW.value == "new"
        assert WordStage.LEARNING.value == "learning"
        assert WordStage.KNOWN.value == "known"

    def test_stage_from_string(self):
        assert WordStage("new") == WordStage.NEW
        assert WordStage("learning") == WordStage.LEARNING
        assert WordStage("known") == WordStage.KNOWN


class TestModels:
    """Test data models."""

    def test_text_create(self):
        text = Text.create(
            title="Test",
            content="Привіт",
            difficulty="beginner",
        )
        assert text.title == "Test"
        assert text.content == "Привіт"
        assert text.id is not None
        assert len(text.id) == 36  # UUID

    def test_wordlist_create(self):
        wl = WordList.create(
            title="Test List",
            theme="test",
            words=[
                WordEntry(word="слово", translation="word", notes=None)
            ],
        )
        assert wl.title == "Test List"
        assert len(wl.words) == 1
        assert wl.words[0].word == "слово"

    def test_grammar_note_create(self):
        note = GrammarNote.create(
            title="Cases",
            content="Ukrainian has 7 cases.",
            tags=["grammar", "cases"],
        )
        assert note.title == "Cases"
        assert "cases" in note.tags


class TestTextProcessor:
    """Test Ukrainian text processing."""

    def setup_method(self):
        self.processor = TextProcessor()

    def test_tokenize_simple(self):
        tokens = self.processor.tokenize("Привіт світ")
        words = [t for t in tokens if t.is_word]
        assert len(words) == 2
        assert words[0].text == "Привіт"
        assert words[1].text == "світ"

    def test_tokenize_with_punctuation(self):
        tokens = self.processor.tokenize("Привіт, світ!")
        words = [t for t in tokens if t.is_word]
        assert len(words) == 2

    def test_tokenize_preserves_case(self):
        tokens = self.processor.tokenize("ПРИВІТ Світ")
        words = [t for t in tokens if t.is_word]
        assert words[0].text == "ПРИВІТ"
        assert words[0].normalized == "привіт"

    def test_tokenize_apostrophe(self):
        # Ukrainian uses apostrophes in words like "п'ять" (five)
        tokens = self.processor.tokenize("п'ять")
        words = [t for t in tokens if t.is_word]
        assert len(words) == 1
        assert "п" in words[0].text

    def test_tokenize_mixed_scripts(self):
        # Should only match Cyrillic as Ukrainian words
        tokens = self.processor.tokenize("Hello Привіт World")
        words = [t for t in tokens if t.is_word]
        # Only "Привіт" should be recognized as a Ukrainian word
        assert any(w.text == "Привіт" for w in words)

    def test_iter_lines(self):
        text = "Рядок один\nРядок два\nРядок три"
        lines = list(self.processor.iter_lines_annotated(text, set(), set()))
        assert len(lines) == 3

    def test_annotation_known_words(self):
        known = {"привіт"}
        lines = list(self.processor.iter_lines_annotated("Привіт світ", known, set()))
        tokens = lines[0]
        words = [t for t in tokens if t.is_word]
        # "привіт" should be marked as known
        assert words[0].stage == WordStage.KNOWN
        assert words[1].stage == WordStage.NEW

    def test_annotation_learning_words(self):
        learning = {"світ"}
        lines = list(self.processor.iter_lines_annotated("Привіт світ", set(), learning))
        tokens = lines[0]
        words = [t for t in tokens if t.is_word]
        assert words[0].stage == WordStage.NEW
        assert words[1].stage == WordStage.LEARNING

    def test_tokenize_with_stress_accents(self):
        # Ukrainian learning texts often have stress marks (combining acute accent)
        # "ме́не" = "м" + "е" + combining acute + "н" + "е"
        tokens = self.processor.tokenize("ме́не")
        words = [t for t in tokens if t.is_word]
        assert len(words) == 1
        # Original text preserved
        assert "е́" in words[0].text or len(words[0].text) >= 4
        # Normalized form strips accents
        assert words[0].normalized == "мене"

    def test_extract_words_strips_accents(self):
        # Text with stress marks should normalize properly
        words = self.processor.extract_words("Ти ме́не чу́єш?")
        assert "мене" in words
        assert "чуєш" in words

    def test_known_word_with_accent_matches(self):
        # A word with accent marks should match known word without accents
        known = {"мене"}
        lines = list(self.processor.iter_lines_annotated("ме́не", known, set()))
        tokens = lines[0]
        words = [t for t in tokens if t.is_word]
        assert len(words) == 1
        assert words[0].stage == WordStage.KNOWN


class TestStripAccents:
    """Test accent stripping function."""

    def test_strip_combining_acute(self):
        # Combining acute accent U+0301
        assert strip_accents("ме́не") == "мене"
        assert strip_accents("чу́єш") == "чуєш"

    def test_strip_preserves_regular_text(self):
        # Text without accents unchanged
        assert strip_accents("привіт") == "привіт"
        assert strip_accents("слово") == "слово"

    def test_strip_multiple_accents(self):
        # Multiple words with accents
        result = strip_accents("Ти ме́не чу́єш?")
        assert result == "Ти мене чуєш?"


class TestTheme:
    """Test theme helper functions."""

    def test_get_stage_attr(self):
        assert get_stage_attr(WordStage.KNOWN) == "known"
        assert get_stage_attr(WordStage.LEARNING) == "learning"
        assert get_stage_attr(WordStage.NEW) == "new"

    def test_get_cursor_attr_not_selected(self):
        assert get_cursor_attr(WordStage.KNOWN, False) == "cursor_known"
        assert get_cursor_attr(WordStage.LEARNING, False) == "cursor_learning"
        assert get_cursor_attr(WordStage.NEW, False) == "cursor"

    def test_get_cursor_attr_selected(self):
        # When selected, always returns cursor_selected
        assert get_cursor_attr(WordStage.KNOWN, True) == "cursor_selected"
        assert get_cursor_attr(WordStage.LEARNING, True) == "cursor_selected"
        assert get_cursor_attr(WordStage.NEW, True) == "cursor_selected"


class TestDatabase:
    """Test database operations with temp SQLite file."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)

    def teardown_method(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_set_and_get_word_stage(self):
        self.db.set_word_stage("тест", WordStage.KNOWN)
        word = self.db.get_word("тест")
        assert word is not None
        assert word.stage == WordStage.KNOWN

    def test_bulk_set_stage(self):
        words = ["один", "два", "три"]
        self.db.bulk_set_stage(words, WordStage.LEARNING)

        for w in words:
            word = self.db.get_word(w)
            assert word.stage == WordStage.LEARNING

    def test_get_known_words_set(self):
        self.db.set_word_stage("відомий", WordStage.KNOWN)
        self.db.set_word_stage("новий", WordStage.NEW)

        known = self.db.get_known_words_set()
        assert "відомий" in known
        assert "новий" not in known

    def test_set_translation(self):
        self.db.set_word_translation("слово", "word")
        word = self.db.get_word("слово")
        assert word.translation == "word"

    def test_word_info_cache(self):
        self.db.save_word_info("тест", "word", "This is test info")
        cached = self.db.get_word_info("тест")
        assert cached == "This is test info"

    def test_word_info_cache_miss(self):
        cached = self.db.get_word_info("nonexistent")
        assert cached is None

    def test_vocabulary_stats(self):
        self.db.set_word_stage("a", WordStage.KNOWN)
        self.db.set_word_stage("b", WordStage.KNOWN)
        self.db.set_word_stage("c", WordStage.LEARNING)

        stats = self.db.get_vocabulary_stats()
        assert stats["known"] == 2
        assert stats["learning"] == 1
