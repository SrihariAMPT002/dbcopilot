"""Intelligence package registry helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from app.config.manager import get_config_manager
from app.core.config import settings


@lru_cache()
def get_package_registry() -> dict[str, Any]:
    if not settings.intelligence_packages_enabled:
        return {"packages": {}}
    return get_config_manager().get_packages()


def package_is_enabled(package_name: str) -> bool:
    if not settings.intelligence_packages_enabled:
        return False
    packages = get_package_registry().get("packages", {})
    package = packages.get(package_name, {})
    return bool(package.get("enabled", False))


def package_ui_visible(package_name: str) -> bool:
    if not settings.intelligence_packages_enabled:
        return False
    packages = get_package_registry().get("packages", {})
    package = packages.get(package_name, {})
    return bool(package.get("ui_visibility", False))


def package_artifacts(package_name: str) -> list[str]:
    packages = get_package_registry().get("packages", {})
    package = packages.get(package_name, {})
    return list(package.get("artifacts", []) or [])


def clear_package_registry_cache() -> None:
    get_package_registry.cache_clear()
