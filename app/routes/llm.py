# app/routes/llm.py
from __future__ import annotations
import math, os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

router = APIRouter(prefix="/llm", tags=["llm"])
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

def get_client():
    try:
        return OpenAI()  # reads OPENAI_API_KEY from env
    except TypeError as e:
        # Clear error if httpx is wrong version
        raise HTTPException(status_code=500, detail=f"LLM client init failed: {e}. Pin httpx==0.27.2")

class TestIn(BaseModel):
    prompt: str
    max_output_tokens: int = 250

@router.post("/test")
def llm_test(body: TestIn):
    try:
        client = get_client()
        r = client.responses.create(
            model=MODEL,
            input=body.prompt,
            max_output_tokens=body.max_output_tokens,
        )
        text = getattr(r, "output_text", None) or str(r)
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
