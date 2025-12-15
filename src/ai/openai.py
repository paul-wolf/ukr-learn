"""OpenAI GPT AI provider."""

import os
from typing import Optional

from src.ai.base import AIProvider


class OpenAIProvider(AIProvider):
    """OpenAI GPT API provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = model
        self._client = None

    def _get_client(self):
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                import openai
                self._client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client

    def is_available(self) -> bool:
        """Check if OpenAI is configured."""
        return bool(self.api_key)

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 2000,
    ) -> str:
        """Generate text using GPT."""
        if not self.is_available():
            raise ValueError("OpenAI API key not configured")

        client = self._get_client()

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )

        return response.choices[0].message.content
