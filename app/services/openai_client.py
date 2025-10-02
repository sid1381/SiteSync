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
        self.model = os.getenv("LLM_MODEL") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self._token_param = None  # Cache which param works for this model

    def chat_completion(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,  # Higher default for gpt-5-mini reasoning tokens
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

        # GPT-4.1 and newer models use max_completion_tokens
        # Check if model needs special handling
        uses_new_api = ("gpt-4.1" in self.model.lower() or
                        "gpt-5" in self.model.lower() or
                        "o1" in self.model.lower())

        if uses_new_api:
            # Newer models: max_completion_tokens, default temperature only
            kwargs["max_completion_tokens"] = max_tokens
            # Don't set temperature or response_format - not supported by some newer models
        else:
            # Older models: max_tokens, custom temperature, response_format
            kwargs["max_tokens"] = max_tokens
            kwargs["temperature"] = temperature
            if response_format:
                kwargs["response_format"] = response_format

        # Debug logging
        logger.info(f"Calling OpenAI with model={self.model}, kwargs keys={list(kwargs.keys())}")

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""

        # Log if response is unexpectedly empty
        if not content:
            logger.error(f"{self.model} returned empty response! Full response: {response}")
            logger.error(f"Prompt was: {user_message[:200]}")

        return content

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

        For GPT-5 models: adds explicit JSON instruction to prompt
        For GPT-4 models: uses response_format parameter
        """
        # Add explicit JSON instruction for newer models
        uses_new_api = ("gpt-4.1" in self.model.lower() or
                        "gpt-5" in self.model.lower() or
                        "o1" in self.model.lower())

        if uses_new_api:
            enhanced_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON with no additional text before or after."
            enhanced_system = (system_message or "You are a helpful assistant.") + " Always return valid JSON only."
        else:
            enhanced_prompt = prompt
            enhanced_system = system_message or "You are a helpful assistant."

        response_text = self.chat_completion(
            system_message=enhanced_system,
            user_message=enhanced_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        # Try to parse JSON, handling potential markdown code blocks
        response_text = response_text.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]  # Remove ```json
        if response_text.startswith("```"):
            response_text = response_text[3:]  # Remove ```
        if response_text.endswith("```"):
            response_text = response_text[:-3]  # Remove trailing ```

        response_text = response_text.strip()

        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response_text[:200]}")
            raise ValueError(f"LLM returned invalid JSON: {str(e)}")


# Global client instance
_client_instance = None

def get_openai_client() -> UnifiedOpenAIClient:
    """Get or create the global OpenAI client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = UnifiedOpenAIClient()
    return _client_instance
