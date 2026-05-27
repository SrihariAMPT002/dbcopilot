"""
Pytest configuration for DB Copilot test suite.
"""

import os
import sys

import pytest

# ── Ensure the project root is on the path ───────────────────
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ── Set test environment variables before any app imports ────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "dbcopilot_test")
os.environ.setdefault("POSTGRES_USER", "dbcopilot")
os.environ.setdefault("POSTGRES_PASSWORD", "dbcopilot_secret")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://dbcopilot:dbcopilot_secret@localhost:5432/dbcopilot_test",
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    "postgresql://dbcopilot:dbcopilot_secret@localhost:5432/dbcopilot_test",
)

# Generate a real Fernet key for tests
from cryptography.fernet import Fernet
_test_key = Fernet.generate_key().decode()
os.environ.setdefault("ENCRYPTION_KEY", _test_key)
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-characters-ok!")
os.environ.setdefault("API_BASE_URL", "http://localhost:8000/api/v1")


# ── Async test support ────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop_policy():
    import asyncio
    return asyncio.DefaultEventLoopPolicy()
