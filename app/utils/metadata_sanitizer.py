"""
Helpers for normalizing external database metadata before persistence.
"""

from typing import Optional

INT32_MAX = 2_147_483_647

# MySQL / MariaDB report unbounded text types with sentinel lengths that do not
# fit in a 32-bit integer. We normalize those to NULL because the length is not
# meaningful for storage or display.
UNBOUNDED_TEXT_TYPES = frozenset(
    {
        "text",
        "tinytext",
        "mediumtext",
        "longtext",
        "json",
    }
)


def normalize_optional_int(value: Optional[int]) -> Optional[int]:
    """
    Defensive guard for external integer metadata.

    Returns None when the source value is missing, non-numeric, or outside the
    32-bit signed range used by most of the app's metadata fields.
    """
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    if parsed > INT32_MAX or parsed < 0:
        return None
    return parsed


def normalize_column_max_length(data_type: Optional[str], max_length: Optional[int]) -> Optional[int]:
    """
    Normalize column length metadata from external databases.

    - TEXT / LONGTEXT and other unbounded text-like types -> None
    - Oversized sentinel values -> None
    - Bounded types like VARCHAR(n) -> preserve n
    """
    if max_length is None:
        return None

    normalized_type = (data_type or "").strip().lower()
    if normalized_type in UNBOUNDED_TEXT_TYPES:
        return None

    return normalize_optional_int(max_length)


async def safe_flush(session) -> None:
    """
    Flush ORM changes and roll back the session if the flush fails.

    SQLAlchemy sessions remain in a failed state after flush/commit errors until
    rollback() is called. This helper prevents a single failed write from
    poisoning the session for later operations.
    """
    try:
        await session.flush()
    except Exception:
        await session.rollback()
        raise
