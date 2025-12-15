"""Core business logic - UI independent."""
from .models import Text, WordList, GrammarNote, Word, WordStage
from .text_processor import TextProcessor

# Note: VocabularyManager and ContentManager are imported directly
# where needed to avoid circular imports with storage module

__all__ = [
    "Text",
    "WordList",
    "GrammarNote",
    "Word",
    "WordStage",
    "TextProcessor",
]
