"""
Compatibility shim for legacy imports.

The canonical prompt registry lives in app.config.prompts.
"""

from app.config.prompts import (  # noqa: F401
    PromptError,
    PromptMetadata,
    PromptRegistry,
    RenderedPrompt,
    get_enrichment_prompt,
    get_prompt_registry,
    get_semantic_prompt,
)

__all__ = [
    "PromptError",
    "PromptMetadata",
    "PromptRegistry",
    "RenderedPrompt",
    "get_prompt_registry",
    "get_semantic_prompt",
    "get_enrichment_prompt",
]
