"""
Unified OpenAI Client with runtime auto-detection of correct token parameter.
Handles both max_tokens and max_completion_tokens automatically.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

# Set up logging
logger = logging.getLogger(__name__)

class UnifiedOpenAIClient:
    """
    Unified OpenAI client that auto-detects the correct token parameter at runtime.
    Tries max_tokens first, falls back to max_completion_tokens if needed.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self._token_param = None  # Cache which param works for this model

    def chat_completion(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 500,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Create a chat completion using OpenAI SDK v2.0+

        GPT-5 models require max_completion_tokens parameter.
        GPT-4 and earlier use max_tokens.

        Args:
            system_message: System context for the model
            user_message: User prompt/question
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            response_format: Optional format like {"type": "json_object"}

        Returns:
            The model's response text
        """
        messages = [
            {"role": "system", "content": system_message or "You are a helpful assistant."},
            {"role": "user", "content": user_message}
        ]

        # GPT-5 models use max_completion_tokens, GPT-4 and earlier use max_tokens
        kwargs = {
            "model": self.model,
            "messages": messages,
        }

        # Use max_completion_tokens for gpt-5 models
        # GPT-5 models only support temperature=1 (default), not custom values
        if "gpt-5" in self.model.lower():
            kwargs["max_completion_tokens"] = max_tokens
            # Don't set temperature for gpt-5 - only default (1) is supported
        else:
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature

        if response_format:
            kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content or ""

    def create_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Legacy method name for compatibility. Calls chat_completion.
        """
        return self.chat_completion(
            system_message=system_message or "You are a helpful assistant.",
            user_message=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format
        )

    def create_json_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Create a completion that returns JSON.
        """
        response_text = self.chat_completion(
            system_message=system_message or "You are a helpful assistant.",
            user_message=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        return json.loads(response_text)


# Global client instance
_client_instance = None

def get_openai_client() -> UnifiedOpenAIClient:
    """Get or create the global OpenAI client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = UnifiedOpenAIClient()
    return _client_instance
