"""
Sponsor-side routes for site search and feasibility assessment.
ADL uses this to help sponsors find and evaluate clinical trial sites.
"""
import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from datetime import datetime

from app.db import get_session
from app.services.ctgov_client import CTGovClient, InferredSiteProfile
from app import models

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/sponsor", tags=["sponsor"])


# ============== Request/Response Models ==============

class SiteSearchRequest(BaseModel):
    """Request to search for clinical trial sites"""
    condition: str = Field(..., description="Therapeutic area (e.g., 'NASH', 'NAFLD')")
    country: Optional[str] = Field("United States", description="Country filter")
    state: Optional[str] = Field(None, description="State filter (e.g., 'California')")
    min_trials: int = Field(2, description="Minimum trials for inclusion")
    phase_filter: Optional[List[str]] = Field(None, description="Phase experience filter")


class SiteSearchResult(BaseModel):
    """Single site in search results"""
    id: str  # Generated from facility+city+state
    facility_name: str
    city: str
    state: str
    country: str
    total_trials: int
    completed_trials: int
    active_trials: int
    completion_rate: float
    therapeutic_experience: Dict[str, int]
    phase_experience: Dict[str, int]
    top_investigators: List[Dict]
    competing_trials: int
    has_demo_profile: bool = False  # True for UCSD
    data_source: str = "ClinicalTrials.gov"


class SiteSearchResponse(BaseModel):
    """Response from site search"""
    condition: str
    location: Optional[str]
    total_sites: int
    sites: List[SiteSearchResult]
    search_timestamp: str


class ProtocolRequirements(BaseModel):
    """Protocol requirements for assessment"""
    protocol_name: str
    therapeutic_area: str
    phase: str
    target_enrollment: Optional[int] = None
    enrollment_period_months: Optional[int] = None
    required_equipment: Optional[List[str]] = None
    key_inclusion_criteria: Optional[List[str]] = None
    key_exclusion_criteria: Optional[List[str]] = None


class AssessmentRequest(BaseModel):
    """Request to assess selected sites"""
    protocol: ProtocolRequirements
    site_ids: List[str] = Field(..., description="Site IDs to assess")
    # We'll also accept the full site data for sites from search
    sites_data: Optional[List[Dict]] = Field(None, description="Full site data from search")


class CategoryScore(BaseModel):
    """Score for a single category"""
    category: str
    weight: float
    score: int
    max_score: int = 100
    confidence: str  # HIGH, MODERATE, LOW
    verification_status: str  # VERIFIED, PARTIAL, UNVERIFIED
    details: List[str]
    data_source: str


class FeasibilityFlag(BaseModel):
    """Red/Yellow/Gray flag"""
    severity: str  # RED, YELLOW, GRAY
    title: str
    details: str
    risk_assessment: str
    recommendation: str
    data_source: str
    related_category: str


class SiteAssessment(BaseModel):
    """Full assessment for a single site"""
    site_id: str
    facility_name: str
    city: str
    state: str
    country: str

    # Overall
    overall_score: int
    confidence: str  # HIGH, MODERATE, LOW

    # Category breakdown
    category_scores: List[CategoryScore]

    # Flags
    red_flags: List[FeasibilityFlag]
    yellow_flags: List[FeasibilityFlag]
    gray_flags: List[FeasibilityFlag]  # Data gaps

    # AI recommendation
    recommendation: str
    suggested_questions: List[str]

    # Metadata
    data_sources: List[str]
    has_demo_profile: bool
    assessed_at: str


class AssessmentResponse(BaseModel):
    """Response from site assessment"""
    assessment_id: str
    protocol_name: str
    sites_assessed: int
    assessments: List[SiteAssessment]
    comparison_summary: Optional[Dict] = None
    created_at: str


# ============== Helper Functions ==============

def generate_site_id(facility: str, city: str, state: str) -> str:
    """Generate unique ID for a site"""
    import hashlib
    key = f"{facility}|{city}|{state}".lower()
    return hashlib.md5(key.encode()).hexdigest()[:12]


def is_demo_site(facility_name: str) -> bool:
    """Check if this is our UCSD demo site"""
    demo_keywords = [
        "ucsd",
        "university of california san diego",
        "uc san diego",
        "nafld research center"
    ]
    facility_lower = facility_name.lower()
    return any(kw in facility_lower for kw in demo_keywords)


async def get_demo_site_profile(db: Session) -> Optional[Dict]:
    """Get the full UCSD demo profile from database"""
    site = db.query(models.Site).filter(models.Site.id == 1).first()
    if not site:
        return None

    return {
        "facility_name": site.name,
        "city": "La Jolla",
        "state": "California",
        "country": "United States",
        "investigators": [
            {
                "name": "Dr. Rohit Loomba",
                "roles": {"PRINCIPAL_INVESTIGATOR": 47},
                "trial_count": 47,
                "primary_role": "PRINCIPAL_INVESTIGATOR"
            }
        ],
        "total_trials": 89,
        "completed_trials": 47,
        "active_trials": 12,
        "terminated_trials": 2,
        "phase_experience": {"Phase 1": 8, "Phase 2": 35, "Phase 3": 14, "Phase 4": 2},
        "therapeutic_experience": {"NASH": 15, "NAFLD": 32, "Hepatitis": 8, "Cirrhosis": 6},
        "sponsors_worked_with": ["Madrigal", "Gilead", "Novo Nordisk", "89bio", "Akero"],
        "completion_rate": 0.96,
        "competing_trials": [
            {"nct_id": "NCT04951232", "title": "NASH Phase 3 Study", "sponsor": "Competitor A"},
            {"nct_id": "NCT05123456", "title": "NAFLD Fibrosis Trial", "sponsor": "Competitor B"}
        ],
        # Rich data from site profile
        "site_profile": {
            "patient_population": site.population_capabilities or {},
            "staff": site.staff_and_experience or {},
            "equipment": site.facilities_and_equipment or {},
            "facilities": site.operational_capabilities or {}
        },
        "data_source": "SiteSync Profile + ClinicalTrials.gov",
        "data_confidence": "HIGH",
        "has_demo_profile": True
    }


# ============== Routes ==============

@router.post("/search-sites", response_model=SiteSearchResponse)
async def search_sites(
    request: SiteSearchRequest,
    db: Session = Depends(get_session)
):
    """
    Search for clinical trial sites by therapeutic area and location.
    Returns sites aggregated from ClinicalTrials.gov data.
    """
    try:
        # Build location string
        location_parts = []
        if request.state:
            location_parts.append(request.state)
        if request.country and request.country != "United States":
            location_parts.append(request.country)
        location = ", ".join(location_parts) if location_parts else None

        # Search CT.gov
        client = CTGovClient()
        sites = await client.search_sites(
            condition=request.condition,
            location=location,
            min_trials=request.min_trials,
            include_phases=request.phase_filter
        )

        # Convert to response format
        results = []
        for site in sites:
            site_id = generate_site_id(site.facility_name, site.city, site.state)
            has_demo = is_demo_site(site.facility_name)

            results.append(SiteSearchResult(
                id=site_id,
                facility_name=site.facility_name,
                city=site.city,
                state=site.state,
                country=site.country,
                total_trials=site.total_trials,
                completed_trials=site.completed_trials,
                active_trials=site.active_trials,
                completion_rate=site.completion_rate,
                therapeutic_experience=site.therapeutic_experience,
                phase_experience=site.phase_experience,
                top_investigators=site.investigators[:3],
                competing_trials=len(site.competing_trials),
                has_demo_profile=has_demo,
                data_source="ClinicalTrials.gov"
            ))

        # Check if demo site should be added/enhanced
        demo_in_results = any(r.has_demo_profile for r in results)
        if not demo_in_results and request.condition.upper() in ["NASH", "NAFLD"]:
            # Add UCSD demo site if searching for NASH/NAFLD
            demo_profile = await get_demo_site_profile(db)
            if demo_profile:
                demo_result = SiteSearchResult(
                    id=generate_site_id("UCSD NAFLD Research Center", "La Jolla", "California"),
                    facility_name="UCSD NAFLD Research Center",
                    city="La Jolla",
                    state="California",
                    country="United States",
                    total_trials=89,
                    completed_trials=47,
                    active_trials=12,
                    completion_rate=0.96,
                    therapeutic_experience={"NASH": 15, "NAFLD": 32, "Hepatitis": 8},
                    phase_experience={"Phase 1": 8, "Phase 2": 35, "Phase 3": 14},
                    top_investigators=[{
                        "name": "Dr. Rohit Loomba",
                        "trial_count": 47,
                        "primary_role": "PRINCIPAL_INVESTIGATOR"
                    }],
                    competing_trials=2,
                    has_demo_profile=True,
                    data_source="SiteSync Profile"
                )
                # Insert at top
                results.insert(0, demo_result)

        return SiteSearchResponse(
            condition=request.condition,
            location=location,
            total_sites=len(results),
            sites=results,
            search_timestamp=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Site search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/assess-sites", response_model=AssessmentResponse)
async def assess_sites(
    request: AssessmentRequest,
    db: Session = Depends(get_session)
):
    """
    Run AI-powered feasibility assessment on selected sites.
    Uses industry-standard scoring rubric.
    """
    try:
        from app.services.sponsor_feasibility_scorer import SponsorFeasibilityScorer

        scorer = SponsorFeasibilityScorer()
        assessments = []

        # Prepare protocol requirements
        protocol_dict = {
            "protocol_name": request.protocol.protocol_name,
            "therapeutic_area": request.protocol.therapeutic_area,
            "phase": request.protocol.phase,
            "target_enrollment": request.protocol.target_enrollment,
            "enrollment_period_months": request.protocol.enrollment_period_months,
            "required_equipment": request.protocol.required_equipment,
            "key_inclusion_criteria": request.protocol.key_inclusion_criteria,
            "key_exclusion_criteria": request.protocol.key_exclusion_criteria
        }

        for site_data in (request.sites_data or []):
            site_id = site_data.get("id", "unknown")
            has_demo = site_data.get("has_demo_profile", False)

            # If demo site, enrich with full profile
            if has_demo:
                full_profile = await get_demo_site_profile(db)
                if full_profile:
                    site_data = {**site_data, **full_profile}

            # Run AI assessment
            result = scorer.assess_site(site_data, protocol_dict, site_id)

            # Convert to response model
            assessment = SiteAssessment(
                site_id=result.site_id,
                facility_name=result.facility_name,
                city=result.city,
                state=result.state,
                country=result.country,
                overall_score=result.overall_score,
                confidence=result.overall_confidence,
                category_scores=[
                    CategoryScore(
                        category=cs.category,
                        weight=cs.weight,
                        score=cs.score,
                        confidence=cs.confidence,
                        verification_status=cs.verification_status,
                        details=cs.details,
                        data_source=cs.data_source
                    )
                    for cs in result.category_scores
                ],
                red_flags=[
                    FeasibilityFlag(
                        severity=f.severity,
                        title=f.title,
                        details=f.details,
                        risk_assessment=f.risk_assessment,
                        recommendation=f.recommendation,
                        data_source=f.data_source,
                        related_category=f.related_category
                    )
                    for f in result.red_flags
                ],
                yellow_flags=[
                    FeasibilityFlag(
                        severity=f.severity,
                        title=f.title,
                        details=f.details,
                        risk_assessment=f.risk_assessment,
                        recommendation=f.recommendation,
                        data_source=f.data_source,
                        related_category=f.related_category
                    )
                    for f in result.yellow_flags
                ],
                gray_flags=[
                    FeasibilityFlag(
                        severity=f.severity,
                        title=f.title,
                        details=f.details,
                        risk_assessment=f.risk_assessment,
                        recommendation=f.recommendation,
                        data_source=f.data_source,
                        related_category=f.related_category
                    )
                    for f in result.gray_flags
                ],
                recommendation=result.recommendation,
                suggested_questions=result.suggested_questions,
                data_sources=result.data_sources,
                has_demo_profile=result.has_complete_profile,
                assessed_at=result.assessed_at
            )

            assessments.append(assessment)

        # Sort by score
        assessments.sort(key=lambda x: x.overall_score, reverse=True)

        # Generate assessment ID
        import uuid
        assessment_id = str(uuid.uuid4())[:8]

        return AssessmentResponse(
            assessment_id=assessment_id,
            protocol_name=request.protocol.protocol_name,
            sites_assessed=len(assessments),
            assessments=assessments,
            comparison_summary={
                "highest_score": max((a.overall_score for a in assessments), default=0),
                "lowest_score": min((a.overall_score for a in assessments), default=0),
                "avg_score": round(sum(a.overall_score for a in assessments) / len(assessments), 1) if assessments else 0,
                "sites_with_red_flags": sum(1 for a in assessments if a.red_flags),
                "sites_with_yellow_flags": sum(1 for a in assessments if a.yellow_flags)
            },
            created_at=datetime.utcnow().isoformat()
        )

    except Exception as e:
        logger.error(f"Assessment error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assessment/{assessment_id}")
async def get_assessment(assessment_id: str):
    """Retrieve a saved assessment by ID"""
    # For now, return not found - we can add persistence later
    raise HTTPException(status_code=404, detail="Assessment not found. Assessments are not yet persisted.")
