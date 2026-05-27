"""
Shared utility helpers used across the application.
"""

import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def now_utc() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


def snake_to_title(name: str) -> str:
    """Convert snake_case to Title Case: 'my_table_name' → 'My Table Name'."""
    return " ".join(word.capitalize() for word in name.split("_"))


def truncate(text: str, max_len: int = 100, suffix: str = "…") -> str:
    """Truncate a string to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[: max_len - len(suffix)] + suffix


def safe_int(value: Any, default: int = 0) -> int:
    """Parse an int safely, returning default on failure."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def is_valid_identifier(name: str) -> bool:
    """
    Return True if `name` is a valid SQL identifier.
    Allows letters, digits, underscores; must start with letter or underscore.
    """
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_$]*$", name))


def redact_dict(d: Dict[str, Any], sensitive_keys: Optional[set] = None) -> Dict[str, Any]:
    """
    Return a copy of dict `d` with sensitive values replaced by '****'.
    Useful for safe logging of credential dicts.
    """
    if sensitive_keys is None:
        sensitive_keys = {"password", "secret", "token", "key", "credential"}
    return {
        k: "****" if any(s in k.lower() for s in sensitive_keys) else v
        for k, v in d.items()
    }
