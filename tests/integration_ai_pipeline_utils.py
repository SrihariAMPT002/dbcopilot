from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Callable

import requests


logger = logging.getLogger(__name__)


def integration_enabled() -> bool:
    return os.getenv("RUN_AI_INTEGRATION_TESTS", "").lower() in {"1", "true", "yes", "on"}


def azure_configured() -> bool:
    return bool(
        os.getenv("AZURE_OPENAI_ENDPOINT")
        and os.getenv("AZURE_OPENAI_KEY")
        and os.getenv("AZURE_OPENAI_DEPLOYMENT")
        and os.getenv("AZURE_OPENAI_API_VERSION")
    )


def api_base_url() -> str:
    return os.getenv("API_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")


def get_json(path: str, timeout: int = 60) -> tuple[bool, Any]:
    try:
        response = requests.get(f"{api_base_url()}{path}", timeout=timeout)
        response.raise_for_status()
        return True, response.json()
    except Exception as exc:
        return False, str(exc)


def post_json(path: str, payload: dict[str, Any], timeout: int = 120) -> tuple[bool, Any]:
    try:
        response = requests.post(f"{api_base_url()}{path}", json=payload, timeout=timeout)
        response.raise_for_status()
        return True, response.json()
    except Exception as exc:
        return False, str(exc)


def ensure(condition: bool, message: str) -> None:
    assert condition, message


def dump_response(name: str, payload: Any) -> None:
    logger.info("%s=%s", name, payload)
