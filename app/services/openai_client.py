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
        Create a chat completion with automatic parameter detection.

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

        # If we've already detected which param works, use it
        if self._token_param:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                self._token_param: max_tokens
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = self.client.chat.completions.create(**kwargs)
            return response.choices[0].message.content or ""

        # Try max_tokens first (works for gpt-4, gpt-3.5)
        # Some models like gpt-5-mini require max_completion_tokens instead
        try:
            kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            if response_format:
                kwargs["response_format"] = response_format

            response = self.client.chat.completions.create(**kwargs)
            self._token_param = "max_tokens"
            logger.info(f"✓ Using max_tokens with {self.model}")
            return response.choices[0].message.content or ""
        except Exception as e:
            error_msg = str(e)
            # OpenAI API explicitly says to use max_completion_tokens
            if "max_completion_tokens" in error_msg and "Unsupported parameter" in error_msg:
                logger.info(f"Retrying with max_completion_tokens for {self.model}")
                # Remove max_tokens, add max_completion_tokens
                kwargs.pop("max_tokens", None)
                kwargs["max_completion_tokens"] = max_tokens

                response = self.client.chat.completions.create(**kwargs)
                self._token_param = "max_completion_tokens"
                logger.info(f"✓ Using max_completion_tokens with {self.model}")
                return response.choices[0].message.content or ""
            # If it's a different error, raise it
            raise

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
