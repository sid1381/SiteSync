# app/routes/drafts.py
from __future__ import annotations
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app import models
from app.scoring import build_autofill_draft
from app.llm_provider import generate

router = APIRouter(prefix="/drafts", tags=["drafts"])

class QuestionIn(BaseModel):
    id: str = Field(..., description="Stable ID for the question (use any unique string)")
    text: str = Field(..., description="The sponsor's question text")
    key: Optional[str] = Field(None, description="Optional internal key to map factual fills")

class DraftRequest(BaseModel):
    protocol_id: int
    site_id: int
    questions: List[QuestionIn]

class DraftOut(BaseModel):
    protocol_id: int
    site_id: int
    answers: Dict[str, str]  # {question_id: drafted_text}
    notes: Optional[str] = None

SYSTEM_INSTRUCTIONS = """You are assisting a clinical research site to answer sponsor feasibility questions.
- Only use the provided site facts and protocol context.
- Do NOT fabricate specific patient identities or PHI.
- Be concise, professional, and directly answer the question.
- If data is missing, say 'Unknown – requires site input' and suggest the minimal data needed.
- Keep sensitive info aggregated (counts, capabilities) rather than patient-level details.
"""

def _format_context(protocol: models.Protocol, objective_answers: Dict[str, Any], missing: List[str]) -> str:
    lines = []
    lines.append(f"Protocol: {protocol.name} (Phase: {protocol.phase or 'NA'}, NCT: {protocol.nct_id or 'NA'})")
    if objective_answers:
        lines.append("Known objective answers:")
        for k, v in objective_answers.items():
            lines.append(f"- {k}: {v}")
    if missing:
        lines.append("Missing factual fields:")
        for k in missing:
            lines.append(f"- {k}")
    return "\n".join(lines)

@router.post("/autofill", response_model=DraftOut)
def draft_autofill(body: DraftRequest, db: Session = Depends(get_session)):
    protocol = db.get(models.Protocol, body.protocol_id)
    site = db.get(models.Site, body.site_id)
    if not protocol or not site:
        raise HTTPException(status_code=404, detail="Protocol or site not found")

    # Reuse your existing builder to get objective fills & what’s missing
    base = build_autofill_draft(db, body.protocol_id, body.site_id)
    if "error" in base:
        raise HTTPException(status_code=400, detail=base["error"])

    objective = base.get("objective_answers", {})
    missing = base.get("unresolved_missing_data", [])
    subjective = base.get("unresolved_subjective", [])

    # Build a clean context
    context = _format_context(protocol, objective, missing)

    # Build a single prompt asking for JSON answers keyed by question IDs
    questions_json = [{ "id": q.id, "text": q.text, "key": q.key } for q in body.questions]
    user_prompt = f"""
CONTEXT
{context}

QUESTIONS (return a JSON object mapping question id -> answer string):
{questions_json}

NOTES
- Where objective facts exist (e.g., age ranges, scanners, EHR), use them explicitly.
- If subjective (e.g., PI commitment), provide a concise draft and mark where the site should edit.
- Keep answers 1–3 sentences each.
"""

    messages = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
        {"role": "user", "content": user_prompt.strip()},
    ]

    raw = generate(messages, temperature=0.15, max_tokens=900).strip()

    # Try to parse a top-level JSON object. If not JSON, wrap as a single note-answer.
    answers: Dict[str, str] = {}
    try:
        maybe = raw
        # Some models reply with code fences; strip them
        if maybe.startswith("```"):
            maybe = maybe.strip("`")
            # remove leading 'json' if present
            if maybe.lower().startswith("json"):
                maybe = maybe[4:]
        data = json.loads(maybe)  # type: ignore[name-defined]
        if isinstance(data, dict):
            # Ensure only known ids are kept, values are strings
            ids = {q.id for q in body.questions}
            for k, v in data.items():
                if k in ids:
                    answers[k] = v if isinstance(v, str) else str(v)
    except Exception:
        # fallback: single blob into all questions
        for q in body.questions:
            answers[q.id] = f"(Model freeform output)\n{raw}"

    # Guarantee every question has an answer
    for q in body.questions:
        answers.setdefault(q.id, "Unknown – requires site input")

    return DraftOut(
        protocol_id=body.protocol_id,
        site_id=body.site_id,
        answers=answers,
        notes="Generated with site facts; review subjective items before sending to sponsors."
    )
