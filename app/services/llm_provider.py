# app/llm_provider.py
from __future__ import annotations
import os
from typing import List, Dict

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" | "none"

def _openai_chat(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
    """
    Call OpenAI using unified client with automatic parameter detection
    """
    from app.services.openai_client import get_openai_client

    client = get_openai_client()

    # Extract system and user messages
    system_message = ""
    user_message = ""

    for msg in messages:
        if msg.get("role") == "system":
            system_message = msg.get("content", "")
        elif msg.get("role") == "user":
            user_message = msg.get("content", "")

    # If no explicit system/user split, use first as system, last as user
    if not system_message and not user_message:
        if len(messages) == 1:
            user_message = messages[0].get("content", "")
        elif len(messages) >= 2:
            system_message = messages[0].get("content", "")
            user_message = messages[-1].get("content", "")

    # Use unified client's chat_completion method
    return client.chat_completion(
        system_message=system_message or "You are a helpful assistant.",
        user_message=user_message,
        temperature=temperature,
        max_tokens=max_tokens
    )

def _local_fallback(messages: List[Dict[str, str]], **_) -> str:
    # Deterministic, no-API fallback: echoes the "questions" with simple factual fills if present in context.
    # This keeps demos running when you don't have a key.
    system = messages[0]["content"] if messages else ""
    user = messages[-1]["content"] if messages else ""
    return (
        "NOTE: Local fallback (no API key). Provide concise factual answers and mark subjective items.\n\n"
        f"System:\n{system}\n\nUser:\n{user}\n"
    )

def generate(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
    """
    Generate a completion using configured LLM provider.
    Routes through unified OpenAI client for automatic parameter detection.
    """
    if PROVIDER == "openai":
        try:
            return _openai_chat(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            print(f"OpenAI call failed: {e}")
            # Don't crash the demo — fall back to local
            return _local_fallback(messages)
    else:
        return _local_fallback(messages)
