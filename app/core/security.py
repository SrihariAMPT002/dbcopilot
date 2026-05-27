"""
Security utilities.

Handles:
  - Symmetric encryption of DB credentials at rest (Fernet / AES-128-CBC)
  - Password masking for logs
  - Connection string sanitization
"""

import base64
import logging
from urllib.parse import quote_plus
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Fernet cipher (lazy-init so we don't crash if key is missing at import) ──

_cipher: Optional[Fernet] = None


def _get_cipher() -> Fernet:
    global _cipher
    if _cipher is None:
        key = settings.encryption_key
        if not key:
            raise RuntimeError(
                "ENCRYPTION_KEY is not set. "
                "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
            )
        try:
            _cipher = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as exc:
            raise RuntimeError(f"Invalid ENCRYPTION_KEY: {exc}") from exc
    return _cipher


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret string and return base64-encoded ciphertext."""
    if not plaintext:
        return ""
    try:
        cipher = _get_cipher()
        token = cipher.encrypt(plaintext.encode("utf-8"))
        return token.decode("utf-8")
    except Exception as exc:
        logger.error("Encryption failed: %s", exc)
        raise


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a Fernet token back to plaintext."""
    if not ciphertext:
        return ""
    try:
        cipher = _get_cipher()
        plaintext = cipher.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken:
        raise ValueError(
            "Failed to decrypt credential — key mismatch or corrupted data."
        )
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        raise


def mask_secret(value: str, visible_chars: int = 4) -> str:
    """Return a masked version safe for logging: 'pass****'."""
    if not value:
        return "****"
    show = value[:visible_chars]
    return show + "*" * max(4, len(value) - visible_chars)


def sanitize_connection_string(conn_str: str) -> str:
    """Remove password from a connection string for safe logging."""
    import re

    # Matches postgresql://user:password@host or similar
    return re.sub(r"(:)[^:@]+(@)", r"\1****\2", conn_str)


def build_connection_url(
    db_type: str,
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    driver: Optional[str] = None,
) -> str:
    """Build a SQLAlchemy-compatible connection URL."""
    db_type = db_type.lower()

    if db_type == "postgresql":
        drv = driver or "postgresql+psycopg2"
        return f"{drv}://{username}:{password}@{host}:{port}/{database}"

    elif db_type == "mysql":
        drv = driver or "mysql+pymysql"
        return f"{drv}://{username}:{password}@{host}:{port}/{database}"

    elif db_type == "sqlserver":
        drv = driver or "mssql+pyodbc"
        return (
            f"{drv}://{username}:{password}@{host}:{port}/{database}"
            "?driver=ODBC+Driver+17+for+SQL+Server"
        )

    elif db_type == "mongodb":
        # Return a Mongo URI (not SQLAlchemy)
        user = quote_plus(username)
        secret = quote_plus(password)
        return f"mongodb://{user}:{secret}@{host}:{port}/{database}"

    else:
        raise ValueError(f"Unsupported db_type: {db_type}")
