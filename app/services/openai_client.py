"""
Unified OpenAI Client for GPT-4o.
OpenAI SDK 2.0.1, Chat Completions API with structured outputs.
Optimized for high TPM tier with GPT-4o's advanced reasoning capabilities.
Includes automatic retry logic for transient API failures.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from openai import OpenAI
import openai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)

logger = logging.getLogger(__name__)

class UnifiedOpenAIClient:
    """
    Production OpenAI client using GPT-4o exclusively.
    - SDK: OpenAI Python SDK 2.0.1+
    - Model: GPT-4o (gpt-4o) - flagship model with best reasoning + speed
    - API: Chat Completions with response_format support
    - Parameters: max_tokens, temperature, response_format
    - Optimized for high TPM tier accounts
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")
        self.client = OpenAI(api_key=self.api_key)
        # Force GPT-4o, ignore environment variable for consistency
        self.model = "gpt-4o"
        logger.info(f"🤖 OpenAI Client initialized with model: {self.model}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.InternalServerError
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True
    )
    def chat_completion(
        self,
        system_message: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 4000,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        Call Chat Completions API using GPT-4o with automatic retry logic.

        Retries on transient failures:
        - RateLimitError: Exceeded TPM/RPM limits (waits exponentially)
        - APITimeoutError: Request timed out (retries up to 3 times)
        - APIConnectionError: Network connectivity issues (retries)
        - InternalServerError: OpenAI server errors (retries)

        Does NOT retry on:
        - AuthenticationError: Invalid API key (immediate fail)
        - BadRequestError: Invalid parameters (immediate fail)

        GPT-4o supports:
        - max_tokens: Output token limit (default 4000 for complex responses)
        - temperature: Sampling temperature (0.0-2.0, default 0.1 for consistency)
        - response_format: {"type": "json_object"} for JSON responses

        Returns:
            str: The completion text from GPT-4o

        Raises:
            openai.AuthenticationError: Invalid API key
            openai.BadRequestError: Invalid request parameters
            openai.RateLimitError: Rate limit exceeded after 3 retries
            ValueError: Empty response from GPT-4o
        """
        messages = [
            {"role": "system", "content": system_message or "You are a helpful assistant."},
            {"role": "user", "content": user_message}
        ]

        # GPT-4o parameters (standard model, not reasoning)
        kwargs = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if response_format:
            kwargs["response_format"] = response_format

        try:
            response = self.client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason

            # Log response metadata
            logger.debug(f"✅ GPT-4o response: length={len(content)}, finish_reason={finish_reason}, tokens={response.usage.total_tokens if response.usage else 'N/A'}")

            if not content:
                logger.error(f"❌ Empty response! finish_reason={finish_reason}, usage={response.usage}")
                logger.error(f"Prompt preview: {user_message[:200]}...")
                raise ValueError(f"GPT-4o returned empty response (finish_reason: {finish_reason})")

            return content

        except (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError, openai.InternalServerError) as e:
            # These exceptions trigger retry (handled by @retry decorator)
            logger.warning(f"⚠️ Retryable GPT-4o error: {type(e).__name__}: {e}")
            raise

        except (openai.AuthenticationError, openai.BadRequestError) as e:
            # These exceptions DO NOT retry (fatal errors)
            logger.error(f"❌ Fatal GPT-4o error (no retry): {type(e).__name__}: {e}")
            raise

        except Exception as e:
            # Unknown exceptions (log and raise)
            logger.error(f"❌ Unexpected GPT-4o error: {type(e).__name__}: {e}")
            raise

    def create_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4000
    ) -> str:
        """
        Legacy method name for compatibility.
        Calls chat_completion with GPT-4o.
        """
        return self.chat_completion(
            system_message=system_message or "You are a helpful assistant.",
            user_message=prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )

    def create_json_completion(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4000
    ) -> Dict[str, Any]:
        """
        Get structured JSON response from GPT-4o.

        GPT-4o natively supports response_format=json_object for reliable JSON output.
        No manual parsing or markdown stripping needed with structured outputs.

        Args:
            prompt: The user prompt
            system_message: System instructions (should mention JSON format)
            temperature: Sampling temperature (default 0.1)
            max_tokens: Max output tokens (default 4000 for large JSON responses)

        Returns:
            Dict[str, Any]: Parsed JSON response

        Raises:
            ValueError: If JSON parsing fails
        """
        # GPT-4o: Use native response_format for guaranteed JSON
        response_text = self.chat_completion(
            system_message=system_message or "You are a helpful assistant. Always return valid JSON.",
            user_message=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )

        # Strip markdown code fences (defensive, shouldn't be needed with response_format)
        response_text = response_text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
            logger.warning("⚠️ GPT-4o returned markdown despite response_format=json_object")
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        # Parse JSON
        try:
            parsed = json.loads(response_text)
            logger.debug(f"✅ JSON parsed successfully: {len(parsed)} keys")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse failed for GPT-4o response")
            logger.error(f"Response preview: {response_text[:500]}...")
            raise ValueError(f"GPT-4o returned invalid JSON: {str(e)}")


# Global client instance
_client_instance = None

def get_openai_client() -> UnifiedOpenAIClient:
    """Get or create the global OpenAI client instance"""
    global _client_instance
    if _client_instance is None:
        _client_instance = UnifiedOpenAIClient()
    return _client_instance
