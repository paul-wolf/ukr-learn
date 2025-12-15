"""Color theme and styling for the TUI."""

# Urwid palette for the application
# Format: (name, foreground, background, mono, foreground_high, background_high)

PALETTE = [
    # Word stages
    ("known", "light green", ""),
    ("learning", "yellow", ""),
    ("new", "white", ""),
    ("selected", "standout", ""),

    # UI elements
    ("header", "white", "dark blue"),
    ("footer", "white", "dark gray"),
    ("tab_active", "white,bold", "dark blue"),
    ("tab_inactive", "light gray", "dark gray"),

    # List items
    ("list_item", "white", ""),
    ("list_item_selected", "white", "dark blue"),
    ("list_item_focus", "white,bold", "dark cyan"),

    # Content
    ("content", "white", ""),
    ("content_title", "white,bold", ""),

    # Status/info
    ("info", "light cyan", ""),
    ("success", "light green", ""),
    ("warning", "yellow", ""),
    ("error", "light red", ""),

    # Quiz
    ("quiz_word", "white,bold", ""),
    ("quiz_translation", "light green", ""),
    ("quiz_hint", "dark gray", ""),

    # Dialog
    ("dialog", "white", "dark gray"),
    ("dialog_title", "white,bold", "dark blue"),
    ("button", "white", "dark gray"),
    ("button_focus", "white,bold", "dark blue"),
]


def get_stage_attr(stage) -> str:
    """Get attribute name for a word stage."""
    from src.core.models import WordStage
    return {
        WordStage.KNOWN: "known",
        WordStage.LEARNING: "learning",
        WordStage.NEW: "new",
    }.get(stage, "new")
