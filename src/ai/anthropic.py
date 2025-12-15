"""Anthropic Claude AI provider."""

import os
from typing import Optional

from src.ai.base import AIProvider


class AnthropicProvider(AIProvider):
    """Anthropic Claude API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-3-haiku-20240307",
    ):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "anthropic package not installed. "
                    "Install with: pip install anthropic"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if Anthropic is configured."""
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text using Claude."""
        if not self.is_available():
            raise ValueError("Anthropic API key not configured")

        client = self._get_client()

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            kwargs["system"] = system

        response = client.messages.create(**kwargs)

        # Extract text from response
        return response.content[0].text
