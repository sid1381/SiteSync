# app/routes/llm.py
from __future__ import annotations
import math, os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.openai_client import get_openai_client

router = APIRouter(prefix="/llm", tags=["llm"])
MODEL = os.getenv("LLM_MODEL", "gpt-5-mini")

class TestIn(BaseModel):
    prompt: str
    max_output_tokens: int = 250

@router.post("/test")
def llm_test(body: TestIn):
    try:
        client = get_openai_client()
        text = client.chat_completion(
            system_message="You are a helpful assistant.",
            user_message=body.prompt,
            max_tokens=body.max_output_tokens,
        )
        return {"model": MODEL, "text": text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")

class EstimateIn(BaseModel):
    prompt: str
    expected_output_tokens: int = 250

@router.post("/estimate")
def estimate_cost(body: EstimateIn):
    tokens_in = math.ceil(len(body.prompt) / 4)  # ~4 chars/token
    tokens_out = body.expected_output_tokens
    cost_in = tokens_in * 0.60 / 1_000_000     # $0.60 / 1M input
    cost_out = tokens_out * 2.40 / 1_000_000   # $2.40 / 1M output
    return {
        "model": MODEL,
        "estimated_tokens": {"input": tokens_in, "output": tokens_out},
        "estimated_usd": round(cost_in + cost_out, 6),
        "assumptions": "4 chars ≈ 1 token; GPT-4o-mini text pricing."
    }
