"""
News Snek - Generalized Provider Infrastructure
Handles different AI backends (Ollama, OpenRouter) and fallback chains.
"""

import logging
import requests
import json
from abc import ABC, abstractmethod
from typing import Dict, Optional, List, Any

logger = logging.getLogger(__name__)

# ============================================================================
# PROVIDER INTERFACE
# ============================================================================

class Provider(ABC):
    """Base class for all AI providers."""

    def __init__(self, name: str, config: Dict[str, Any]):
        """
        Initialize the provider.

        Args:
            name: Unique name for this provider instance (e.g., 'ollama-smollm')
            config: Provider-specific configuration dict
        """
        self.name = name
        self.config = config

    @abstractmethod
    def summarize(self, text: str, prompt: str = "Summarize this:") -> str:
        """
        Generate a summary for the given text.

        Args:
            text: Input text to summarize
            prompt: Prompt/instruction to use

        Returns:
            Summarized text

        Raises:
            Exception: If the provider fails to generate a summary
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Check if the provider is reachable/available.

        Returns:
            True if available, False otherwise
        """
        pass


# ============================================================================
# PROVIDER IMPLEMENTATIONS
# ============================================================================

class OllamaProvider(Provider):
    """Ollama local LLM provider."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.host = config.get("host", "http://localhost:11434")
        self.model = config.get("model", "llama2")
        self.timeout = config.get("timeout", 120)

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama provider '{self.name}' unavailable: {e}")
            return False

    def summarize(self, text: str, prompt: str = "Summarize this:") -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": f"{prompt}\n\n{text}",
            "stream": True
        }

        try:
            with requests.post(url, json=payload, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                summary = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if "response" in data:
                        summary += data["response"]
                    if data.get("done"):
                        break
                return summary.strip()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Ollama request failed for {self.name}: {e}")


class OpenRouterProvider(Provider):
    """OpenRouter (remote LLM) provider."""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key = config.get("api_key")
        self.model = config.get("model", "openrouter/auto")
        self.timeout = config.get("timeout", 120)

        if not self.api_key:
            raise ValueError(f"OpenRouter provider '{name}' missing api_key")

    def is_available(self) -> bool:
        # Simple check: do we have a key? (Real check would hit API, but we don't want to rate limit)
        return bool(self.api_key)

    def summarize(self, text: str, prompt: str = "Summarize this:") -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": f"{prompt}\n\n{text}"}
            ]
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            result = response.json()
            # OpenRouter response structure
            return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise Exception(f"OpenRouter request failed for {self.name}: {e}")


# ============================================================================
# PROVIDER REGISTRY & CHAIN
# ============================================================================

class ProviderRegistry:
    """Registry to manage named provider instances."""

    def __init__(self):
        self._providers: Dict[str, Provider] = {}

    def register(self, name: str, provider: Provider):
        self._providers[name] = provider
        logger.info(f"Registered provider: {name} ({type(provider).__name__})")

    def get(self, name: str) -> Optional[Provider]:
        return self._providers.get(name)

    def list_providers(self) -> List[str]:
        return list(self._providers.keys())


class ProviderChain:
    """
    A chain of providers that tries the next one if the previous fails.
    Implements the "next_provider" fallback logic.
    """

    def __init__(self, name: str, provider_names: List[str], registry: ProviderRegistry):
        """
        Initialize the chain.

        Args:
            name: Name of this chain (e.g., "discord-chain")
            provider_names: Ordered list of provider names to try
            registry: The registry to look up providers
        """
        self.name = name
        self.provider_names = provider_names
        self.registry = registry

    def summarize(self, text: str, prompt: str = "Summarize this:") -> str:
        """
        Try providers in order until one succeeds.

        Raises:
            Exception: If all providers in the chain fail
        """
        errors = []

        for provider_name in self.provider_names:
            provider = self.registry.get(provider_name)
            if not provider:
                logger.warning(f"Provider '{provider_name}' not found in registry, skipping")
                continue

            logger.info(f"Trying chain '{self.name}' with provider '{provider_name}'")

            try:
                # Check availability first (optional, but good practice)
                if not provider.is_available():
                    logger.warning(f"Provider '{provider_name}' is unavailable, trying next...")
                    continue

                # Attempt summarization
                return provider.summarize(text, prompt)

            except Exception as e:
                logger.warning(f"Provider '{provider_name}' failed: {e}")
                errors.append(f"{provider_name}: {str(e)}")
                continue # Try next provider

        # If we get here, all failed
        raise Exception(f"Chain '{self.name}' failed. Errors: {'; '.join(errors)}")


# ============================================================================
# FACTORY
# ============================================================================

def create_provider_from_config(provider_type: str, name: str, config: Dict) -> Provider:
    """
    Factory to create a provider instance from config.

    Args:
        provider_type: Type of provider ('ollama', 'openrouter')
        name: Name for the provider instance
        config: Configuration dict for the provider

    Returns:
        Provider instance

    Raises:
        ValueError: If provider type is unknown
    """
    if provider_type == 'ollama':
        return OllamaProvider(name, config)
    elif provider_type == 'openrouter':
        return OpenRouterProvider(name, config)
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")