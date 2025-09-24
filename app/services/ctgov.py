# app/ctgov.py
from __future__ import annotations
import re
from typing import Any, Dict, List, Optional
import requests

API_BASE = "https://clinicaltrials.gov/api/v2"

def fetch_study(nct_id: str) -> Dict[str, Any]:
    nct_id = nct_id.strip().upper()
    r = requests.get(f"{API_BASE}/studies/{nct_id}", timeout=15)
    if r.status_code != 200:
        raise RuntimeError(f"CT.gov fetch failed: {r.status_code}")
    return r.json()

# --- helpers to normalize ages ---
_AGE_RE = re.compile(r"(?i)\b(\d+)\s*(year|yr|years|yrs|y)\b")
def _age_to_years(age: Optional[str]) -> Optional[int]:
    if not age:
        return None
    s = age.strip()
    # Try ISO 8601 duration like 'P18Y'
    m = re.match(r"(?i)P(\d+)Y", s)
    if m:
        return int(m.group(1))
    # Try '18 Years' etc.
    m = _AGE_RE.search(s)
    if m:
        return int(m.group(1))
    # Try plain number
    try:
        return int(float(s))
    except:
        return None

def build_requirements_from_ctgov(study_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return {protocol_meta, requirements[]} using eligibility + phase.
    Keeps this minimal and deterministic for your rules engine.
    """
    study = study_json.get("studies", [{}])[0] if "studies" in study_json else study_json
    id_info = study.get("protocolSection", {}).get("identificationModule", {})
    nct_id = id_info.get("nctId")
    brief_title = id_info.get("briefTitle")

    elig = study.get("protocolSection", {}).get("eligibilityModule", {}) or {}
    min_age = _age_to_years(elig.get("minimumAge"))
    max_age = _age_to_years(elig.get("maximumAge"))
    sex = (elig.get("sex", "") or "").lower()  # "all" | "male" | "female"

    design = study.get("protocolSection", {}).get("designModule", {}) or {}
    phase = (design.get("phases") or [])
    # phases is array like ["PHASE2"], normalize simple string
    phase_simple = phase[0] if phase else None

    reqs: List[Dict[str, Any]] = []

    # Age/sex → site capabilities must cover them
    if min_age is not None:
        reqs.append({
            "key": "patient_age_min_years",
            "op": "<=",
            "value": min_age,
            "weight": 2,
            "type": "objective",
            "source_question": f"Protocol minimum age: {min_age}"
        })
    if max_age is not None:
        reqs.append({
            "key": "patient_age_max_years",
            "op": ">=",
            "value": max_age,
            "weight": 2,
            "type": "objective",
            "source_question": f"Protocol maximum age: {max_age}"
        })
    if sex in ("all", "male", "female"):
        reqs.append({
            "key": "patient_sex",
            "op": "in",
            "value": ["all", sex],  # site 'all' or exact match
            "weight": 1,
            "type": "objective",
            "source_question": f"Sex eligibility: {sex}"
        })

    # Phase (optional; only if you later add a truth key for phase capability)
    if phase_simple:
        reqs.append({
            "key": "phase_experience",
            "op": "in",
            "value": [phase_simple, "ANY"],
            "weight": 1,
            "type": "objective",
            "source_question": f"Study phase: {phase_simple}"
        })

    return {
        "protocol_meta": {
            "name": brief_title or nct_id or "CT.gov Study",
            "nct_id": nct_id,
            "phase": phase_simple
        },
        "requirements": reqs
    }
