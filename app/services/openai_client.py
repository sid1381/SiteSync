"""
Unified OpenAI Client with support for both Responses API (gpt-5) and Chat Completions API (gpt-4o)
Automatically detects and uses the appropriate API with fallback
"""
import os
import json
import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI

# Set up logging
logger = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "gpt-5-mini")

class UnifiedOpenAIClient:
    """
    Wrapper around OpenAI client that supports both new Responses API and legacy Chat Completions API
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=self.api_key)
        self.model = MODEL

    def create_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Create a completion using the appropriate API

        Args:
            prompt: The user prompt/question
            system_message: Optional system message for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            response_format: Optional response format (e.g., {"type": "json_object"})

        Returns:
            The model's response text
        """
        # Try Responses API first (for gpt-5 and newer models)
        try:
            if hasattr(self.client, 'responses'):
                logger.info(f"Attempting {self.model} with Responses API...")

                # Format input for Responses API
                full_prompt = prompt
                if system_message:
                    full_prompt = f"{system_message}\n\n{prompt}"

                resp = self.client.responses.create(
                    model=self.model,
                    input=full_prompt,
                    max_output_tokens=max_tokens,
                )

                result = getattr(resp, "output_text", None) or str(resp)
                logger.info(f"✓ Successfully using model: {self.model} (Responses API)")
                return result
        except (AttributeError, Exception) as e:
            # Responses API not available or failed
            logger.warning(f"Responses API failed ({type(e).__name__}: {e}), falling back to Chat Completions API")

        # Fallback to Chat Completions API (always use configured fallback model)
        messages = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": prompt})

        # Use configured fallback model (defaults to gpt-5-mini for quality and rate limits)
        fallback_model = FALLBACK_MODEL

        logger.info(f"Using Chat Completions API with model: {fallback_model}")

        # Chat Completions API ALWAYS uses max_tokens regardless of model
        kwargs = {
            "model": fallback_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if response_format:
            kwargs["response_format"] = response_format

        resp = self.client.chat.completions.create(**kwargs)
        result = resp.choices[0].message.content or ""

        logger.info(f"✓ Successfully using model: {fallback_model} (Chat Completions API)")
        return result

    def create_json_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000
    ) -> Dict[str, Any]:
        """
        Create a completion that returns JSON

        Args:
            prompt: The user prompt/question
            system_message: Optional system message for context
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON response as dictionary
        """
        response_text = self.create_completion(
            prompt=prompt,
            system_message=system_message,
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
