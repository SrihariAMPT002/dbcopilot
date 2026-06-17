from app.services.cache_service import CacheService


def test_cache_service_defaults_without_redis(monkeypatch):
    monkeypatch.delenv("REDIS_ENABLED", raising=False)
    service = CacheService()
    assert service.enabled is False
    assert service.ttl_seconds == 3600
