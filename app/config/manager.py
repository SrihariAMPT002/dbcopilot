"""
ConfigurationManager - Centralized configuration loading and management.

This module provides a singleton ConfigurationManager that:
1. Loads YAML configuration files
2. Validates configuration structure
3. Caches configurations in memory
4. Provides environment variable overrides
5. Supports hot-reloading of configurations
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional
import yaml
from functools import lru_cache
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ConfigEnvironment:
    """Represents the configuration environment."""
    name: str
    debug: bool
    environment: str  # development, staging, production


class ConfigurationError(Exception):
    """Raised when configuration loading or validation fails."""
    pass


class ConfigurationManager:
    """Centralized configuration management for all services.
    
    Loads and manages all YAML configuration files from app/config/ directory.
    Supports environment-based overrides and dynamic reloading.
    """

    _instance: Optional["ConfigurationManager"] = None
    _config_cache: Dict[str, Any] = {}
    _config_dir = None

    def __new__(cls):
        """Implement singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize configuration manager."""
        if self._initialized:
            return
        
        self._initialized = True
        self._config_dir = Path(__file__).parent  # app/config directory
        self.environment = self._detect_environment()
        logger.info(f"ConfigurationManager initialized for {self.environment}")

    @staticmethod
    def _detect_environment() -> str:
        """Detect current environment from env variables."""
        env = os.getenv("APP_ENV", "development").lower()
        if env not in ["development", "staging", "production"]:
            logger.warning(f"Unknown environment '{env}', defaulting to 'development'")
            return "development"
        return env

    def load_config(self, config_name: str, force_reload: bool = False) -> Dict[str, Any]:
        """Load a YAML configuration file.
        
        Args:
            config_name: Name of config file without .yaml extension (e.g., 'ai_models')
            force_reload: Skip cache and reload from disk
        
        Returns:
            Parsed configuration dictionary
        
        Raises:
            ConfigurationError: If file not found or invalid YAML
        """
        # Check cache first
        if not force_reload and config_name in self._config_cache:
            logger.debug(f"Loaded {config_name} from cache")
            return self._config_cache[config_name]

        # Load from file. Support nested config paths like "governance/pii_rules".
        config_file = self._config_dir / f"{config_name}.yaml"
        if not config_file.exists() and "/" in config_name:
            config_file = self._config_dir.joinpath(*config_name.split("/")).with_suffix(".yaml")
        if not config_file.exists():
            raise ConfigurationError(f"Configuration file not found: {config_file}")

        try:
            with open(config_file, "r") as f:
                config = yaml.safe_load(f)
            
            if config is None:
                config = {}
            
            logger.info(f"Loaded configuration from {config_file}")
            
            # Apply environment-specific overrides
            config = self._apply_environment_overrides(config, config_name)
            
            # Cache the configuration
            self._config_cache[config_name] = config
            
            return config

        except yaml.YAMLError as e:
            raise ConfigurationError(f"Invalid YAML in {config_file}: {e}")
        except Exception as e:
            raise ConfigurationError(f"Error loading {config_file}: {e}")

    def _apply_environment_overrides(
        self, config: Dict[str, Any], config_name: str
    ) -> Dict[str, Any]:
        """Apply environment-specific overrides from environment section."""
        if "environments" not in config:
            return config

        env_name = self.environment
        if env_name not in config["environments"]:
            return config

        env_config = config["environments"][env_name]
        logger.debug(f"Applying {env_name} environment overrides to {config_name}")
        
        # Deep merge environment config into main config
        config = self._deep_merge(config, env_config)
        return config

    @staticmethod
    def _deep_merge(base: Dict, override: Dict) -> Dict:
        """Deep merge override dictionary into base dictionary."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigurationManager._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def get_ai_models(self) -> Dict[str, Any]:
        """Get AI models configuration."""
        return self.load_config("ai_models")

    def get_readiness_rules(self) -> Dict[str, Any]:
        """Get readiness scoring rules."""
        return self.load_config("readiness_rules")

    def get_scoring_rules(self) -> Dict[str, Any]:
        """Get scoring algorithms and formulas."""
        return self.load_config("scoring_rules")

    def get_semantic_rules(self) -> Dict[str, Any]:
        """Get semantic analysis rules."""
        return self.load_config("semantic_rules")

    def get_governance_rulebook(self) -> Dict[str, Any]:
        """Get governance rulebook config."""
        return {
            "pii_rules": self.load_config("governance/pii_rules"),
            "sensitive_data_rules": self.load_config("governance/sensitive_data_rules"),
            "regulatory_rules": self.load_config("governance/regulatory_rules"),
            "governance_policy": self.load_config("governance/governance_policy"),
        }

    def get_feature_flags(self) -> Dict[str, Any]:
        """Get feature flags."""
        return self.load_config("feature_flags")

    def get_retry_policies(self) -> Dict[str, Any]:
        """Get retry and resilience policies."""
        return self.load_config("retry_policies")

    def is_feature_enabled(self, feature_name: str) -> bool:
        """Check if a feature is enabled.
        
        Args:
            feature_name: Name of feature (e.g., 'semantic_intelligence')
        
        Returns:
            True if enabled, False otherwise
        """
        try:
            flags = self.get_feature_flags()
            feature = flags.get("features", {}).get(feature_name, {})
            
            # Check global enabled flag
            if not feature.get("enabled", False):
                return False
            
            # Check environment-specific flag
            env_config = feature.get("environments", {})
            if self.environment in env_config:
                return env_config[self.environment]
            
            # Default to enabled if not specified
            return True
        except Exception as e:
            logger.error(f"Error checking feature flag '{feature_name}': {e}")
            return False

    def get_model_config(self, model_key: str) -> Dict[str, Any]:
        """Get configuration for a specific AI model.
        
        Args:
            model_key: Model identifier (e.g., 'semantic_generation')
        
        Returns:
            Model configuration dictionary
        
        Raises:
            ConfigurationError: If model not found
        """
        config = self.get_ai_models()
        models = config.get("models", {})
        
        if model_key not in models:
            raise ConfigurationError(f"Model configuration not found: {model_key}")
        
        return models[model_key]

    def get_retry_policy(self, service_name: str) -> Dict[str, Any]:
        """Get retry policy for a service.
        
        Args:
            service_name: Service identifier (e.g., 'azure_openai')
        
        Returns:
            Retry policy configuration
        """
        config = self.get_retry_policies()
        policies = config.get("retry_policies", {})
        
        # Return service-specific policy or defaults
        return policies.get(
            service_name,
            policies.get("defaults", {})
        )

    def get_readiness_threshold(self, status: str) -> int:
        """Get readiness score threshold for a status.
        
        Args:
            status: Status name ('ready', 'partial', 'not_ready')
        
        Returns:
            Minimum score for status
        """
        config = self.get_readiness_rules()
        thresholds = config.get("status_thresholds", {})
        
        if status not in thresholds:
            raise ConfigurationError(f"Unknown readiness status: {status}")
        
        return thresholds[status].get("min_score", 0)

    def clear_cache(self):
        """Clear all cached configurations."""
        self._config_cache.clear()
        logger.info("Configuration cache cleared")

    def reload_all(self):
        """Reload all configurations from disk."""
        self.clear_cache()
        logger.info("Configuration reload initiated")
        
        # Pre-load all known configurations
        try:
            self.get_ai_models()
            self.get_readiness_rules()
            self.get_scoring_rules()
            self.get_semantic_rules()
            self.get_governance_rulebook()
            self.get_feature_flags()
            self.get_retry_policies()
            logger.info("All configurations reloaded successfully")
        except Exception as e:
            logger.error(f"Error reloading configurations: {e}")
            raise

    @property
    def config_directory(self) -> Path:
        """Get the configuration directory path."""
        return self._config_dir

    def list_configs(self) -> list:
        """List all available configuration files."""
        if not self._config_dir.exists():
            return []
        
        return [
            f.stem for f in self._config_dir.glob("*.yaml")
            if f.is_file()
        ]


# Singleton instance
config_manager = ConfigurationManager()


# Helper functions for easy access
def get_config_manager() -> ConfigurationManager:
    """Get the configuration manager singleton."""
    return config_manager


def reload_config():
    """Reload all configurations from disk."""
    config_manager.reload_all()


def is_feature_enabled(feature_name: str) -> bool:
    """Check if a feature is enabled."""
    return config_manager.is_feature_enabled(feature_name)


def get_model_config(model_key: str) -> Dict[str, Any]:
    """Get AI model configuration."""
    return config_manager.get_model_config(model_key)


def get_retry_policy(service_name: str) -> Dict[str, Any]:
    """Get retry policy for a service."""
    return config_manager.get_retry_policy(service_name)
