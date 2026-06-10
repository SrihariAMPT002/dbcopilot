"""
PromptRegistry - Centralized prompt management and rendering.

This module provides a PromptRegistry that:
1. Loads prompts from YAML files
2. Manages prompt versioning
3. Renders prompts with variable substitution (Jinja2)
4. Validates prompts against schemas
5. Provides prompts to services without hardcoding
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, List
import yaml
from jinja2 import Environment, FileSystemLoader, Template, TemplateError
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptMetadata:
    """Metadata about a prompt."""
    id: str
    name: str
    version: str
    description: str
    category: str
    language: str


@dataclass
class RenderedPrompt:
    """A rendered prompt with metadata."""
    id: str
    system_message: str
    user_prompt: str
    metadata: PromptMetadata
    constraints: Dict[str, Any]
    tokens_estimated: Optional[int] = None


class PromptError(Exception):
    """Raised when prompt loading or rendering fails."""
    pass


class PromptRegistry:
    """Centralized registry for all prompts.
    
    Loads prompts from app/prompts/ directory in YAML format.
    Supports Jinja2 variable substitution and prompt versioning.
    """

    def __init__(self):
        """Initialize prompt registry."""
        self.prompts_dir = Path(__file__).parent.parent / "prompts"
        self._prompt_cache: Dict[str, Dict[str, Any]] = {}
        self.jinja_env = self._setup_jinja_environment()
        logger.info(f"PromptRegistry initialized with prompts directory: {self.prompts_dir}")

    def _setup_jinja_environment(self) -> Environment:
        """Set up Jinja2 environment for template rendering."""
        if self.prompts_dir.exists():
            env = Environment(loader=FileSystemLoader(str(self.prompts_dir)))
        else:
            env = Environment()
        
        # Add custom filters
        env.filters["truncate"] = self._truncate
        env.filters["format_list"] = self._format_list
        env.filters["tojson"] = self._tojson
        
        return env

    @staticmethod
    def _truncate(text: str, length: int = 100) -> str:
        """Truncate text to specified length."""
        if len(text) <= length:
            return text
        return text[:length] + "..."

    @staticmethod
    def _format_list(items: List[str], separator: str = ", ") -> str:
        """Format a list as a string."""
        return separator.join(str(i) for i in items)

    @staticmethod
    def _tojson(value: Any, indent: int = 2) -> str:
        """Render a value as JSON for prompt templates."""
        return json.dumps(value, ensure_ascii=False, indent=indent, default=str)

    def load_prompt(self, prompt_id: str, category: str = None, force_reload: bool = False) -> Dict[str, Any]:
        """Load a prompt from YAML file.
        
        Args:
            prompt_id: Unique prompt identifier (e.g., 'database_analysis')
            category: Category subdirectory (e.g., 'semantic', 'enrichment')
            force_reload: Skip cache and reload from disk
        
        Returns:
            Parsed prompt dictionary
        
        Raises:
            PromptError: If prompt not found or invalid
        """
        cache_key = f"{category}/{prompt_id}" if category else prompt_id
        
        # Check cache
        if not force_reload and cache_key in self._prompt_cache:
            logger.debug(f"Loaded prompt {cache_key} from cache")
            return self._prompt_cache[cache_key]

        # Construct file path
        if category:
            prompt_file = self.prompts_dir / category / f"{prompt_id}.yaml"
        else:
            prompt_file = self.prompts_dir / f"{prompt_id}.yaml"

        if not prompt_file.exists():
            raise PromptError(f"Prompt file not found: {prompt_file}")

        try:
            with open(prompt_file, "r") as f:
                prompt = yaml.safe_load(f)
            
            if not prompt:
                raise PromptError(f"Empty prompt file: {prompt_file}")
            
            # Validate required fields
            self._validate_prompt(prompt)
            
            # Cache the prompt
            self._prompt_cache[cache_key] = prompt
            logger.info(f"Loaded prompt {cache_key} from {prompt_file}")
            
            return prompt

        except yaml.YAMLError as e:
            raise PromptError(f"Invalid YAML in {prompt_file}: {e}")
        except Exception as e:
            raise PromptError(f"Error loading {prompt_file}: {e}")

    def _validate_prompt(self, prompt: Dict[str, Any]):
        """Validate prompt structure.
        
        Args:
            prompt: Prompt dictionary to validate
        
        Raises:
            PromptError: If validation fails
        """
        required_fields = ["id", "name", "user_prompt", "constraints"]
        
        for field in required_fields:
            if field not in prompt:
                raise PromptError(f"Prompt missing required field: {field}")

    def render_prompt(
        self,
        prompt_id: str,
        variables: Dict[str, Any],
        category: str = None
    ) -> RenderedPrompt:
        """Render a prompt with variable substitution.
        
        Args:
            prompt_id: Prompt identifier
            variables: Dictionary of variables for template substitution
            category: Category subdirectory
        
        Returns:
            RenderedPrompt with rendered text
        
        Raises:
            PromptError: If rendering fails
        """
        # Load the prompt
        prompt_config = self.load_prompt(prompt_id, category)
        
        try:
            # Render user prompt
            user_template = Template(prompt_config["user_prompt"])
            user_prompt = user_template.render(**variables)
            
            # Render system message if present
            system_message = ""
            if "system_message" in prompt_config:
                system_template = Template(prompt_config["system_message"])
                system_message = system_template.render(**variables)
            
            # Extract metadata
            metadata = PromptMetadata(
                id=prompt_config.get("id", prompt_id),
                name=prompt_config.get("name", ""),
                version=prompt_config.get("version", "1.0"),
                description=prompt_config.get("description", ""),
                category=prompt_config.get("metadata", {}).get("category", ""),
                language=prompt_config.get("language", "English")
            )
            
            # Create rendered prompt
            rendered = RenderedPrompt(
                id=prompt_config["id"],
                system_message=system_message,
                user_prompt=user_prompt,
                metadata=metadata,
                constraints=prompt_config.get("constraints", {})
            )
            
            logger.debug(f"Rendered prompt {prompt_id}")
            return rendered

        except TemplateError as e:
            raise PromptError(f"Error rendering prompt {prompt_id}: {e}")
        except Exception as e:
            raise PromptError(f"Unexpected error rendering prompt {prompt_id}: {e}")

    def get_semantic_prompt(self, variables: Dict[str, Any]) -> RenderedPrompt:
        """Get rendered semantic analysis prompt.
        
        Args:
            variables: Database metadata variables
        
        Returns:
            RenderedPrompt
        """
        return self.render_prompt("database_analysis", variables, category="semantic")

    def get_enrichment_prompt(self, variables: Dict[str, Any]) -> RenderedPrompt:
        """Get rendered table enrichment prompt.
        
        Args:
            variables: Table metadata variables
        
        Returns:
            RenderedPrompt
        """
        return self.render_prompt("table_enrichment", variables, category="enrichment")

    def list_prompts(self, category: str = None) -> List[str]:
        """List all available prompts.
        
        Args:
            category: Optional category to filter
        
        Returns:
            List of prompt IDs
        """
        if not self.prompts_dir.exists():
            return []

        prompts = []
        if category:
            category_dir = self.prompts_dir / category
            if category_dir.exists():
                prompts = [f.stem for f in category_dir.glob("*.yaml")]
        else:
            for prompt_file in self.prompts_dir.rglob("*.yaml"):
                if prompt_file.parent == self.prompts_dir:
                    prompts.append(prompt_file.stem)
                else:
                    prompts.append(f"{prompt_file.parent.name}/{prompt_file.stem}")

        return sorted(prompts)

    def validate_response(
        self,
        response: Dict[str, Any],
        prompt_id: str,
        category: str = None
    ) -> bool:
        """Validate AI response against prompt schema.
        
        Args:
            response: AI response dictionary
            prompt_id: Prompt identifier
            category: Category subdirectory
        
        Returns:
            True if valid, False otherwise
        """
        try:
            prompt = self.load_prompt(prompt_id, category)
            schema = prompt.get("response_schema", {})
            
            if not schema:
                logger.warning(f"No response schema defined for {prompt_id}")
                return True
            
            # Basic schema validation
            required_fields = schema.keys()
            for field in required_fields:
                if field not in response:
                    logger.error(f"Response missing required field: {field}")
                    return False
            
            logger.debug(f"Response validation passed for {prompt_id}")
            return True

        except Exception as e:
            logger.error(f"Error validating response: {e}")
            return False

    def estimate_tokens(self, rendered_prompt: RenderedPrompt) -> int:
        """Estimate token count for a rendered prompt.
        
        Args:
            rendered_prompt: Rendered prompt object
        
        Returns:
            Estimated token count
        """
        # Simple word-to-token estimation (actual: use tokenizer library)
        total_text = rendered_prompt.system_message + rendered_prompt.user_prompt
        words = len(total_text.split())
        # Average ~1.3 tokens per word
        estimated_tokens = int(words * 1.3)
        return estimated_tokens

    def clear_cache(self):
        """Clear prompt cache."""
        self._prompt_cache.clear()
        logger.info("Prompt cache cleared")

    def reload_all(self, force_reload: bool = True):
        """Reload all prompts from disk."""
        self.clear_cache()
        logger.info("Reloading all prompts")
        
        # Pre-load all prompts
        try:
            prompts = self.list_prompts()
            for prompt_id in prompts:
                if "/" in prompt_id:
                    category, pid = prompt_id.split("/", 1)
                    self.load_prompt(pid, category, force_reload=force_reload)
                else:
                    self.load_prompt(prompt_id, force_reload=force_reload)
            
            logger.info(f"Reloaded {len(prompts)} prompts")
        except Exception as e:
            logger.error(f"Error reloading prompts: {e}")
            raise


# Singleton instance
_prompt_registry: Optional[PromptRegistry] = None


def get_prompt_registry() -> PromptRegistry:
    """Get the prompt registry singleton."""
    global _prompt_registry
    if _prompt_registry is None:
        _prompt_registry = PromptRegistry()
    return _prompt_registry


def get_semantic_prompt(variables: Dict[str, Any]) -> RenderedPrompt:
    """Get rendered semantic analysis prompt."""
    return get_prompt_registry().get_semantic_prompt(variables)


def get_enrichment_prompt(variables: Dict[str, Any]) -> RenderedPrompt:
    """Get rendered table enrichment prompt."""
    return get_prompt_registry().get_enrichment_prompt(variables)
