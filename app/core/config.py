"""
Core configuration — loads from environment variables / .env file.
All settings are validated by Pydantic at startup.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────
    app_name: str = Field(default="DB Copilot")
    app_env: str = Field(default="development")
    app_version: str = Field(default="1.0.0")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # ── API ────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    api_prefix: str = Field(default="/api/v1")
    workers: int = Field(default=1)
    allowed_origins: List[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://streamlit:8501",
        ]
    )

    # ── Internal Metadata DB ───────────────────────────────────
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)
    postgres_db: str = Field(default="dbcopilot_meta")
    postgres_user: str = Field(default="dbcopilot")
    postgres_password: str = Field(default="dbcopilot_secret")

    database_url: str = Field(
        default="postgresql+asyncpg://dbcopilot:dbcopilot_secret@postgres:5432/dbcopilot_meta"
    )
    database_url_sync: str = Field(
        default="postgresql://dbcopilot:dbcopilot_secret@postgres:5432/dbcopilot_meta"
    )

    # ── Security & Encryption ──────────────────────────────────
    encryption_key: str = Field(default="")
    secret_key: str = Field(default="changeme-in-production-32-chars!!")

    # ── Connection Defaults ────────────────────────────────────
    connection_timeout: int = Field(default=30)
    max_pool_size: int = Field(default=5)
    min_pool_size: int = Field(default=1)
    connection_max_retries: int = Field(default=3)
    sync_request_timeout_seconds: int = Field(default=180)
    embeddings_request_timeout_seconds: int = Field(default=180)
    prompt_studio_request_timeout_seconds: int = Field(default=180)

    # ── Streamlit ──────────────────────────────────────────────
    api_base_url: str = Field(default="http://fastapi:8000/api/v1")

    # ── Redis ──────────────────────────────────────────
    redis_host: Optional[str] = Field(default=None)
    redis_port: int = Field(default=6379)

    # ── Azure OpenAI ───────────────────────────────────────────────
    azure_openai_endpoint: Optional[str] = Field(default=None)
    azure_openai_key: Optional[str] = Field(default=None)
    azure_openai_api_version: str = Field(default="2024-02-15-preview")
    azure_openai_deployment: str = Field(default="gpt-4o")

    # Embeddings use a separate endpoint/key and support custom dimensions
    azure_openai_embedding_url: Optional[str] = Field(default=None)
    azure_openai_embedding_api_key: Optional[str] = Field(default=None)
    azure_openai_embedding_deployment: str = Field(default="text-embedding-3-small")
    azure_openai_embedding_dimensions: int = Field(default=384)

    # ──  Qdrant ─────────────────────────────────────────
    qdrant_host: Optional[str] = Field(default=None)
    qdrant_port: int = Field(default=6333)
    qdrant_url: Optional[str] = Field(default=None)

    # ── PII Governance ───────────────────────────────────────────
    pii_prompt_protection_enabled: bool = Field(default=True)
    pii_embedding_protection_enabled: bool = Field(default=True)

    # Observability
    langsmith_tracing: bool = Field(default=False)
    langsmith_api_key: Optional[str] = Field(default=None)
    langsmith_project: Optional[str] = Field(default=None)
    langsmith_endpoint: Optional[str] = Field(default=None)

    # Intelligence Package Registry
    intelligence_packages_enabled: bool = Field(default=True)
    strict_schema_validation: bool = Field(default=True)

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {allowed}")
        return upper

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in ("development", "dev", "local")

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() in ("production", "prod")

    @property
    def supported_db_types(self) -> List[str]:
        return ["postgresql", "mysql", "sqlserver", "mongodb"]

    @property
    def embedding_configured(self) -> bool:
        """True if embedding credentials are available (either dedicated or fallback)."""
        has_dedicated = bool(self.azure_openai_embedding_url and self.azure_openai_embedding_api_key)
        has_fallback = bool(self.azure_openai_endpoint and self.azure_openai_key)
        return has_dedicated or has_fallback
    
@lru_cache()
def get_settings() -> Settings:
    """Return cached settings singleton."""
    return Settings()


settings = get_settings()
