from typing import Any, Dict
from sqlalchemy.orm import Session
from app import models
from app.services.scoring import score_protocol_for_site, load_site_truth_map, parse_value, evaluate_rule

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