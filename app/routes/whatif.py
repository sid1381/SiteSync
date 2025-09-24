from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from sqlalchemy.orm import Session
from app.db import get_session
from app.services.scoring import score_protocol_for_site, load_site_truth_map

router = APIRouter(prefix="/whatif", tags=["whatif"])

class WhatIfScoreRequest(BaseModel):
    protocol_id: int
    site_id: int
    overrides: Dict[str, str] = {}

@router.post("/score")
def score_with_overrides(request: WhatIfScoreRequest, db: Session = Depends(get_session)) -> Dict[str, Any]:
    """Score a protocol for a site with temporary overrides to site data."""

    # Get original site truth map
    original_truth_map = load_site_truth_map(db, request.site_id)

    # Apply overrides (merge with original truth map)
    modified_truth_map = {**original_truth_map, **request.overrides}

    # Temporarily modify the scoring function to use our overridden map
    # We'll patch the load_site_truth_map function for this one call
    import app.services.scoring as scoring_module
    original_load_function = scoring_module.load_site_truth_map

    def patched_load_site_truth_map(db_session, site_id):
        if site_id == request.site_id:
            return modified_truth_map
        return original_load_function(db_session, site_id)

    # Temporarily replace the function
    scoring_module.load_site_truth_map = patched_load_site_truth_map

    try:
        # Run scoring with overrides
        result = score_protocol_for_site(db, request.protocol_id, request.site_id)
        result["what_if"] = True
        result["overrides_applied"] = request.overrides
        return result
    finally:
        # Restore original function
        scoring_module.load_site_truth_map = original_load_function