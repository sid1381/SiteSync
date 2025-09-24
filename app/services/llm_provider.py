# app/llm_provider.py
from __future__ import annotations
import os
import json
from typing import List, Dict, Any, Optional

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" | "none"
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
TIMEOUT = int(os.getenv("LLM_TIMEOUT_SECS", "20"))

def _openai_chat(messages: List[Dict[str, str]], temperature: float = 0.2, max_tokens: int = 800) -> str:
    try:
        from openai import OpenAI  # pip install openai
    except Exception as e:
        raise RuntimeError("OpenAI SDK not installed. Add `openai` to requirements.txt") from e

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)
    resp = client.chat.completions.create(
        model=MODEL,
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
