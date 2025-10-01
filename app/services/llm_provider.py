# app/llm_provider.py
from __future__ import annotations
import os
import json
from typing import List, Dict, Any, Optional

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" | "none"
MODEL = os.getenv("LLM_MODEL", "gpt-4o")
FALLBACK_MODEL = os.getenv("LLM_FALLBACK_MODEL", "gpt-4o")
TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECS", "20"))

def _openai_chat(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
    """
    Call OpenAI with automatic API detection and fallback
    Tries new Responses API first (for gpt-5), falls back to Chat Completions API
    """
    try:
        from openai import OpenAI  # pip install openai
    except Exception as e:
        raise RuntimeError("OpenAI SDK not installed. Add `openai` to requirements.txt") from e

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)

    # Try new Responses API first (for gpt-5 and future models)
    try:
        if hasattr(client, 'responses'):
            # Convert messages format for new API
            if len(messages) == 1:
                prompt_content = messages[0]["content"]
            else:
                # Combine system + user messages
                prompt_content = "\n\n".join([f"{msg['role']}: {msg['content']}" for msg in messages])

            resp = client.responses.create(
                model=MODEL,
                input=prompt_content,
                max_output_tokens=max_tokens,
            )
            return getattr(resp, "output_text", None) or str(resp)
    except (AttributeError, Exception) as e:
        # Responses API not available or failed, fall back to chat completions
        print(f"Responses API unavailable ({e}), falling back to chat.completions API")
        pass

    # Fallback to standard Chat Completions API (always use gpt-4o for quality)
    fallback_model = FALLBACK_MODEL
    resp = client.chat.completions.create(
        model=fallback_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=TIMEOUT,
    )
    return resp.choices[0].message.content or ""

def _local_fallback(messages: List[Dict[str, str]], **_) -> str:
    # Deterministic, no-API fallback: echoes the “questions” with simple factual fills if present in context.
    # This keeps demos running when you don’t have a key.
    system = messages[0]["content"] if messages else ""
    user = messages[-1]["content"] if messages else ""
    return (
        "NOTE: Local fallback (no API key). Provide concise factual answers and mark subjective items.\n\n"
        f"System:\n{system}\n\nUser:\n{user}\n"
    )

def generate(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
    if PROVIDER == "openai":
        try:
            return _openai_chat(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            # Don’t crash the demo — fall back to local
            return _local_fallback(messages)
    else:
        return _local_fallback(messages)
