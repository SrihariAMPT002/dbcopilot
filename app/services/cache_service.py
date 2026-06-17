"""Optional Redis-backed cache helpers used by pipeline and UI polling."""

from __future__ import annotations

import fnmatch
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

try:  # Optional dependency.
    from redis.asyncio import Redis
except Exception:  # pragma: no cover - optional dependency.
    Redis = None

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self) -> None:
        self.enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        self.url = os.getenv("REDIS_URL") or self._build_url()
        self.ttl_seconds = int(os.getenv("REDIS_TTL_SECONDS", "3600"))
        self._client: Redis | None = None

    def _build_url(self) -> str | None:
        host = os.getenv("REDIS_HOST")
        if not host or Redis is None:
            return None
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))
        return f"redis://{host}:{port}/{db}"

    async def _get_client(self) -> Redis | None:
        if not self.enabled or Redis is None or not self.url:
            return None
        if self._client is None:
            self._client = Redis.from_url(self.url, decode_responses=True)
        return self._client

    async def get(self, key: str) -> Optional[str]:
        client = await self._get_client()
        if client is None:
            return None
        try:
            return await client.get(key)
        except Exception:
            logger.debug("Redis get failed for %s", key, exc_info=True)
            return None

    async def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.set(key, value, ex=ttl_seconds or self.ttl_seconds)
            return True
        except Exception:
            logger.debug("Redis set failed for %s", key, exc_info=True)
            return False

    async def delete(self, key: str) -> bool:
        client = await self._get_client()
        if client is None:
            return False
        try:
            await client.delete(key)
            return True
        except Exception:
            logger.debug("Redis delete failed for %s", key, exc_info=True)
            return False

    async def invalidate_pattern(self, pattern: str) -> int:
        client = await self._get_client()
        if client is None:
            return 0
        try:
            keys = await client.keys(pattern)
            if not keys:
                return 0
            return int(await client.delete(*keys))
        except Exception:
            logger.debug("Redis invalidate failed for %s", pattern, exc_info=True)
            return 0

    @asynccontextmanager
    async def lock(self, key: str, ttl_seconds: int = 600) -> AsyncIterator[bool]:
        client = await self._get_client()
        if client is None:
            yield True
            return
        acquired = False
        try:
            acquired = bool(await client.set(key, "1", nx=True, ex=ttl_seconds))
            yield acquired
        finally:
            if acquired:
                try:
                    await client.delete(key)
                except Exception:
                    logger.debug("Redis lock release failed for %s", key, exc_info=True)

    async def unlock(self, key: str) -> bool:
        return await self.delete(key)


cache_service = CacheService()
