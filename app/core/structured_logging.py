"""Small helpers for consistent structured runtime log prefixes."""

from __future__ import annotations

from typing import Any


def _fmt_fields(**fields: Any) -> str:
    items = [f"{key}={value}" for key, value in fields.items() if value is not None]
    return " | " + ", ".join(items) if items else ""


def sync_message(event: str, **fields: Any) -> str:
    return f"[SYNC] {event}{_fmt_fields(**fields)}"


def stage_message(event: str, **fields: Any) -> str:
    return f"[STAGE] {event}{_fmt_fields(**fields)}"


def error_message(event: str, **fields: Any) -> str:
    return f"[ERROR] {event}{_fmt_fields(**fields)}"


def api_message(event: str, **fields: Any) -> str:
    return f"[API] {event}{_fmt_fields(**fields)}"
