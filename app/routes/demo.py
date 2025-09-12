from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session
from app.db import get_session
from app import models

router = APIRouter(prefix="/demo", tags=["demo"])

# ----- Demo: seed sample data -----

@router.post("/seed")
def seed(db: Session = Depends(get_session)):
    # Helper: get or create site by name
    def get_or_create_site(name: str, address: str) -> models.Site:
        site = db.query(models.Site).filter(models.Site.name == name).first()
        if site:
            return site
        site = models.Site(name=name, address=address)
        db.add(site)
        db.commit()
        db.refresh(site)
        return site

    def add_truth(site_id: int, key: str, value: str, unit: Optional[str] = None, evidence_required: bool = False):
        tf = models.SiteTruthField(
            site_id=site_id, key=key, value=value, unit=unit, evidence_required=evidence_required
        )
        db.add(tf)

    # Sample sites
    s1 = get_or_create_site("Brown Uni Site", "Van Wickle St")
    s2 = get_or_create_site("Providence Research Center", "123 Hope St")
    s3 = get_or_create_site("East Bay Clinical", "456 Bay Ave")

    # Wipe existing truth for a clean demo (optional)
    db.query(models.SiteTruthField).delete()
    db.commit()

    # Sample truth fields (toy data)
    add_truth(s1.id, "ct_scanners", "2", "units", True)
    add_truth(s1.id, "ehr_vendor", "Epic")
    add_truth(s1.id, "crc_fte", "1.5", "FTE")
    add_truth(s1.id, "onc_trials_last_12mo", "3", "trials")

    add_truth(s2.id, "ct_scanners", "0", "units", True)
    add_truth(s2.id, "ehr_vendor", "Cerner")
    add_truth(s2.id, "crc_fte", "0.8", "FTE")
    add_truth(s2.id, "onc_trials_last_12mo", "1", "trials")

    add_truth(s3.id, "ct_scanners", "1", "units", True)
    add_truth(s3.id, "ehr_vendor", "Athena")
    add_truth(s3.id, "crc_fte", "2.0", "FTE")
    add_truth(s3.id, "onc_trials_last_12mo", "5", "trials")

    db.commit()

    return {"status": "seeded", "sites": [s1.id, s2.id, s3.id]}

# ----- Demo: simple ranking -----

class Rule(BaseModel):
    key: str                 # e.g. "ct_scanners"
    op: str                  # one of: "==", ">=", "<=", ">", "<", "in"
    value: Any               # e.g. 1, "Epic", ["Epic","Cerner"]
    weight: int = 1          # how important this rule is

class RankRequest(BaseModel):
    site_ids: Optional[List[int]] = None  # if None, evaluate all sites
    rules: List[Rule]

def _to_number(s: str):
    try:
        return float(s)
    except:
        return None

def evaluate_rule(rule: Rule, field_value: Optional[str]) -> bool:
    if field_value is None:
        return False

    # Numeric-aware comparisons if possible
    fv_num = _to_number(field_value) if isinstance(field_value, str) else None
    rv_num = rule.value if isinstance(rule.value, (int, float)) else _to_number(str(rule.value)) if rule.op in (">=", "<=", ">", "<") else None

    if rule.op == "==":
        return str(field_value).strip().lower() == str(rule.value).strip().lower()
    if rule.op == "in":
        if not isinstance(rule.value, list):
            return False
        return str(field_value).strip().lower() in [str(v).strip().lower() for v in rule.value]
    if rule.op in (">=", "<=", ">", "<"):
        if fv_num is None or rv_num is None:
            return False
        if rule.op == ">=":
            return fv_num >= rv_num
        if rule.op == "<=":
            return fv_num <= rv_num
        if rule.op == ">":
            return fv_num > rv_num
        if rule.op == "<":
            return fv_num < rv_num
    return False

@router.post("/rank")
def rank(req: RankRequest, db: Session = Depends(get_session)):
    # Load candidate sites
    q = db.query(models.Site)
    if req.site_ids:
        q = q.filter(models.Site.id.in_(req.site_ids))
    sites = q.all()

    # Build a map of site_id -> {key: value}
    truths: Dict[int, Dict[str, str]] = {}
    trows = db.query(models.SiteTruthField).all()
    for t in trows:
        truths.setdefault(t.site_id, {})[t.key] = t.value

    # Score each site
    results = []
    total_weight = sum(r.weight for r in req.rules) or 1
    for s in sites:
        tmap = truths.get(s.id, {})
        score = 0
        matches = []
        misses = []
        for r in req.rules:
            val = tmap.get(r.key)
            ok = evaluate_rule(r, val)
            if ok:
                score += r.weight
                matches.append({"key": r.key, "value": val, "op": r.op, "target": r.value, "weight": r.weight})
            else:
                misses.append({"key": r.key, "value": val, "op": r.op, "target": r.value, "weight": r.weight})
        confidence = int(round(100 * (score / total_weight)))
        results.append({
            "site_id": s.id,
            "site_name": s.name,
            "score": score,
            "confidence": confidence,
            "matches": matches,
            "misses": misses,
        })

    results.sort(key=lambda x: (x["score"], x["confidence"]), reverse=True)
    return {"results": results, "total_weight": total_weight}

@router.post("/rank/pretty")
def rank_pretty(req: RankRequest, db: Session = Depends(get_session)):
    data = rank(req, db)
    lines = []
    for r in data["results"]:
        match_keys = [m["key"] for m in r["matches"]]
        miss_keys = [m["key"] for m in r["misses"]]
        lines.append(
            f"{r['site_name']} — {r['score']}/{data['total_weight']} ({r['confidence']}%) | "
            f"matches: {', '.join(match_keys) or 'none'}; "
            f"misses: {', '.join(miss_keys) or 'none'}"
        )
    return {"summary": lines, "results": data["results"], "total_weight": data["total_weight"]}
