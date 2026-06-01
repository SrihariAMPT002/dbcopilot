"""
Configuration management module.

Provides centralized management of:
- YAML configuration files
- Prompt templates
- Feature flags
- Retry policies
- Scoring rules
- AI model configurations
"""

from app.config.manager import (
    ConfigurationManager,
    config_manager,
    get_config_manager,
    is_feature_enabled,
    get_model_config,
    get_retry_policy,
    reload_config,
)

from app.config.prompts import (
    PromptRegistry,
    RenderedPrompt,
    PromptMetadata,
    get_prompt_registry,
    get_semantic_prompt,
    get_enrichment_prompt,
)

__all__ = [
    # Configuration Management
    "ConfigurationManager",
    "config_manager",
    "get_config_manager",
    "is_feature_enabled",
    "get_model_config",
    "get_retry_policy",
    "reload_config",
    # Prompt Management
    "PromptRegistry",
    "RenderedPrompt",
    "PromptMetadata",
    "get_prompt_registry",
    "get_semantic_prompt",
    "get_enrichment_prompt",
]
