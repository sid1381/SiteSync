from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any

from app.db import get_session
from app import models

router = APIRouter(prefix="/site-profile", tags=["site-profile"])

@router.get("/{site_id}")
async def get_site_profile(site_id: int, db: Session = Depends(get_session)):
    """Get comprehensive site profile with JSONB structure"""
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    return {
        "site_id": site.id,
        "name": site.name,
        "population_capabilities": site.population_capabilities or {},
        "staff_and_experience": site.staff_and_experience or {},
        "facilities_and_equipment": site.facilities_and_equipment or {},
        "operational_capabilities": site.operational_capabilities or {},
        "historical_performance": site.historical_performance or {},
        "compliance_and_training": site.compliance_and_training or {},
        "metadata": {
            "profile_completeness": site.profile_completeness,
            "last_updated": site.last_updated,
            "created_at": site.created_at
        }
    }