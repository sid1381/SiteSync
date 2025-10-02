"""
Unified OpenAI Client for gpt-5-mini (stable recipe).
OpenAI SDK 2.0.1, Chat Completions API, max_tokens parameter only.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

class UnifiedOpenAIClient:
    """
    Stable OpenAI client for gpt-5-mini.
    - SDK: 2.0.1
    - API: Chat Completions only
    - Param: max_completion_tokens (API requirement for gpt-5-mini)
    - Budget: 1000-2000 tokens for reasoning overhead
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=self.api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-5-mini")

    def chat_completion(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Call Chat Completions API.

        gpt-4o-mini: uses max_tokens + response_format (standard)
        gpt-5-mini: uses max_completion_tokens (reasoning model)
        """
        messages = [
            {"role": "system", "content": system_message or "You are a helpful assistant."},
            {"role": "user", "content": user_message}
        ]

        # Model-specific parameters
        if "gpt-5" in self.model.lower():
            # gpt-5-mini: reasoning model, needs max_completion_tokens
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_completion_tokens": max_tokens
            }
        else:
            # gpt-4o-mini and others: standard models
            kwargs = {
                "model": self.model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            if response_format:
                kwargs["response_format"] = response_format

        response = self.client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason

        # Log for debugging truncation
        logger.info(f"OpenAI response: model={self.model}, length={len(content)}, finish_reason={finish_reason}")

        if not content:
            logger.error(f"Empty response! finish_reason={finish_reason}, usage={response.usage}")
            logger.error(f"Prompt was: {user_message[:200]}")

        return content

    def create_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> str:
        """Legacy method name for compatibility."""
        return self.chat_completion(
            system_message=system_message or "You are a helpful assistant.",
            user_message=prompt,
            max_tokens=max_tokens
        )

    def create_json_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Get JSON response.

        gpt-4o-mini: uses response_format=json_object (fast, reliable)
        gpt-5-mini: manual parsing (response_format not supported)
        """
        if "gpt-5" in self.model.lower():
            # gpt-5-mini: explicit prompt + manual parsing
            enhanced_prompt = f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON with no additional text before or after."
            enhanced_system = (system_message or "You are a helpful assistant.") + " Always return valid JSON only."

            response_text = self.chat_completion(
                system_message=enhanced_system,
                user_message=enhanced_prompt,
                max_tokens=max_tokens
            )
        else:
            # gpt-4o-mini: use response_format
            response_text = self.chat_completion(
                system_message=system_message or "You are a helpful assistant.",
                user_message=prompt,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"}
            )

        # Strip markdown code fences
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse failed: {response_text[:200]}")
            raise ValueError(f"LLM returned invalid JSON: {str(e)}")


# Global client instance
_client_instance = None

def get_openai_client() -> UnifiedOpenAIClient:
    """Get or create the global OpenAI client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = UnifiedOpenAIClient()
    return _client_instance
