from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app import models

def _to_number(s: str | int | float | None):
    if s is None:
        return None
    try:
        return float(s) if not isinstance(s, (int, float)) else float(s)
    except:
        try:
            return float(str(s))
        except:
            return None

def parse_value(raw: str | None):
    """Turn a stored text 'value' into python: list, number, bool, or str."""
    if raw is None:
        return None
    txt = str(raw).strip()
    # lists like ["Epic","Cerner"]
    if txt.startswith("[") and txt.endswith("]"):
        # naive CSV inside brackets
        inner = txt[1:-1].strip()
        if not inner:
            return []
        return [v.strip().strip('"').strip("'") for v in inner.split(",")]
    # booleans
    low = txt.lower()
    if low in ("true", "false"):
        return low == "true"
    # number?
    n = _to_number(txt)
    if n is not None and txt.replace(".", "", 1).isdigit() or (txt.count(".") == 1 and txt.replace(".","",1).isdigit()):
        return n
    return txt

def evaluate_rule(op: str, rule_value: Any, field_value: Optional[str]) -> bool:
    """Compare field_value (string from DB) to rule_value using operator."""
    if field_value is None:
        return False

    fv = field_value
    rv = rule_value

    # Handle "in" as membership (case-insensitive for strings)
    if op == "in":
        if not isinstance(rv, list):
            return False
        return str(fv).strip().lower() in [str(x).strip().lower() for x in rv]

    if op == "==":
        return str(fv).strip().lower() == str(rv).strip().lower()

    # Numeric compare
    fv_num = _to_number(fv)
    rv_num = _to_number(rv)
    if op in (">=", "<=", ">", "<"):
        if fv_num is None or rv_num is None:
            return False
        if op == ">=":
            return fv_num >= rv_num
        if op == "<=":
            return fv_num <= rv_num
        if op == ">":
            return fv_num > rv_num
        if op == "<":
            return fv_num < rv_num

    return False

def load_site_truth_map(db: Session, site_id: int) -> Dict[str, str]:
    """Collect SiteTruthField + some patient capability fields into a single map."""
    tmap: Dict[str, str] = {}
    # base truth fields
    for t in db.query(models.SiteTruthField).filter(models.SiteTruthField.site_id == site_id).all():
        tmap[t.key] = t.value

    # patient capability -> flatten into keys we can match on
    # e.g., indication_label, age_min_years, age_max_years, sex, annual_eligible_patients
    # For multiple rows, we keep the "best" values or comma-join labels.
    pcs = db.query(models.SitePatientCapability).filter(models.SitePatientCapability.site_id == site_id).all()
    if pcs:
        # join labels
        labels = [p.indication_label for p in pcs if p.indication_label]
        if labels:
            tmap["indications"] = ", ".join(labels)
        # minima / maxima across rows
        mins = [p.age_min_years for p in pcs if p.age_min_years is not None]
        maxs = [p.age_max_years for p in pcs if p.age_max_years is not None]
        if mins:
            tmap["patient_age_min_years"] = str(min(mins))
        if maxs:
            tmap["patient_age_max_years"] = str(max(maxs))
        sexes = set([ (p.sex or "all").lower() for p in pcs ])
        if "all" in sexes or len(sexes) > 1:
            tmap["patient_sex"] = "all"
        else:
            tmap["patient_sex"] = list(sexes)[0]
        vols = [p.annual_eligible_patients for p in pcs if p.annual_eligible_patients is not None]
        if vols:
            tmap["annual_eligible_patients"] = str(max(vols))
    return tmap

def score_protocol_for_site(db: Session, protocol_id: int, site_id: int) -> Dict[str, Any]:
    prot = db.get(models.Protocol, protocol_id)
    if not prot:
        return {"error": "protocol_not_found"}

    reqs = db.query(models.ProtocolRequirement).filter(models.ProtocolRequirement.protocol_id == protocol_id).all()
    tmap = load_site_truth_map(db, site_id)

    total_weight = sum(r.weight for r in reqs if r.type == "objective") or 1
    score = 0
    matches, misses, subjective = [], [], []

    for r in reqs:
        rv = parse_value(r.value)
        if r.type == "subjective":
            subjective.append({
                "key": r.key, "op": r.op, "target": rv, "weight": r.weight,
                "source_question": r.source_question
            })
            continue
        val = tmap.get(r.key)
        ok = evaluate_rule(r.op, rv, val)
        (matches if ok else misses).append({
            "key": r.key, "value": val, "op": r.op, "target": rv, "weight": r.weight,
            "source_question": r.source_question
        })
        if ok:
            score += r.weight

    confidence = int(round(100 * (score / total_weight)))
    return {
        "protocol_id": protocol_id,
        "site_id": site_id,
        "score": score,
        "confidence": confidence,
        "total_weight": total_weight,
        "matches": matches,
        "misses": misses,
        "subjective": subjective
    }

def build_autofill_draft(db: Session, protocol_id: int, site_id: int) -> Dict[str, Any]:
    """Propose answers for objective items; flag subjective and missing."""
    res = score_protocol_for_site(db, protocol_id, site_id)
    if "error" in res:
        return res

    tmap = load_site_truth_map(db, site_id)

    objective_answers = []
    unresolved_missing = []

    # For every objective requirement, if we have a site value, propose it
    prot_reqs = db.query(models.ProtocolRequirement).filter(models.ProtocolRequirement.protocol_id == protocol_id).all()
    for r in prot_reqs:
        if r.type == "subjective":
            continue
        site_val = tmap.get(r.key)
        if site_val is not None:
            objective_answers.append({
                "question": r.source_question or r.key,
                "key": r.key,
                "proposed_answer": site_val,
                "rationale": f"From site truth field '{r.key}'",
                "meets_requirement": evaluate_rule(r.op, parse_value(r.value), site_val)
            })
        else:
            unresolved_missing.append({
                "question": r.source_question or r.key,
                "key": r.key,
                "reason": "No site data found"
            })

    coverage_pct = int(round(100 * (len(objective_answers) / max(1, len([r for r in prot_reqs if r.type=='objective'])))))

    return {
        "score": {k: res[k] for k in ("score","confidence","total_weight")},
        "objective_answers": objective_answers,
        "unresolved_subjective": res["subjective"],
        "unresolved_missing_data": unresolved_missing,
        "coverage_pct": coverage_pct
    }
