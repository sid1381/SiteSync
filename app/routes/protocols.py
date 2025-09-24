# app/routes/protocols.py
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_session
from app import models
from app.services.scoring import score_protocol_for_site, parse_value
from app.services.autofill import build_autofill_draft
from app.services.ctgov import fetch_study, build_requirements_from_ctgov

router = APIRouter(prefix="/protocols", tags=["protocols"])

# ---------------------------
# Schemas
# ---------------------------

class ProtocolCreate(BaseModel):
    name: str
    sponsor: Optional[str] = None
    disease: Optional[str] = None
    phase: Optional[str] = None
    nct_id: Optional[str] = None
    notes: Optional[str] = None

class RequirementIn(BaseModel):
    key: str
    op: str  # "==", ">=", "<=", ">", "<", "in", "n/a" (for subjective placeholders)
    value: Any = None
    weight: int = 1
    type: str = Field(default="objective", pattern="^(objective|subjective)$")
    source_question: Optional[str] = None

class ProtocolOut(BaseModel):
    id: int
    name: str
    sponsor: Optional[str]
    disease: Optional[str]
    phase: Optional[str]
    nct_id: Optional[str]
    notes: Optional[str]

    class Config:
        from_attributes = True

class CtgovImportIn(BaseModel):
    nct_id: str

class PatientCapIn(BaseModel):
    indication_label: Optional[str] = None
    indication_code: Optional[str] = None
    age_min_years: Optional[int] = None
    age_max_years: Optional[int] = None
    sex: Optional[str] = "all"
    annual_eligible_patients: Optional[int] = None
    notes: Optional[str] = None
    evidence_url: Optional[str] = None

# Allowed operators for quick validation
ALLOWED_OPS = {"==", ">=", "<=", ">", "<", "in", "n/a"}

# ---------------------------
# CT.gov import
# ---------------------------

@router.post("/import/ctgov")
def import_ctgov(body: CtgovImportIn, db: Session = Depends(get_session)):
    """Create a Protocol + objective requirements from CT.gov eligibility."""
    data = fetch_study(body.nct_id)
    bundle = build_requirements_from_ctgov(data)
    meta = bundle["protocol_meta"]
    reqs = bundle["requirements"]

    p = models.Protocol(
        name=meta.get("name") or body.nct_id,
        sponsor=None,
        disease=None,
        phase=meta.get("phase"),
        nct_id=meta.get("nct_id"),
        notes=f"Imported from CT.gov NCT {body.nct_id}",
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    for it in reqs:
        op = it.get("op")
        if op not in ALLOWED_OPS:
            raise HTTPException(status_code=400, detail=f"Invalid op in import: {op}")

        r = models.ProtocolRequirement(
            protocol_id=p.id,
            key=it["key"],
            op=op,
            value=str(it.get("value")),
            weight=int(it.get("weight", 1)),
            type=it.get("type", "objective"),
            source_question=it.get("source_question"),
        )
        db.add(r)
    db.commit()

    return {"protocol_id": p.id, "requirements_added": [r.key for r in p.requirements]}

# ---------------------------
# Protocol CRUD
# ---------------------------

@router.post("", response_model=ProtocolOut)
def create_protocol(body: ProtocolCreate, db: Session = Depends(get_session)):
    p = models.Protocol(
        name=body.name,
        sponsor=body.sponsor,
        disease=body.disease,
        phase=body.phase,
        nct_id=body.nct_id,
        notes=body.notes,
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p

@router.get("", response_model=List[ProtocolOut])
def list_protocols(db: Session = Depends(get_session)):
    return db.query(models.Protocol).order_by(models.Protocol.id.asc()).all()

@router.get("/{protocol_id}", response_model=ProtocolOut)
def get_protocol(protocol_id: int, db: Session = Depends(get_session)):
    p = db.get(models.Protocol, protocol_id)
    if not p:
        raise HTTPException(status_code=404, detail="Protocol not found")
    return p

# ---------------------------
# Requirements
# ---------------------------

@router.post("/{protocol_id}/requirements")
def add_requirements(protocol_id: int, items: List[RequirementIn], db: Session = Depends(get_session)):
    p = db.get(models.Protocol, protocol_id)
    if not p:
        raise HTTPException(status_code=404, detail="Protocol not found")

    created = []
    for it in items:
        if it.op not in ALLOWED_OPS:
            raise HTTPException(status_code=400, detail=f"Invalid op: {it.op}")
        r = models.ProtocolRequirement(
            protocol_id=protocol_id,
            key=it.key,
            op=it.op,
            value=str(it.value) if not isinstance(it.value, str) else it.value,
            weight=it.weight,
            type=it.type,
            source_question=it.source_question,
        )
        db.add(r)
        created.append(it.key)
    db.commit()
    return {"added": created, "count": len(created)}

@router.get("/{protocol_id}/requirements")
def list_requirements(protocol_id: int, db: Session = Depends(get_session)):
    rows = db.query(models.ProtocolRequirement).filter(models.ProtocolRequirement.protocol_id == protocol_id).all()
    return [
        {
            "id": r.id,
            "key": r.key,
            "op": r.op,
            "value": parse_value(r.value),
            "weight": r.weight,
            "type": r.type,
            "source_question": r.source_question,
        }
        for r in rows
    ]

# ---------------------------
# Scoring & Autofill
# ---------------------------

@router.post("/{protocol_id}/score")
def score(protocol_id: int, site_id: int, db: Session = Depends(get_session)):
    out = score_protocol_for_site(db, protocol_id, site_id)
    if "error" in out:
        raise HTTPException(status_code=404, detail=out["error"])
    return out

@router.post("/{protocol_id}/autofill")
def autofill(protocol_id: int, site_id: int, db: Session = Depends(get_session)):
    out = build_autofill_draft(db, protocol_id, site_id)
    if "error" in out:
        raise HTTPException(status_code=404, detail=out["error"])
    return out

# ---------------------------
# Site patient capabilities (demo helper)
# ---------------------------

@router.post("/site/{site_id}/patient-capabilities")
def upsert_patient_caps(site_id: int, caps: List[PatientCapIn], db: Session = Depends(get_session)):
    """Demo-only: replace all patient-capability rows for a site."""
    db.query(models.SitePatientCapability).filter(models.SitePatientCapability.site_id == site_id).delete()
    for c in caps:
        row = models.SitePatientCapability(
            site_id=site_id,
            indication_label=c.indication_label,
            indication_code=c.indication_code,
            age_min_years=c.age_min_years,
            age_max_years=c.age_max_years,
            sex=(c.sex or "all").lower(),
            annual_eligible_patients=c.annual_eligible_patients,
            notes=c.notes,
            evidence_url=c.evidence_url,
        )
        db.add(row)
    db.commit()
    return {"status": "ok", "count": len(caps)}
@router.get("/{protocol_id}/score/pretty")
def score_pretty(protocol_id: int, site_id: int, db: Session = Depends(get_session)):
    """Human-readable summary for slide/email."""
    out = score_protocol_for_site(db, protocol_id, site_id)
    if "error" in out:
        raise HTTPException(status_code=404, detail=out["error"])

    conf = out.get("confidence", 0)
    matches = out.get("matches", [])
    misses = out.get("misses", [])
    subj = out.get("subjective", [])

    def fmt_match(m):
        key = m.get("key")
        rule = m.get("rule")
        val = m.get("site_value")
        return f"✓ {key}: {val} (meets {rule})"

    def fmt_miss(m):
        key = m.get("key")
        rule = m.get("rule")
        val = m.get("site_value")
        return f"✗ {key}: {val} (fails {rule})"

    def fmt_subj(s):
        return f"• Needs input: {s.get('key')} — {s.get('source_question')}"

    lines = [
        f"Protocol #{protocol_id} vs Site #{site_id}",
        f"Confidence: {conf:.1f}%",
        "",
        "Matches:"
    ] + ([fmt_match(m) for m in matches] or ["(none)"]) + [
        "",
        "Misses:"
    ] + ([fmt_miss(m) for m in misses] or ["(none)"]) + [
        "",
        "Subjective items:"
    ] + ([fmt_subj(s) for s in subj] or ["(none)"])

    return {"summary": "\n".join(lines)}
