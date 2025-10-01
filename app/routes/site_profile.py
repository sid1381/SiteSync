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

@router.get("/debug/{site_id}")
async def debug_site_profile(site_id: int, db: Session = Depends(get_session)):
    """Debug endpoint to verify profile structure access"""
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Extract comprehensive profile data
    profile_data = {
        "site_id": site.id,
        "name": site.name,
        "population_capabilities": site.population_capabilities or {},
        "staff_and_experience": site.staff_and_experience or {},
        "facilities_and_equipment": site.facilities_and_equipment or {},
        "operational_capabilities": site.operational_capabilities or {},
        "historical_performance": site.historical_performance or {},
        "compliance_and_training": site.compliance_and_training or {}
    }

    # Test critical access patterns
    checks = {
        "has_hepatology_pi": (
            profile_data.get('staff_and_experience', {})
            .get('principal_investigator', {})
            .get('specialty') == 'Hepatology'
        ),
        "pi_name": (
            profile_data.get('staff_and_experience', {})
            .get('principal_investigator', {})
            .get('name', 'Not found')
        ),
        "pi_years_experience": (
            profile_data.get('staff_and_experience', {})
            .get('principal_investigator', {})
            .get('years_experience', 0)
        ),
        "has_fibroscan": (
            profile_data.get('facilities_and_equipment', {})
            .get('imaging', {})
            .get('FibroScan', False)
        ),
        "nash_patients": (
            profile_data.get('population_capabilities', {})
            .get('patient_population', {})
            .get('available_patients_by_condition', {})
            .get('NASH (Non-alcoholic Steatohepatitis)', 0)
        ),
        "coordinator_count": (
            profile_data.get('staff_and_experience', {})
            .get('study_coordinators', {})
            .get('count', 0)
        ),
        "has_pk_processing": (
            'PK processing' in profile_data.get('facilities_and_equipment', {})
            .get('laboratory', {})
            .get('capabilities', [])
        ),
        "has_minus80_freezer": (
            profile_data.get('facilities_and_equipment', {})
            .get('pharmacy', {})
            .get('investigational_drug_storage', {})
            .get('freezer_minus80C', False)
        ),
        "annual_patient_volume": (
            profile_data.get('population_capabilities', {})
            .get('annual_patient_volume', 0)
        ),
        "therapeutic_areas": (
            profile_data.get('population_capabilities', {})
            .get('therapeutic_areas', [])
        )
    }

    return {
        "profile_exists": True,
        "profile_completeness": site.profile_completeness,
        "critical_checks": checks,
        "raw_profile": profile_data
    }