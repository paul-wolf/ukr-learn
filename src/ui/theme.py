"""Color theme and styling for the TUI."""

# Urwid palette for the application
# Format: (name, foreground, background, mono, foreground_high, background_high)

PALETTE = [
    # Word stages
    ("known", "light green", ""),
    ("learning", "yellow", ""),
    ("new", "white", ""),
    ("selected", "standout", ""),

    # Cursor (current word) - underline variants
    ("cursor", "white,underline", ""),
    ("cursor_known", "light green,underline", ""),
    ("cursor_learning", "yellow,underline", ""),
    ("cursor_selected", "standout,underline", ""),

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


def get_cursor_attr(stage, is_selected: bool) -> str:
    """Get attribute name for cursor on a word with given stage."""
    from src.core.models import WordStage
    if is_selected:
        return "cursor_selected"
    return {
        WordStage.KNOWN: "cursor_known",
        WordStage.LEARNING: "cursor_learning",
        WordStage.NEW: "cursor",
    }.get(stage, "cursor")
