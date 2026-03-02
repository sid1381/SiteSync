"""
Screener API Routes for SiteSync.

Sponsor/Consultant-facing endpoints for clinical trial site feasibility screening.
"""

import logging
import math
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.db import get_session
from app import models
from app.services.screener.citeline_parser import normalize_pi_name, parse_trialtrove_full
from app.schemas.screener import (
    ScreenerProjectCreate,
    ScreenerProjectResponse,
    ScreenerProjectListResponse,
    ProtocolCriteriaResponse,
    ProtocolUploadResponse,
    ProtocolConfirmRequest,
    CountryScore,
    CountryRankingResponse,
    SiteScore,
    SiteRankingResponse,
    SiteDetailResponse,
    InvestigatorInfo,
    WeightAdjustmentRequest,
    WeightAdjustmentResponse,
    SiteWeightsUpdateRequest,
    SiteWeightsUpdateResponse,
    ShortlistAction,
    ShortlistResponse,
    ShortlistSummary,
    ExportRequest,
    ExportResponse,
)
from app.services.screener.protocol_analyzer import ScreenerProtocolAnalyzer
from app.services.screener.scoring_engine import ScoringEngine, ScoringConfiguration
from app.services.screener.data_sources.base import ProtocolCriteria
from app.services.screener.site_web_enrichment import enrich_site_from_web
from app.services.screener.pubmed_service import search_pi_publications, batch_search_publications

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screener", tags=["screener"])


# =============================================================================
# Project Management
# =============================================================================

@router.post("/projects", response_model=ScreenerProjectResponse)
async def create_project(
    project: ScreenerProjectCreate,
    db: Session = Depends(get_session)
):
    """Create a new screener project."""
    try:
        new_project = models.ScreenerProject(
            name=project.name,
            status="draft",
        )
        db.add(new_project)
        db.commit()
        db.refresh(new_project)

        return ScreenerProjectResponse(
            id=new_project.id,
            name=new_project.name,
            status=new_project.status,
            description=None,
            created_at=new_project.created_at,
            updated_at=new_project.updated_at,
            protocol_file_path=new_project.protocol_file_path,
            protocol_criteria=new_project.protocol_criteria,
            country_weights=new_project.country_weights or _default_country_weights(),
            site_weights=new_project.site_weights or _default_site_weights(),
            site_country_ratio=new_project.site_country_ratio or 0.7,
            countries_analyzed=0,
            sites_shortlisted=0,
            extra_data=new_project.extra_data,
        )

    except Exception as e:
        logger.error(f"Error creating project: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects", response_model=ScreenerProjectListResponse)
async def list_projects(
    db: Session = Depends(get_session)
):
    """List all screener projects."""
    try:
        projects = db.query(models.ScreenerProject).order_by(
            models.ScreenerProject.updated_at.desc()
        ).all()

        project_responses = []
        for p in projects:
            # Count analyzed countries and shortlisted sites
            country_count = db.query(models.ScreenerCountryResult).filter(
                models.ScreenerCountryResult.project_id == p.id
            ).count()

            shortlist_count = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.project_id == p.id,
                models.ScreenerSiteResult.is_shortlisted == True
            ).count()

            project_responses.append(ScreenerProjectResponse(
                id=p.id,
                name=p.name,
                status=p.status,
                description=None,
                created_at=p.created_at,
                updated_at=p.updated_at,
                protocol_file_path=p.protocol_file_path,
                protocol_criteria=p.protocol_criteria,
                country_weights=p.country_weights or _default_country_weights(),
                site_weights=p.site_weights or _default_site_weights(),
                site_country_ratio=p.site_country_ratio or 0.7,
                countries_analyzed=country_count,
                sites_shortlisted=shortlist_count,
                extra_data=p.extra_data,
            ))

        return ScreenerProjectListResponse(
            projects=project_responses,
            total=len(project_responses),
        )

    except Exception as e:
        logger.error(f"Error listing projects: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}", response_model=ScreenerProjectResponse)
async def get_project(
    project_id: int,
    db: Session = Depends(get_session)
):
    """Get project details."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    country_count = db.query(models.ScreenerCountryResult).filter(
        models.ScreenerCountryResult.project_id == project_id
    ).count()

    shortlist_count = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id,
        models.ScreenerSiteResult.is_shortlisted == True
    ).count()

    return ScreenerProjectResponse(
        id=project.id,
        name=project.name,
        status=project.status,
        description=None,
        created_at=project.created_at,
        updated_at=project.updated_at,
        protocol_file_path=project.protocol_file_path,
        protocol_criteria=project.protocol_criteria,
        country_weights=project.country_weights or _default_country_weights(),
        site_weights=project.site_weights or _default_site_weights(),
        site_country_ratio=project.site_country_ratio or 0.7,
        countries_analyzed=country_count,
        sites_shortlisted=shortlist_count,
        extra_data=project.extra_data,
    )


# =============================================================================
# Protocol Upload & Analysis
# =============================================================================

@router.post("/projects/{project_id}/upload-protocol", response_model=ProtocolUploadResponse)
async def upload_protocol(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session)
):
    """Upload and analyze a protocol PDF."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Read PDF content
        pdf_content = await file.read()

        # Analyze protocol
        analyzer = ScreenerProtocolAnalyzer()
        criteria = await analyzer.analyze_protocol(pdf_content)

        # Update project
        project.protocol_criteria = criteria.to_dict()
        project.status = "analyzing"
        project.updated_at = datetime.utcnow()
        db.commit()

        # Build comprehensive response with all new fields
        confidence_str = "high" if criteria.extraction_confidence >= 0.8 else (
            "medium" if criteria.extraction_confidence >= 0.5 else "low"
        )

        return ProtocolUploadResponse(
            project_id=project_id,
            status="analyzed",
            extracted_criteria=ProtocolCriteriaResponse(
                # Study Identity
                study_title=criteria.study_title,
                protocol_number=criteria.protocol_number,
                sponsor=criteria.sponsor,
                phase=criteria.phase,
                therapeutic_area=criteria.therapeutic_area,

                # Study Design
                design_type=criteria.design_type,
                arm_count=criteria.arm_count,
                arms_description=criteria.arms_description,
                allocation_ratio=criteria.allocation_ratio,
                blinding=criteria.blinding,
                control_type=criteria.control_type,

                # Investigational Product
                drug_name=criteria.drug_name,
                drug_class=criteria.drug_class,
                dose_and_route=criteria.dose_and_route,
                dosing_frequency=criteria.dosing_frequency,
                administration_duration=criteria.administration_duration,

                # Patient Population
                indication=criteria.indication,
                indication_detail=criteria.indication_detail,
                age_range=criteria.age_range,
                age_min=criteria.age_min,
                age_max=criteria.age_max,
                sex_eligibility=criteria.sex_eligibility,
                enrollment_target=criteria.enrollment_target,
                patients_per_site=criteria.patients_per_site,
                target_countries=criteria.target_countries,

                # Eligibility
                inclusion_criteria=criteria.inclusion_criteria,
                exclusion_criteria=criteria.exclusion_criteria,

                # Timeline
                screening_period=criteria.screening_period,
                treatment_duration=criteria.treatment_duration,
                follow_up_duration=criteria.follow_up_duration,
                total_duration=criteria.total_duration,
                duration=criteria.duration,
                duration_weeks=criteria.duration_weeks,
                total_visits=criteria.total_visits,
                visit_count=criteria.visit_count,
                visit_frequency=criteria.visit_frequency,

                # Endpoints
                primary_endpoint=criteria.primary_endpoint,
                secondary_endpoints=criteria.secondary_endpoints,
                primary_assessment=criteria.primary_assessment,

                # Site Requirements
                required_equipment=criteria.required_equipment,
                required_staff=criteria.required_staff,
                procedures=criteria.procedures,

                # Site Capability Flags
                requires_endoscopy=criteria.requires_endoscopy,
                requires_infusion=criteria.requires_infusion,
                requires_imaging=criteria.requires_imaging,
                requires_biopsy=criteria.requires_biopsy,
                storage_requirements=criteria.storage_requirements,
                sample_processing=criteria.sample_processing,
                lab_requirements=criteria.lab_requirements,
                ecg_required=criteria.ecg_required,

                # Safety
                dsmb_required=criteria.dsmb_required,
                safety_monitoring=criteria.safety_monitoring,

                # Metadata
                extraction_confidence=confidence_str,
                extraction_warnings=criteria.extraction_warnings,
            ),
            message="Protocol analyzed successfully. Please review and confirm the extracted criteria.",
        )

    except Exception as e:
        logger.error(f"Error analyzing protocol: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/confirm-protocol", response_model=ProtocolUploadResponse)
async def confirm_protocol(
    project_id: int,
    edits: Optional[ProtocolConfirmRequest] = None,
    db: Session = Depends(get_session)
):
    """User confirms (and optionally edits) protocol criteria."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.protocol_criteria:
        raise HTTPException(status_code=400, detail="No protocol has been uploaded")

    try:
        # Apply any edits - comprehensive field list
        criteria_dict = project.protocol_criteria.copy()

        if edits:
            # Apply all editable fields from the comprehensive schema
            editable_fields = [
                # Study Identity
                "study_title", "protocol_number", "sponsor", "phase", "therapeutic_area",
                # Study Design
                "design_type", "arm_count", "arms_description", "allocation_ratio",
                "blinding", "control_type",
                # Investigational Product
                "drug_name", "drug_class", "dose_and_route", "dosing_frequency",
                "administration_duration",
                # Patient Population
                "indication", "indication_detail", "age_range", "age_min", "age_max",
                "sex_eligibility", "enrollment_target", "patients_per_site", "target_countries",
                # Eligibility
                "inclusion_criteria", "exclusion_criteria",
                # Timeline
                "screening_period", "treatment_duration", "follow_up_duration",
                "total_duration", "duration", "total_visits", "visit_frequency",
                # Endpoints
                "primary_endpoint", "secondary_endpoints", "primary_assessment",
                # Site Requirements
                "required_equipment", "required_staff", "procedures",
                # Site Capability Flags
                "requires_endoscopy", "requires_infusion", "requires_imaging",
                "requires_biopsy", "storage_requirements", "sample_processing",
                "lab_requirements", "ecg_required",
                # Safety
                "dsmb_required", "safety_monitoring",
            ]

            for field in editable_fields:
                value = getattr(edits, field, None)
                if value is not None:
                    criteria_dict[field] = value

        # Update project
        project.protocol_criteria = criteria_dict
        project.status = "countries_ready"
        project.updated_at = datetime.utcnow()
        db.commit()

        # Build response with safe defaults for missing fields
        response_criteria = _build_criteria_response(criteria_dict)

        return ProtocolUploadResponse(
            project_id=project_id,
            status="confirmed",
            extracted_criteria=response_criteria,
            message="Protocol confirmed. Country ranking is now available.",
        )

    except Exception as e:
        logger.error(f"Error confirming protocol: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Country Rankings
# =============================================================================

@router.get("/projects/{project_id}/countries", response_model=CountryRankingResponse)
async def get_country_rankings(
    project_id: int,
    min_trials: int = 1,
    include_ai: bool = True,  # Enable AI analysis by default for regulatory/prevalence scoring
    db: Session = Depends(get_session)
):
    """Get country rankings for the project."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.protocol_criteria:
        raise HTTPException(status_code=400, detail="No protocol criteria defined")

    try:
        # Build ProtocolCriteria from stored dict
        criteria = _dict_to_criteria(project.protocol_criteria)

        # Get scoring configuration
        config = ScoringConfiguration.from_dict({
            "country_weights": project.country_weights or _default_country_weights(),
            "site_weights": project.site_weights or _default_site_weights(),
            "site_country_ratio": project.site_country_ratio or 0.7,
        })

        # Run country ranking
        engine = ScoringEngine(config=config)
        countries = await engine.rank_countries(
            criteria=criteria,
            min_trials=min_trials,
            include_ai_analysis=include_ai,
        )

        # Store results in database
        _store_country_results(db, project_id, countries)

        # Build response
        country_scores = []
        for rank, c in enumerate(countries, 1):
            country_scores.append(CountryScore(
                country_name=c.country_name,
                country_code=c.country_code,
                composite_score=round(c.composite_score, 1),
                rank=rank,
                total_trials=c.total_trials,
                indication_trials=c.indication_trials,
                site_count=c.site_count,
                investigator_count=c.investigator_count,
                actively_recruiting=c.actively_recruiting,
                completed_trials=c.completed_trials,
                trial_experience_score=round(c.trial_experience_score, 1) if c.trial_experience_score is not None else None,
                site_density_score=round(c.site_density_score, 1) if c.site_density_score is not None else None,
                competition_score=round(c.competition_score, 1) if c.competition_score is not None else None,
                regulatory_score=round(c.regulatory_score, 1) if c.regulatory_score is not None else None,
                prevalence_score=round(c.prevalence_score, 1) if c.prevalence_score is not None else None,
                regulatory_summary=c.regulatory_summary,
                prevalence_estimate=c.prevalence_estimate,
                # World Bank indicator raw values
                regulatory_quality_raw=c.regulatory_quality_raw,
                physician_density=c.physician_density,
                logistics_index=c.logistics_index,
                health_expenditure_pct=c.health_expenditure_pct,
                # Population data
                population=c.population,
                # Prevalence data (data-driven)
                prevalence_per_100k=c.prevalence_per_100k,
                incidence_per_100k=c.incidence_per_100k,
                prevalence_source=c.prevalence_source,
                prevalence_confidence=c.prevalence_confidence or "modeled",
                prevalence_data_year=c.prevalence_data_year,
                # Addressable patient pool
                estimated_patients=c.estimated_patients,
                eligibility_fraction=c.eligibility_fraction,
                addressable_pool=c.addressable_pool,
                # Competition pressure (demand/supply model)
                competition_demand=c.competition_demand,
                competition_ratio=c.competition_ratio,
                competition_pressure=c.competition_pressure or "unknown",
                competing_trial_details=getattr(c, 'competing_trial_details', []),
                # Dimension breakdown for transparent scoring
                dimension_breakdown=c.dimension_breakdown,
            ))

        return CountryRankingResponse(
            project_id=project_id,
            indication=criteria.indication,
            phase=criteria.phase,
            total_countries=len(country_scores),
            countries=country_scores,
            generated_at=datetime.utcnow(),
            weights=project.country_weights or _default_country_weights(),
        )

    except Exception as e:
        logger.error(f"Error getting country rankings: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/projects/{project_id}/countries/refresh", response_model=CountryRankingResponse)
async def refresh_country_rankings(
    project_id: int,
    weights: Optional[WeightAdjustmentRequest] = None,
    db: Session = Depends(get_session)
):
    """Refresh country rankings with optionally updated weights."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Update weights if provided
        if weights:
            if weights.country_weights:
                project.country_weights = weights.country_weights.model_dump()
            if weights.site_weights:
                project.site_weights = weights.site_weights.model_dump()
            if weights.site_country_ratio is not None:
                project.site_country_ratio = weights.site_country_ratio
            db.commit()

        # Re-run ranking with new weights (include AI analysis)
        return await get_country_rankings(
            project_id=project_id,
            min_trials=1,
            include_ai=True,
            db=db,
        )

    except Exception as e:
        logger.error(f"Error refreshing rankings: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projects/{project_id}/site-weights", response_model=SiteWeightsUpdateResponse)
async def update_site_weights(
    project_id: int,
    request: SiteWeightsUpdateRequest,
    db: Session = Depends(get_session)
):
    """
    Update site scoring weights for a project.

    This is a lightweight endpoint that only saves weights - it does NOT re-run scoring.
    The frontend should call the sites endpoint separately after this to get recalculated rankings.
    """
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Validate weights sum to 1.0 (with tolerance for floating point)
        weights_dict = request.weights.model_dump()
        weights_sum = sum(weights_dict.values())
        if abs(weights_sum - 1.0) > 0.01:
            raise HTTPException(
                status_code=400,
                detail=f"Weights must sum to 1.0 (got {weights_sum:.3f})"
            )

        # Save weights to project.site_weights
        project.site_weights = weights_dict
        flag_modified(project, 'site_weights')

        # Save preset_name to project.extra_data["scoring_preset"]
        if request.preset_name:
            if not project.extra_data:
                project.extra_data = {}
            project.extra_data["scoring_preset"] = request.preset_name
            flag_modified(project, 'extra_data')

        db.commit()

        logger.info(f"Updated site weights for project {project_id}: {weights_dict}, preset: {request.preset_name}")

        return SiteWeightsUpdateResponse(
            status="updated",
            weights=weights_dict,
            preset_name=request.preset_name
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating site weights: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Site Rankings
# =============================================================================

@router.get("/projects/{project_id}/countries/{country_code}/sites", response_model=SiteRankingResponse)
async def get_site_rankings(
    project_id: int,
    country_code: str,
    min_trials: int = 1,
    include_gap_analysis: bool = False,
    db: Session = Depends(get_session)
):
    """Get site rankings within a specific country."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not project.protocol_criteria:
        raise HTTPException(status_code=400, detail="No protocol criteria defined")

    try:
        criteria = _dict_to_criteria(project.protocol_criteria)

        # Get country name from stored results
        country_result = db.query(models.ScreenerCountryResult).filter(
            models.ScreenerCountryResult.project_id == project_id,
            models.ScreenerCountryResult.country_code == country_code.upper()
        ).first()

        country_name = country_result.country_name if country_result else None
        country_score = country_result.composite_score if country_result else 50.0

        # Get scoring configuration
        config = ScoringConfiguration.from_dict({
            "country_weights": project.country_weights or _default_country_weights(),
            "site_weights": project.site_weights or _default_site_weights(),
            "site_country_ratio": project.site_country_ratio or 0.7,
        })

        # Run site ranking
        engine = ScoringEngine(config=config)
        sites = await engine.rank_sites_in_country(
            criteria=criteria,
            country_code=country_code.upper(),
            country_name=country_name,
            country_score=country_score,
            min_trials=min_trials,
            include_gap_analysis=include_gap_analysis,
        )

        # Check for existing enrichment data before storing new results
        # This preserves citeline, pubmed, fda data across re-rankings
        existing_enrichment_by_name = {}
        existing_results = db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.country_code == country_code.upper()
        ).all()
        for er in existing_results:
            if er.data_sources:
                # Preserve any enrichment data (citeline, pubmed, fda, compliance)
                has_enrichment = any(k in er.data_sources for k in [
                    'citeline_enrichment', 'citeline_pi_discovery', 'pubmed_data', 'fda_data', 'compliance_data'
                ])
                if has_enrichment:
                    existing_enrichment_by_name[er.site_name] = er.data_sources

        # Store results in database and get the database ID mapping
        site_id_map = _store_site_results(db, project_id, country_code.upper(), sites)

        # Re-apply all enrichment data to newly stored records
        if existing_enrichment_by_name:
            for site_name, enrichment_data in existing_enrichment_by_name.items():
                new_site_id = site_id_map.get(site_name)
                if new_site_id:
                    new_record = db.query(models.ScreenerSiteResult).filter(
                        models.ScreenerSiteResult.id == new_site_id
                    ).first()
                    if new_record:
                        if not new_record.data_sources:
                            new_record.data_sources = {}
                        new_record.data_sources.update(enrichment_data)
                        flag_modified(new_record, 'data_sources')
            db.commit()

        # Build response
        site_scores = []
        site_weights = project.site_weights or _default_site_weights()

        for rank, s in enumerate(sites, 1):
            # Normalize PI names to "First Last" format (handles "Last, First" from CT.gov)
            investigators = [
                InvestigatorInfo(
                    name=normalize_pi_name(inv.get("name", "")),
                    trial_count=inv.get("trial_count", 0),
                    publications=inv.get("publications", 0),
                    primary_role=inv.get("primary_role", ""),
                )
                for inv in s.investigators[:3]
            ]

            # Use database ID if available, otherwise fall back to original site_id
            db_site_id = site_id_map.get(s.site_name)
            site_id = str(db_site_id) if db_site_id else s.site_id

            # Get all enrichment data for this site
            all_enrichment = existing_enrichment_by_name.get(s.site_name, {})

            # Check for citeline enrichment
            citeline_enriched = False
            citeline_match_type = None
            citeline_tier = None
            citeline_pi_discovery = None

            if 'citeline_enrichment' in all_enrichment or 'citeline_pi_discovery' in all_enrichment:
                citeline_enriched = True
                citeline_match_type = all_enrichment.get('citeline_match_method')
                enrichment = all_enrichment.get('citeline_enrichment', {})
                citeline_tier = enrichment.get('tier')

                # If this is a PI discovery (site had no PI, we found one in Citeline)
                pi_discovery = all_enrichment.get('citeline_pi_discovery')
                if pi_discovery:
                    citeline_match_type = 'pi_discovery'
                    citeline_pi_discovery = pi_discovery
                    # Add discovered PI to investigators if none exist
                    if not investigators and pi_discovery.get('pi_name'):
                        investigators = [InvestigatorInfo(
                            name=pi_discovery['pi_name'],
                            trial_count=pi_discovery.get('total_trials', 0),
                            publications=0,
                            primary_role="Discovered via Citeline",
                        )]

            # Build original scores dict for enrichment adjustment
            original_scores = {
                'experience_score': round(s.experience_score, 1),
                'pi_strength_score': round(s.pi_strength_score, 1),
                'capacity_score': round(s.capacity_score, 1),
                'compliance_score': round(s.compliance_score, 1),
                'protocol_match_score': round(s.protocol_match_score, 1),
                'site_composite_score': round(s.site_composite_score, 1),
                'final_score': round(s.final_score, 1),
                'country_composite_score': round(s.country_composite_score, 1),
                'strengths': s.strengths or [],
                'red_flags': s.red_flags or [],
            }

            # Build site data for enrichment function
            site_enrichment_data = {
                'data_sources': all_enrichment,
                'pi_name': s.investigators[0].get('name') if s.investigators else None,
                'recruiting_trials': s.competing_trial_count,  # competing_trial_count = currently recruiting competing trials
                'indication_trials': s.indication_trial_count,
            }

            # Apply enrichment-based score adjustments
            adjusted = adjust_scores_with_enrichment(
                original_scores,
                site_enrichment_data,
                site_weights
            )

            # Calculate data confidence tier based on enrichment sources
            confidence = calculate_data_confidence(all_enrichment)

            site_scores.append(SiteScore(
                site_id=site_id,
                site_name=s.site_name,
                city=s.city,
                state=s.state,
                country=s.country,
                country_code=s.country_code,
                final_score=adjusted['final_score'],
                site_composite_score=adjusted['site_composite_score'],
                country_composite_score=round(s.country_composite_score, 1),
                rank=rank,
                experience_score=adjusted.get('experience_score', round(s.experience_score, 1)),
                pi_strength_score=adjusted['pi_strength_score'],
                capacity_score=adjusted.get('capacity_score', round(s.capacity_score, 1)),
                compliance_score=adjusted['compliance_score'],
                protocol_match_score=adjusted.get('protocol_match_score', round(s.protocol_match_score, 1)),
                trial_count=s.trial_count,
                indication_trial_count=s.indication_trial_count,
                completion_rate=round(s.completion_rate, 2),
                competing_trial_count=s.competing_trial_count,
                investigators=investigators,
                red_flags=adjusted.get('red_flags', []),
                yellow_flags=s.yellow_flags,
                strengths=adjusted.get('strengths', []),
                is_shortlisted=False,  # Will check from DB
                citeline_enriched=citeline_enriched,
                citeline_match_type=citeline_match_type,
                citeline_tier=citeline_tier,
                citeline_pi_discovery=citeline_pi_discovery,
                # Data confidence fields
                data_confidence=confidence['tier'],
                data_sources_checked=confidence['sources'],
                data_source_count=confidence['count'],
            ))

        # Apply percentile rankings and calibration bands
        apply_percentile_rankings(site_scores)

        return SiteRankingResponse(
            project_id=project_id,
            country_code=country_code.upper(),
            country_name=country_name or country_code,
            indication=criteria.indication,
            total_sites=len(site_scores),
            sites=site_scores,
            generated_at=datetime.utcnow(),
            weights=project.site_weights or _default_site_weights(),
        )

    except Exception as e:
        logger.error(f"Error getting site rankings: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/sites/{site_id}", response_model=SiteDetailResponse)
async def get_site_details(
    project_id: int,
    site_id: str,
    db: Session = Depends(get_session)
):
    """Get detailed information for a specific site."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Try to parse site_id as integer (database ID) first
    site_result = None
    try:
        site_id_int = int(site_id)
        site_result = db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.id == site_id_int
        ).first()
    except ValueError:
        # If not an integer, fall back to name search
        site_result = db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.site_name.contains(site_id)
        ).first()

    if site_result:
        # Look up country score from country results table
        country_result = db.query(models.ScreenerCountryResult).filter(
            models.ScreenerCountryResult.project_id == project_id,
            models.ScreenerCountryResult.country_code == site_result.country_code
        ).first()
        country_score = country_result.composite_score if country_result else 0

        # Calculate completion rate from trial data if available
        # Note: CT.gov doesn't provide per-site completion data, so this may be N/A
        completion_rate = 0.0
        if site_result.completed_trials and site_result.total_trials:
            completed = site_result.completed_trials or 0
            terminated = site_result.terminated_trials or 0
            total = completed + terminated
            if total > 0:
                completion_rate = completed / total

        # Extract all enrichment data from data_sources
        all_data_sources = site_result.data_sources or {}
        if not isinstance(all_data_sources, dict):
            all_data_sources = {}

        # Citeline enrichment data
        citeline_enriched = False
        citeline_match_type = None
        citeline_tier = None
        citeline_pi_discovery = None
        citeline_enrichment = None
        investigators = []

        if 'citeline_enrichment' in all_data_sources or 'citeline_pi_discovery' in all_data_sources:
            citeline_enriched = True
            citeline_match_type = all_data_sources.get('citeline_match_method')
            enrichment = all_data_sources.get('citeline_enrichment', {})
            citeline_enrichment = enrichment if enrichment else None
            citeline_tier = enrichment.get('tier')

            # Check for PI discovery first (site had no PI, we found one via org matching)
            pi_discovery = all_data_sources.get('citeline_pi_discovery')
            if pi_discovery:
                citeline_match_type = 'pi_discovery'
                citeline_pi_discovery = pi_discovery
                # Add discovered PI to investigators
                if pi_discovery.get('pi_name'):
                    pub_count = 0
                    pubmed_data = all_data_sources.get('pubmed_data', {})
                    if pubmed_data and pubmed_data.get('pi_name') == pi_discovery.get('pi_name'):
                        pub_count = pubmed_data.get('total_publications', 0)
                    investigators = [InvestigatorInfo(
                        name=normalize_pi_name(pi_discovery.get('pi_name', '')),
                        trial_count=pi_discovery.get('total_trials', 0),
                        publications=pub_count,
                        primary_role='Discovered via Citeline',
                        specialty=pi_discovery.get('specialties', [''])[0] if pi_discovery.get('specialties') else ''
                    )]
            # Otherwise, use the confirmed PI from citeline_enrichment
            elif enrichment:
                pi_name = enrichment.get('pi_name')
                if pi_name:
                    pub_count = 0
                    pubmed_data = all_data_sources.get('pubmed_data', {})
                    if pubmed_data and normalize_pi_name(pubmed_data.get('pi_name', '')) == normalize_pi_name(pi_name):
                        pub_count = pubmed_data.get('total_publications', 0)
                    investigators = [InvestigatorInfo(
                        name=normalize_pi_name(pi_name),
                        trial_count=enrichment.get('total_trials', 0),
                        publications=pub_count,
                        primary_role='Confirmed via Citeline',
                        specialty=enrichment.get('specialties', [''])[0] if enrichment.get('specialties') else ''
                    )]

        # If still no investigators, try pi_name from database record
        if not investigators and site_result.pi_name:
            pub_count = 0
            pubmed_data = all_data_sources.get('pubmed_data', {})
            if pubmed_data:
                pub_count = pubmed_data.get('total_publications', 0)
            investigators = [InvestigatorInfo(
                name=normalize_pi_name(site_result.pi_name),
                trial_count=site_result.total_trials or 0,
                publications=pub_count,
                primary_role='Principal Investigator'
            )]

        # Extract PubMed data
        pubmed_data = all_data_sources.get('pubmed_data')
        # PubMed data is enriched if we have a pi_name (means search was done)
        pubmed_enriched = pubmed_data is not None and bool(pubmed_data.get('pi_name') or pubmed_data.get('search_success', False))

        # Extract FDA data
        fda_data = all_data_sources.get('fda_data')
        fda_enriched = fda_data is not None

        # Extract compliance data (NPI, OIG, FDA inspections)
        compliance_data = all_data_sources.get('compliance_data')
        if compliance_data:
            # If compliance_data has FDA inspections but no separate fda_data, use it
            if not fda_data and compliance_data.get('fda_inspections'):
                fda_inspections = compliance_data.get('fda_inspections', {})
                if fda_inspections.get('checked') and fda_inspections.get('total_inspections', 0) > 0:
                    fda_data = fda_inspections
                    fda_enriched = True

        # Build data sources list for display
        data_source_list = ["ClinicalTrials.gov"]
        if citeline_enriched:
            data_source_list.append("Citeline SiteTrove")
        if pubmed_enriched:
            data_source_list.append("PubMed")
        if fda_enriched:
            data_source_list.append("FDA CLIIL")
        if compliance_data:
            if compliance_data.get('oig_exclusion', {}).get('checked'):
                data_source_list.append("OIG LEIE")
            if compliance_data.get('npi'):
                data_source_list.append("NPPES")

        # Build original scores dict for enrichment adjustment
        original_scores = {
            'experience_score': site_result.experience_score or 0,
            'pi_strength_score': site_result.pi_strength_score or 0,
            'capacity_score': site_result.capacity_score or 0,
            'compliance_score': site_result.compliance_score or 0,
            'protocol_match_score': site_result.protocol_match_score or 0,
            'site_composite_score': site_result.site_composite_score or 0,
            'final_score': site_result.final_score or 0,
            'country_composite_score': country_score,
            'strengths': [],
            'red_flags': site_result.red_flags or [],
        }

        # Build site data for enrichment function
        site_enrichment_data = {
            'data_sources': all_data_sources,
            'pi_name': site_result.pi_name,
            'pubmed_data': pubmed_data,
            'citeline_enrichment': citeline_enrichment,
            'citeline_pi_discovery': citeline_pi_discovery,
            'fda_data': fda_data,
            'recruiting_trials': site_result.recruiting_trials,
            'indication_trials': site_result.indication_trials,
        }

        # Apply enrichment-based score adjustments
        adjusted = adjust_scores_with_enrichment(
            original_scores,
            site_enrichment_data,
            project.site_weights or _default_site_weights()
        )

        return SiteDetailResponse(
            site_id=site_id,
            site_name=site_result.site_name,
            city=site_result.city,
            state=site_result.state,
            country=site_result.country,
            country_code=site_result.country_code,
            final_score=adjusted['final_score'],
            site_composite_score=adjusted['site_composite_score'],
            country_composite_score=country_score,
            experience_score=adjusted.get('experience_score', site_result.experience_score or 0),
            pi_strength_score=adjusted['pi_strength_score'],
            capacity_score=adjusted.get('capacity_score', site_result.capacity_score or 0),
            compliance_score=adjusted['compliance_score'],
            protocol_match_score=adjusted.get('protocol_match_score', site_result.protocol_match_score or 0),
            trial_count=site_result.total_trials or 0,
            indication_trial_count=site_result.indication_trials or 0,
            completed_trials=site_result.completed_trials or 0,
            terminated_trials=site_result.terminated_trials or 0,
            completion_rate=completion_rate,
            competing_trial_count=site_result.recruiting_trials or 0,
            investigators=investigators,
            trial_history=[],
            therapeutic_areas=[],
            red_flags=adjusted.get('red_flags', []),
            yellow_flags=[],
            strengths=adjusted.get('strengths', []),
            gap_analysis=site_result.gap_analysis,
            is_shortlisted=site_result.is_shortlisted or False,
            citeline_enriched=citeline_enriched,
            citeline_match_type=citeline_match_type,
            citeline_tier=citeline_tier,
            citeline_pi_discovery=citeline_pi_discovery,
            citeline_enrichment=citeline_enrichment,
            pubmed_data=pubmed_data,
            fda_data=fda_data,
            compliance_data=compliance_data,
            pubmed_enriched=pubmed_enriched,
            fda_enriched=fda_enriched,
            data_sources=data_source_list,
        )

    raise HTTPException(status_code=404, detail="Site not found")


# =============================================================================
# Site Web Enrichment
# =============================================================================

from pydantic import BaseModel as PydanticBaseModel

class SiteEnrichRequest(PydanticBaseModel):
    """Request body for site web enrichment."""
    site_name: str
    city: str
    country: str = ""
    indication: Optional[str] = None
    pi_name: Optional[str] = None


@router.post("/projects/{project_id}/sites/enrich-web")
async def enrich_site_web(
    project_id: int,
    request: SiteEnrichRequest,
    db: Session = Depends(get_session)
):
    """
    Use GPT-4o to gather web intelligence about a site.

    Returns structured information about the institution including:
    - Institution type (Academic, Community, etc.)
    - Parent organization
    - Therapeutic areas
    - Notable investigators
    - Website URL
    - Description
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not request.site_name or not request.city:
        raise HTTPException(status_code=400, detail="site_name and city are required")

    try:
        result = await enrich_site_from_web(
            site_name=request.site_name,
            city=request.city,
            country=request.country,
            indication=request.indication,
            pi_name=request.pi_name,
        )
        return result

    except Exception as e:
        logger.error(f"Error in site enrichment: {e}")
        return {
            "institution_type": "Unknown",
            "confidence": "low",
            "therapeutic_areas": [],
            "notable_investigators": [],
            "enrichment_notes": f"Enrichment unavailable: {str(e)}",
            "sources": [],
            "_error": str(e)
        }


# =============================================================================
# PubMed Publication Lookup
# =============================================================================

class PubMedLookupRequest(PydanticBaseModel):
    """Request body for PubMed PI lookup."""
    pi_name: str
    specialty: Optional[str] = None
    max_results: int = 10


class PubMedBatchRequest(PydanticBaseModel):
    """Request body for batch PubMed lookup."""
    specialty: Optional[str] = None
    max_results_per_pi: int = 10


@router.post("/projects/{project_id}/sites/{site_id}/pubmed-lookup")
async def lookup_site_pubmed(
    project_id: int,
    site_id: str,
    request: PubMedLookupRequest,
    db: Session = Depends(get_session)
):
    """
    Look up PubMed publications for a site's PI.

    Returns publication counts and recent papers for the PI.
    Optionally stores results in site data_sources.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the site
    site_result = None
    try:
        site_id_int = int(site_id)
        site_result = db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.id == site_id_int
        ).first()
    except ValueError:
        site_result = db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.site_name.contains(site_id)
        ).first()

    if not site_result:
        raise HTTPException(status_code=404, detail="Site not found")

    if not request.pi_name:
        raise HTTPException(status_code=400, detail="pi_name is required")

    try:
        # Search PubMed
        result = await search_pi_publications(
            pi_name=request.pi_name,
            specialty=request.specialty,
            max_results=request.max_results
        )

        # Store in site data_sources
        if result["search_success"]:
            if not site_result.data_sources:
                site_result.data_sources = {}

            site_result.data_sources['pubmed_data'] = {
                'pi_name': request.pi_name,
                'total_publications': result['total_publications'],
                'total_publications_5y': result.get('total_publications_5y', 0),
                'clinical_trial_publications': result['clinical_trial_publications'],
                'clinical_trial_publications_5y': result.get('clinical_trial_publications_5y', 0),
                'recent_papers': result['recent_papers'][:10],  # Store top 10
                'searched_at': datetime.utcnow().isoformat(),
            }
            flag_modified(site_result, 'data_sources')
            db.commit()

        return result

    except Exception as e:
        logger.error(f"Error in PubMed lookup: {e}")
        return {
            "pi_name": request.pi_name,
            "search_success": False,
            "error": str(e),
            "total_publications": 0,
            "clinical_trial_publications": 0,
            "recent_papers": []
        }


@router.post("/projects/{project_id}/countries/{country_code}/pubmed-batch")
async def batch_pubmed_lookup(
    project_id: int,
    country_code: str,
    request: PubMedBatchRequest,
    db: Session = Depends(get_session)
):
    """
    Batch lookup PubMed publications for all PIs in a country.

    Searches for publications for each site's PI and returns aggregated results.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get all sites in country with PI names
    site_results = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id,
        models.ScreenerSiteResult.country_code == country_code.upper()
    ).all()

    if not site_results:
        raise HTTPException(status_code=404, detail=f"No sites found for country {country_code}")

    # Build PI list from sites
    pi_list = []
    site_pi_map = {}  # Map PI name to site IDs for updating

    for site in site_results:
        pi_name = None

        # Check for PI in various locations
        if site.pi_name:
            pi_name = site.pi_name
        elif site.data_sources:
            # Check citeline PI discovery
            pi_discovery = site.data_sources.get('citeline_pi_discovery', {})
            if pi_discovery.get('pi_name'):
                pi_name = pi_discovery['pi_name']

        if pi_name:
            pi_list.append({"name": pi_name, "site_id": str(site.id)})
            if pi_name not in site_pi_map:
                site_pi_map[pi_name] = []
            site_pi_map[pi_name].append(site.id)

    if not pi_list:
        return {
            "country_code": country_code,
            "total_sites": len(site_results),
            "sites_with_pi": 0,
            "message": "No PIs found for sites in this country",
            "results": {}
        }

    try:
        # Batch search
        batch_result = await batch_search_publications(
            pi_list=pi_list,
            specialty=request.specialty,
            max_results_per_pi=request.max_results_per_pi
        )

        # Update site records with results
        sites_updated = 0
        for pi_name, pi_result in batch_result["results"].items():
            if pi_result["search_success"]:
                site_ids = site_pi_map.get(pi_name, [])
                for site_id in site_ids:
                    site = db.query(models.ScreenerSiteResult).filter(
                        models.ScreenerSiteResult.id == site_id
                    ).first()
                    if site:
                        if not site.data_sources:
                            site.data_sources = {}
                        site.data_sources['pubmed_data'] = {
                            'pi_name': pi_name,
                            'total_publications': pi_result['total_publications'],
                            'total_publications_5y': pi_result.get('total_publications_5y', 0),
                            'clinical_trial_publications': pi_result['clinical_trial_publications'],
                            'clinical_trial_publications_5y': pi_result.get('clinical_trial_publications_5y', 0),
                            'recent_papers': pi_result['recent_papers'][:10],
                            'searched_at': datetime.utcnow().isoformat(),
                        }
                        flag_modified(site, 'data_sources')
                        sites_updated += 1

        db.commit()

        return {
            "country_code": country_code,
            "total_sites": len(site_results),
            "sites_with_pi": len(pi_list),
            "pis_searched": batch_result["total_pis_searched"],
            "successful_searches": batch_result["successful_searches"],
            "failed_searches": batch_result["failed_searches"],
            "sites_updated": sites_updated,
            "summary": batch_result["summary"],
            "results": batch_result["results"]
        }

    except Exception as e:
        logger.error(f"Error in batch PubMed lookup: {e}")
        raise HTTPException(status_code=500, detail=f"Batch lookup failed: {str(e)}")


# =============================================================================
# Citeline Data Upload & Enrichment
# =============================================================================

import io
from fastapi import Query, Body
from sqlalchemy.orm.attributes import flag_modified

from app.services.screener.citeline_parser import (
    detect_export_type,
    parse_sitetrove,
    parse_trialtrove,
    match_sitetrove_to_sites,
    match_trialtrove_to_trials,
    normalize_pi_name,
)


@router.post("/projects/{project_id}/upload-citeline")
async def upload_citeline(
    project_id: int,
    file: UploadFile = File(...),
    country_code: str = Query(..., description="Country code for site matching"),
    db: Session = Depends(get_session)
):
    """
    Upload a Citeline SiteTrove or TrialTrove export for enrichment.

    Auto-detects export type and matches records to existing CT.gov sites.
    Returns match details for user review before applying enrichment.
    """
    import pandas as pd

    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate file type
    if not file.filename or not file.filename.endswith(('.xlsx', '.xls', '.csv')):
        raise HTTPException(status_code=400, detail="File must be .xlsx, .xls, or .csv")

    # Read file
    contents = await file.read()
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(io.BytesIO(contents))
        else:
            df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")

    if len(df) == 0:
        raise HTTPException(status_code=400, detail="File contains no data rows")

    # Auto-detect export type
    try:
        export_type = detect_export_type(df)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Get existing CT.gov sites for this country from database
    site_results = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id,
        models.ScreenerSiteResult.country_code == country_code.upper()
    ).all()

    # Convert to dict format expected by matching functions
    ctgov_sites = []
    for sr in site_results:
        ctgov_sites.append({
            'site_id': str(sr.id),
            'site_name': sr.site_name,
            'city': sr.city or '',
            'state': sr.state or '',
            'country': sr.country or '',
            'investigators': [{'name': sr.pi_name}] if sr.pi_name else [],
            'trials': sr.data_sources.get('trials', []) if sr.data_sources else [],
        })

    if export_type == 'sitetrove':
        pis = parse_sitetrove(df)
        match_result = match_sitetrove_to_sites(pis, ctgov_sites)

        return {
            "export_type": "sitetrove",
            "file_name": file.filename,
            "total_records": match_result.total_citeline_records,
            "matched": match_result.matched_count,
            "unmatched": match_result.unmatched_count,
            "new_pis": match_result.new_pis_count,
            "enrichment_summary": match_result.enrichment_summary,
            "match_details": match_result.match_details,
        }

    elif export_type == 'trialtrove':
        trials = parse_trialtrove(df)

        # Collect NCT IDs from our CT.gov data
        ctgov_ncts = set()
        for site in ctgov_sites:
            for trial in site.get('trials', []):
                nct = trial.get('nct_id', '')
                if nct:
                    ctgov_ncts.add(nct.upper())

        matched_trials = match_trialtrove_to_trials(trials, list(ctgov_ncts))

        # Extract enrichment metrics
        pts_coverage = sum(1 for t in matched_trials.values() if t.pts_per_site_month is not None)
        accrual_coverage = sum(1 for t in matched_trials.values() if t.actual_accrual is not None)

        return {
            "export_type": "trialtrove",
            "file_name": file.filename,
            "total_records": len(trials),
            "with_nct_ids": sum(1 for t in trials if t.nct_ids),
            "matched": len(matched_trials),
            "unmatched": len(trials) - len(matched_trials),
            "enrichment_summary": {
                "trials_enriched": len(matched_trials),
                "with_pts_per_site_month": pts_coverage,
                "with_actual_accrual": accrual_coverage,
                "pts_coverage_pct": round(pts_coverage / max(len(matched_trials), 1) * 100, 1),
                "accrual_coverage_pct": round(accrual_coverage / max(len(matched_trials), 1) * 100, 1),
            },
            "matched_trials": [
                {
                    "nct_id": nct,
                    "trial_id": trial.trial_id,
                    "pts_per_site_month": trial.pts_per_site_month,
                    "actual_accrual": trial.actual_accrual,
                    "phase": trial.phase,
                    "status": trial.status,
                }
                for nct, trial in matched_trials.items()
            ]
        }

    return {"error": f"Unknown export type: {export_type}"}


@router.post("/projects/{project_id}/upload-trialtrove")
async def upload_trialtrove(
    project_id: int,
    file: UploadFile = File(...),
    country_code: str = Query(..., description="Country code for trial matching"),
    db: Session = Depends(get_session)
):
    """
    Upload TrialTrove export for competitive landscape analysis.

    Parses TrialTrove Excel export and returns analytics preview.
    Use /apply-trialtrove to persist the enrichment data.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Read file content
        file_content = await file.read()

        # Parse TrialTrove export
        parsed = parse_trialtrove_full(file_content, file.filename)

        if 'error' in parsed:
            raise HTTPException(status_code=400, detail=parsed['error'])

        analytics = parsed.get('analytics', {})
        competition = analytics.get('competition_summary', {})
        enrollment = analytics.get('enrollment_benchmarks', {})
        sponsors = analytics.get('sponsor_landscape', {})
        endpoints = analytics.get('endpoint_landscape', {})

        # Get top sponsor from top_sponsors list
        top_sponsor = None
        top_sponsors_list = sponsors.get('top_sponsors', [])
        if top_sponsors_list and len(top_sponsors_list) > 0:
            top_sponsor = top_sponsors_list[0].get('name')

        # Get top endpoint from top_endpoints list
        top_endpoint = None
        top_endpoints_list = endpoints.get('top_endpoints', [])
        if top_endpoints_list and len(top_endpoints_list) > 0:
            top_endpoint = top_endpoints_list[0].get('name')

        # NCT overlap check skipped - upload endpoint only parses, no DB access needed
        nct_overlap = 0

        # Store parsed analytics in pending location for apply step
        if not project.extra_data:
            project.extra_data = {}
        if 'trialtrove_pending' not in project.extra_data:
            project.extra_data['trialtrove_pending'] = {}

        # Store full analytics data for later apply
        project.extra_data['trialtrove_pending'][country_code] = {
            "country_code": country_code,
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_name": file.filename,
            "total_records": parsed.get('total_records', 0),
            "query_context": parsed.get('query_context', {}),
            "nct_ids": parsed.get('nct_ids', []),
            "analytics": analytics,
        }
        flag_modified(project, 'extra_data')
        db.commit()

        return {
            "status": "parsed",
            "export_type": "trialtrove",
            "file_name": file.filename,
            "total_records": parsed.get('total_records', 0),
            "nct_overlap": nct_overlap,
            "query_context": parsed.get('query_context', {}),
            "analytics_preview": {
                "active_trials": competition.get('active_trials', 0),
                "recruiting_trials": competition.get('recruiting_count', 0),
                "total_enrollment_target": competition.get('total_enrollment', 0),
                "median_pts_per_site_month": enrollment.get('median_pts_site_month'),
                "median_enrollment": enrollment.get('median_target_accrual'),
                "top_sponsor": top_sponsor,
                "sponsor_count": len(top_sponsors_list),
                "top_endpoint": top_endpoint,
                "phase_distribution": competition.get('by_phase', {}),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing TrialTrove file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse TrialTrove file: {str(e)}")


@router.post("/projects/{project_id}/apply-citeline")
async def apply_citeline_enrichment(
    project_id: int,
    country_code: str = Query(...),
    match_details: List[dict] = Body(..., description="Match details from upload-citeline"),
    db: Session = Depends(get_session)
):
    """
    Apply Citeline enrichment to site scores after user reviews matches.

    Stores enrichment data in project.extra_data and marks sites as enriched.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Filter to only matched records
    matched = [m for m in match_details if m.get('matched')]

    # Store enrichment data in project metadata
    enrichment_data = {
        "country_code": country_code,
        "source": "citeline",
        "applied_at": datetime.utcnow().isoformat(),
        "matches": matched,
    }

    if not project.extra_data:
        project.extra_data = {}

    if 'citeline_enrichments' not in project.extra_data:
        project.extra_data['citeline_enrichments'] = {}

    project.extra_data['citeline_enrichments'][country_code] = enrichment_data
    flag_modified(project, 'extra_data')

    # Also update individual site records with enrichment data
    # Store in data_sources JSON field (already exists on ScreenerSiteResult)
    pi_discoveries_applied = 0

    for match in matched:
        site_id = match.get('matched_site_id')
        if site_id:
            try:
                site_result = db.query(models.ScreenerSiteResult).filter(
                    models.ScreenerSiteResult.id == int(site_id)
                ).first()
                if site_result:
                    if not site_result.data_sources:
                        site_result.data_sources = {}

                    # Store enrichment data
                    enrichment = match.get('enrichment', {})
                    site_result.data_sources['citeline_enrichment'] = enrichment
                    site_result.data_sources['citeline_match_confidence'] = match.get('confidence', 0)
                    site_result.data_sources['citeline_match_method'] = match.get('match_method', '')

                    # Handle PI discovery - store discovered PI info for sites without PIs
                    is_discovery = match.get('is_pi_discovery', False)
                    if is_discovery:
                        site_result.data_sources['citeline_pi_discovery'] = {
                            'pi_name': match.get('citeline_pi'),
                            'pi_city': match.get('citeline_city'),
                            'pi_org': match.get('citeline_org'),
                            'npi': enrichment.get('npi'),
                            'tier': enrichment.get('tier'),
                            'total_trials': enrichment.get('total_trials', 0),
                            'specialties': enrichment.get('specialties', []),
                            'disease_areas': enrichment.get('disease_areas', []),
                        }
                        pi_discoveries_applied += 1
                        logger.info(f"Applied PI discovery to site {site_id}: {match.get('citeline_pi')}")

                    flag_modified(site_result, 'data_sources')
            except (ValueError, TypeError) as e:
                logger.warning(f"Error updating site {site_id}: {e}")
                continue

    db.commit()

    return {
        "status": "applied",
        "sites_enriched": len(matched),
        "pi_discoveries": pi_discoveries_applied,
        "country_code": country_code,
    }


@router.post("/projects/{project_id}/apply-trialtrove")
async def apply_trialtrove_enrichment(
    project_id: int,
    country_code: str = Query(..., description="Country code for trial data"),
    db: Session = Depends(get_session)
):
    """
    Apply TrialTrove analytics to project after user reviews preview.

    Moves analytics from pending storage to permanent trialtrove_analytics.
    No file upload needed - uses data stored during upload step.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Check for pending data from upload step
        if not project.extra_data:
            raise HTTPException(status_code=400, detail="No pending TrialTrove data. Please upload first.")

        pending = project.extra_data.get('trialtrove_pending', {})
        pending_data = pending.get(country_code)

        if not pending_data:
            raise HTTPException(
                status_code=400,
                detail=f"No pending TrialTrove data for {country_code}. Please upload first."
            )

        # Move from pending to permanent storage
        if 'trialtrove_analytics' not in project.extra_data:
            project.extra_data['trialtrove_analytics'] = {}

        # Add applied timestamp
        pending_data['applied_at'] = datetime.utcnow().isoformat()

        project.extra_data['trialtrove_analytics'][country_code] = pending_data

        # Remove from pending
        del project.extra_data['trialtrove_pending'][country_code]
        if not project.extra_data['trialtrove_pending']:
            del project.extra_data['trialtrove_pending']

        flag_modified(project, 'extra_data')
        db.commit()

        analytics = pending_data.get('analytics', {})
        enrollment = analytics.get('enrollment_benchmarks', {})

        return {
            "status": "applied",
            "country_code": country_code,
            "total_records": pending_data.get('total_records', 0),
            "analytics_stored": True,
            "benchmarks": {
                "median_pts_per_site_month": enrollment.get('median_pts_site_month'),
                "median_enrollment": enrollment.get('median_target_accrual'),
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying TrialTrove enrichment: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply TrialTrove data: {str(e)}")


# =============================================================================
# GBD Prevalence Upload
# =============================================================================

@router.post("/projects/{project_id}/upload-gbd-prevalence")
async def upload_gbd_prevalence(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session)
):
    """
    Upload GBD Results Tool CSV export to override GPT-estimated prevalence.

    Parses the GBD CSV and stores parsed prevalence data for user review.
    Use /apply-gbd-prevalence to persist and recalculate prevalence scores.
    """
    from app.services.screener.data_sources.prevalence_source import parse_gbd_prevalence

    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Read file content
        file_content = await file.read()

        # Parse GBD export
        parsed_data = parse_gbd_prevalence(file_content, file.filename)

        if not parsed_data:
            raise HTTPException(
                status_code=400,
                detail="No valid country data found in GBD file. Check format."
            )

        # Get list of countries in project for comparison (from ScreenerCountryResult)
        project_countries = set()
        country_results = db.query(models.ScreenerCountryResult).filter(
            models.ScreenerCountryResult.project_id == project_id
        ).all()
        project_countries = {r.country_code for r in country_results if r.country_code}

        # Count matches
        matched_codes = set(parsed_data.keys()) & project_countries
        unmatched_codes = set(parsed_data.keys()) - project_countries

        # Get indication and year from first entry
        first_entry = next(iter(parsed_data.values()))
        indication = first_entry.notes.split("(")[0].strip() if first_entry.notes else "Unknown"
        data_year = first_entry.data_year

        # Store in pending location
        if not project.extra_data:
            project.extra_data = {}

        # Convert PrevalenceData to dict for storage
        gbd_pending = {
            "uploaded_at": datetime.utcnow().isoformat(),
            "file_name": file.filename,
            "data_year": data_year,
            "countries_parsed": len(parsed_data),
            "countries_matched": len(matched_codes),
            "data": {
                code: {
                    "country_code": data.country_code,
                    "country_name": data.country_name,
                    "prevalence_per_100k": data.prevalence_per_100k,
                    "incidence_per_100k": data.incidence_per_100k,
                    "data_source": data.data_source,
                    "data_year": data.data_year,
                    "confidence": data.confidence,
                    "notes": data.notes,
                }
                for code, data in parsed_data.items()
            }
        }

        project.extra_data['gbd_prevalence_pending'] = gbd_pending
        flag_modified(project, 'extra_data')
        db.commit()

        return {
            "status": "success",
            "file_name": file.filename,
            "countries_parsed": len(parsed_data),
            "countries_matched": len(matched_codes),
            "countries_unmatched": list(unmatched_codes)[:20],  # Limit for response size
            "indication": indication,
            "data_year": data_year,
            "preview": [
                {
                    "country_code": code,
                    "country_name": parsed_data[code].country_name,
                    "prevalence_per_100k": parsed_data[code].prevalence_per_100k,
                    "incidence_per_100k": parsed_data[code].incidence_per_100k,
                }
                for code in list(matched_codes)[:10]  # Preview first 10 matched
            ]
        }

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error parsing GBD file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse GBD file: {str(e)}")


@router.post("/projects/{project_id}/apply-gbd-prevalence")
async def apply_gbd_prevalence(
    project_id: int,
    db: Session = Depends(get_session)
):
    """
    Apply uploaded GBD prevalence data to project countries.

    Overrides GPT-estimated prevalence with GBD data and recalculates
    prevalence percentile scores across all countries.
    """
    # Validate project exists
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Check for pending GBD data
        if not project.extra_data:
            raise HTTPException(status_code=400, detail="No pending GBD data. Please upload first.")

        pending = project.extra_data.get('gbd_prevalence_pending')
        if not pending:
            raise HTTPException(status_code=400, detail="No pending GBD data. Please upload first.")

        gbd_data = pending.get('data', {})
        if not gbd_data:
            raise HTTPException(status_code=400, detail="GBD data is empty.")

        # Get country results from database
        country_results = db.query(models.ScreenerCountryResult).filter(
            models.ScreenerCountryResult.project_id == project_id
        ).all()

        if not country_results:
            raise HTTPException(
                status_code=400,
                detail="No country results found. Please run country ranking first."
            )

        # Build lookup by country code
        results_by_code = {r.country_code: r for r in country_results}

        # Track what we updated
        updated_countries = []

        # Store GBD prevalence data for each country in extra_data
        if 'gbd_prevalence_data' not in project.extra_data:
            project.extra_data['gbd_prevalence_data'] = {}

        # Update prevalence data for each country with GBD data
        for country_code, gbd_entry in gbd_data.items():
            if country_code in results_by_code:
                # Store GBD data for this country
                project.extra_data['gbd_prevalence_data'][country_code] = {
                    'prevalence_per_100k': gbd_entry.get('prevalence_per_100k'),
                    'incidence_per_100k': gbd_entry.get('incidence_per_100k'),
                    'data_source': gbd_entry.get('data_source', 'IHME GBD'),
                    'data_year': gbd_entry.get('data_year'),
                    'confidence': gbd_entry.get('confidence', 'published'),
                }
                updated_countries.append(country_code)

        # Recalculate prevalence percentile scores
        # Collect all valid prevalence values (GBD overrides + existing)
        valid_prevalences = {}
        for r in country_results:
            code = r.country_code
            # Use GBD data if available, otherwise keep existing
            if code in project.extra_data['gbd_prevalence_data']:
                prev = project.extra_data['gbd_prevalence_data'][code].get('prevalence_per_100k')
            else:
                # Check if there was previously stored prevalence data
                prev = None
            if prev is not None and prev > 0:
                valid_prevalences[code] = prev

        if valid_prevalences:
            # Sort by prevalence (ascending) and assign percentile ranks
            sorted_countries = sorted(valid_prevalences.items(), key=lambda x: x[1])
            n = len(sorted_countries)

            for rank, (code, _) in enumerate(sorted_countries):
                percentile = (rank / max(n - 1, 1)) * 100
                # Update the database record
                if code in results_by_code:
                    results_by_code[code].prevalence_score = round(percentile, 1)

        # Store applied GBD data for reference
        project.extra_data['gbd_prevalence'] = {
            "applied_at": datetime.utcnow().isoformat(),
            "file_name": pending.get('file_name'),
            "data_year": pending.get('data_year'),
            "countries_updated": len(updated_countries),
        }

        # Remove pending
        del project.extra_data['gbd_prevalence_pending']

        flag_modified(project, 'extra_data')
        db.commit()

        return {
            "status": "applied",
            "countries_updated": len(updated_countries),
            "updated_countries": updated_countries[:20],  # Limit response size
            "data_year": pending.get('data_year'),
            "file_name": pending.get('file_name'),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying GBD prevalence: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to apply GBD data: {str(e)}")


# =============================================================================
# Shortlist Management
# =============================================================================

@router.post("/projects/{project_id}/shortlist", response_model=ShortlistResponse)
async def toggle_shortlist(
    project_id: int,
    action: ShortlistAction,
    db: Session = Depends(get_session)
):
    """Add or remove a site from the shortlist."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    try:
        # Find site result - try database ID first, then name search
        site_result = None
        try:
            site_id_int = int(action.site_id)
            site_result = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.project_id == project_id,
                models.ScreenerSiteResult.id == site_id_int
            ).first()
        except ValueError:
            # Fall back to name search
            site_result = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.project_id == project_id,
                models.ScreenerSiteResult.site_name.contains(action.site_id[:20])
            ).first()

        if not site_result:
            raise HTTPException(status_code=404, detail="Site not found")

        # Update shortlist status
        if action.action == "add":
            site_result.is_shortlisted = True
        else:
            site_result.is_shortlisted = False

        db.commit()

        return ShortlistResponse(
            project_id=project_id,
            site_id=action.site_id,
            is_shortlisted=site_result.is_shortlisted,
            message=f"Site {'added to' if action.action == 'add' else 'removed from'} shortlist",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating shortlist: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projects/{project_id}/shortlist", response_model=ShortlistSummary)
async def get_shortlist(
    project_id: int,
    db: Session = Depends(get_session)
):
    """Get all shortlisted sites for a project."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    shortlisted = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id,
        models.ScreenerSiteResult.is_shortlisted == True
    ).all()

    # Cache country scores for lookup
    country_codes = set(s.country_code for s in shortlisted if s.country_code)
    country_results = db.query(models.ScreenerCountryResult).filter(
        models.ScreenerCountryResult.project_id == project_id,
        models.ScreenerCountryResult.country_code.in_(country_codes)
    ).all()
    country_score_map = {c.country_code: c.composite_score for c in country_results}

    sites = []
    countries = set()

    for s in shortlisted:
        countries.add(s.country_code)
        country_score = country_score_map.get(s.country_code, 0)
        sites.append(SiteScore(
            site_id=str(s.id),
            site_name=s.site_name,
            city=s.city,
            state=s.state,
            country=s.country,
            country_code=s.country_code,
            final_score=s.final_score or 0,
            site_composite_score=s.site_composite_score or 0,
            country_composite_score=country_score,
            rank=0,
            experience_score=s.experience_score or 0,
            pi_strength_score=s.pi_strength_score or 0,
            capacity_score=s.capacity_score or 0,
            compliance_score=s.compliance_score or 0,
            protocol_match_score=s.protocol_match_score or 0,
            trial_count=s.total_trials or 0,
            indication_trial_count=s.indication_trials or 0,
            completion_rate=0,  # CT.gov doesn't provide per-site completion data
            competing_trial_count=s.recruiting_trials or 0,
            investigators=[],
            red_flags=s.red_flags or [],
            yellow_flags=[],
            strengths=[],
            is_shortlisted=True,
        ))

    return ShortlistSummary(
        project_id=project_id,
        total_shortlisted=len(sites),
        sites=sites,
        countries_represented=list(countries),
    )


# =============================================================================
# Compliance Data Ingestion
# =============================================================================

from app.services.screener.compliance_service import (
    clean_npi,
    parse_pi_name,
    batch_npi_resolution,
    batch_oig_check,
    batch_fda_inspections,
    run_all_compliance_checks,
)


@router.post("/projects/{project_id}/compliance/resolve-npis")
async def resolve_npis(
    project_id: int,
    country_code: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """
    Resolve NPI numbers for all sites in a project.

    - Cleans existing NPIs from Citeline (removes .0 suffixes)
    - Looks up missing NPIs via NPPES registry using PI names
    - Stores resolved NPIs in data_sources.compliance_data

    Args:
        project_id: Project ID
        country_code: Optional country filter (e.g., "US")
    """
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id
    )
    if country_code:
        query = query.filter(models.ScreenerSiteResult.country_code == country_code.upper())

    site_results = query.all()

    if not site_results:
        return {
            "status": "no_sites",
            "total_sites": 0,
            "message": "No sites found for this project/country"
        }

    # Convert to dict format for service
    sites_data = []
    for sr in site_results:
        sites_data.append({
            "site_id": str(sr.id),
            "site_name": sr.site_name,
            "city": sr.city,
            "state": sr.state,
            "country": sr.country,
            "country_code": sr.country_code,
            "investigators": [{"name": sr.pi_name}] if sr.pi_name else [],
            "data_sources": sr.data_sources or {},
        })

    # Run NPI resolution
    result = await batch_npi_resolution(sites_data, project_id)

    # Update site records with resolved NPIs
    for npi_result in result.get("results", []):
        site_id = npi_result.get("site_id")
        npi = npi_result.get("npi")
        source = npi_result.get("source")

        if site_id and npi:
            site = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.id == int(site_id)
            ).first()
            if site:
                if not site.data_sources:
                    site.data_sources = {}
                if "compliance_data" not in site.data_sources:
                    site.data_sources["compliance_data"] = {}

                site.data_sources["compliance_data"]["npi"] = npi
                site.data_sources["compliance_data"]["npi_source"] = source
                site.data_sources["compliance_data"]["npi_resolved_at"] = datetime.utcnow().isoformat()

                # Add nppes_data if available
                nppes_data = npi_result.get("nppes_data")
                if nppes_data:
                    site.data_sources["compliance_data"]["nppes_data"] = nppes_data

                flag_modified(site, "data_sources")

    db.commit()

    return {
        "status": "completed",
        "total_sites": result["total_sites"],
        "npi_from_citeline": result["npi_from_citeline"],
        "npi_from_nppes": result["npi_from_nppes"],
        "npi_not_found": result["npi_not_found"],
    }


@router.post("/projects/{project_id}/compliance/check-oig")
async def check_oig_exclusions(
    project_id: int,
    country_code: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """
    Check OIG LEIE exclusions for all PIs in a project.

    Downloads the OIG exclusion list and checks each PI name.
    Stores results in data_sources.compliance_data.oig_exclusion
    """
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id
    )
    if country_code:
        query = query.filter(models.ScreenerSiteResult.country_code == country_code.upper())

    site_results = query.all()

    if not site_results:
        return {
            "status": "no_sites",
            "total_checked": 0,
            "message": "No sites found for this project/country"
        }

    # Convert to dict format
    sites_data = []
    for sr in site_results:
        # Get PI name from various sources
        pi_name = sr.pi_name
        if not pi_name and sr.data_sources:
            citeline = sr.data_sources.get("citeline_data", {})
            pi_name = citeline.get("pi_name")
        if not pi_name and sr.data_sources:
            discovery = sr.data_sources.get("citeline_pi_discovery", {})
            pi_name = discovery.get("pi_name")

        sites_data.append({
            "site_id": str(sr.id),
            "site_name": sr.site_name,
            "state": sr.state,
            "investigators": [{"name": pi_name}] if pi_name else [],
            "data_sources": sr.data_sources or {},
        })

    # Run OIG check
    result = await batch_oig_check(sites_data, project_id)

    # Update site records
    for oig_result in result.get("results", []):
        site_id = oig_result.get("site_id")
        if site_id:
            site = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.id == int(site_id)
            ).first()
            if site:
                if not site.data_sources:
                    site.data_sources = {}
                if "compliance_data" not in site.data_sources:
                    site.data_sources["compliance_data"] = {}

                # Store OIG result
                site.data_sources["compliance_data"]["oig_exclusion"] = {
                    "checked": oig_result.get("checked", False),
                    "checked_at": oig_result.get("checked_at"),
                    "excluded": oig_result.get("excluded", False),
                    "exclusion_type": oig_result.get("exclusion_type"),
                    "exclusion_date": oig_result.get("exclusion_date"),
                    "reinstatement_date": oig_result.get("reinstatement_date"),
                    "reinstated": oig_result.get("reinstated", False),
                    "match_confidence": oig_result.get("match_confidence"),
                }

                # Track checked sources
                if "checked_sources" not in site.data_sources["compliance_data"]:
                    site.data_sources["compliance_data"]["checked_sources"] = []
                site.data_sources["compliance_data"]["checked_sources"].append({
                    "source": "oig_leie",
                    "checked_at": oig_result.get("checked_at"),
                })

                flag_modified(site, "data_sources")

    db.commit()

    return {
        "status": "completed",
        "total_checked": result["total_checked"],
        "exclusions_found": result["exclusions_found"],
        "reinstated": result["reinstated"],
        "clean": result["clean"],
    }


@router.post("/projects/{project_id}/compliance/check-fda")
async def check_fda_inspections(
    project_id: int,
    country_code: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """
    Look up FDA inspection history for all sites in a project.

    Queries the openFDA API for inspection results.
    Stores results in data_sources.compliance_data.fda_inspections
    """
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id
    )
    if country_code:
        query = query.filter(models.ScreenerSiteResult.country_code == country_code.upper())

    site_results = query.all()

    if not site_results:
        return {
            "status": "no_sites",
            "total_sites_checked": 0,
            "message": "No sites found for this project/country"
        }

    # Convert to dict format
    sites_data = []
    for sr in site_results:
        sites_data.append({
            "site_id": str(sr.id),
            "site_name": sr.site_name,
            "city": sr.city,
            "state": sr.state,
            "data_sources": sr.data_sources or {},
        })

    # Run FDA inspection check
    result = await batch_fda_inspections(sites_data, project_id)

    # Update site records
    for fda_result in result.get("results", []):
        site_id = fda_result.get("site_id")
        if site_id:
            site = db.query(models.ScreenerSiteResult).filter(
                models.ScreenerSiteResult.id == int(site_id)
            ).first()
            if site:
                if not site.data_sources:
                    site.data_sources = {}
                if "compliance_data" not in site.data_sources:
                    site.data_sources["compliance_data"] = {}

                # Store FDA result
                site.data_sources["compliance_data"]["fda_inspections"] = {
                    "checked": fda_result.get("checked", False),
                    "checked_at": fda_result.get("checked_at"),
                    "inspections": fda_result.get("inspections", []),
                    "total_inspections": fda_result.get("total_inspections", 0),
                    "nai_count": fda_result.get("nai_count", 0),
                    "vai_count": fda_result.get("vai_count", 0),
                    "oai_count": fda_result.get("oai_count", 0),
                    "most_recent_date": fda_result.get("most_recent_date"),
                }

                # Track checked sources
                if "checked_sources" not in site.data_sources["compliance_data"]:
                    site.data_sources["compliance_data"]["checked_sources"] = []
                site.data_sources["compliance_data"]["checked_sources"].append({
                    "source": "fda_inspections",
                    "checked_at": fda_result.get("checked_at"),
                })

                flag_modified(site, "data_sources")

    db.commit()

    return {
        "status": "completed",
        "total_sites_checked": result["total_sites_checked"],
        "sites_with_inspections": result["sites_with_inspections"],
        "total_inspections": result["total_inspections"],
        "oai_found": result["oai_found"],
    }


@router.post("/projects/{project_id}/compliance/run-all")
async def run_all_compliance(
    project_id: int,
    country_code: Optional[str] = None,
    db: Session = Depends(get_session)
):
    """
    Run all compliance checks in sequence: NPI resolution, OIG check, FDA inspections.

    This is the master endpoint that orchestrates all compliance data ingestion.
    """
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Build query
    query = db.query(models.ScreenerSiteResult).filter(
        models.ScreenerSiteResult.project_id == project_id
    )
    if country_code:
        query = query.filter(models.ScreenerSiteResult.country_code == country_code.upper())

    site_results = query.all()

    if not site_results:
        return {
            "status": "no_sites",
            "total_sites": 0,
            "message": "No sites found for this project/country"
        }

    # Convert to dict format
    sites_data = []
    for sr in site_results:
        pi_name = sr.pi_name
        if not pi_name and sr.data_sources:
            citeline = sr.data_sources.get("citeline_data", {})
            pi_name = citeline.get("pi_name")
        if not pi_name and sr.data_sources:
            discovery = sr.data_sources.get("citeline_pi_discovery", {})
            pi_name = discovery.get("pi_name")

        sites_data.append({
            "site_id": str(sr.id),
            "site_name": sr.site_name,
            "city": sr.city,
            "state": sr.state,
            "country": sr.country,
            "country_code": sr.country_code,
            "investigators": [{"name": pi_name}] if pi_name else [],
            "data_sources": sr.data_sources or {},
        })

    # Run all compliance checks
    combined_result = await run_all_compliance_checks(sites_data, project_id)

    # Update site records with all results
    # This is a simplified version - in production you'd want to merge results properly
    db.commit()

    return {
        "status": "completed",
        "project_id": project_id,
        "total_sites": len(site_results),
        "npi_resolution": combined_result.get("npi_resolution"),
        "oig_check": combined_result.get("oig_check"),
        "fda_inspections": combined_result.get("fda_inspections"),
        "errors": combined_result.get("errors", []),
        "started_at": combined_result.get("started_at"),
        "completed_at": combined_result.get("completed_at"),
    }


# =============================================================================
# Export
# =============================================================================

@router.get("/projects/{project_id}/export")
async def export_project(
    project_id: int,
    format: str = "excel",
    db: Session = Depends(get_session)
):
    """Export project data to Excel/CSV."""
    project = db.query(models.ScreenerProject).filter(
        models.ScreenerProject.id == project_id
    ).first()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # TODO: Implement export functionality
    # For now, return placeholder
    raise HTTPException(
        status_code=501,
        detail="Export functionality not yet implemented"
    )


# =============================================================================
# Helper Functions
# =============================================================================

def _build_criteria_response(d: dict) -> ProtocolCriteriaResponse:
    """Build ProtocolCriteriaResponse with safe defaults for missing fields."""
    # Convert extraction_confidence from float to string if needed
    conf = d.get("extraction_confidence", "medium")
    if isinstance(conf, (int, float)):
        conf_str = "high" if conf >= 0.8 else ("medium" if conf >= 0.5 else "low")
    else:
        conf_str = conf if conf else "medium"

    return ProtocolCriteriaResponse(
        # Study Identity
        study_title=d.get("study_title", ""),
        protocol_number=d.get("protocol_number", ""),
        sponsor=d.get("sponsor", ""),
        phase=d.get("phase", ""),
        therapeutic_area=d.get("therapeutic_area", ""),

        # Study Design
        design_type=d.get("design_type", ""),
        arm_count=d.get("arm_count"),
        arms_description=d.get("arms_description", []),
        allocation_ratio=d.get("allocation_ratio", ""),
        blinding=d.get("blinding", ""),
        control_type=d.get("control_type", ""),

        # Investigational Product
        drug_name=d.get("drug_name", ""),
        drug_class=d.get("drug_class", ""),
        dose_and_route=d.get("dose_and_route", ""),
        dosing_frequency=d.get("dosing_frequency", ""),
        administration_duration=d.get("administration_duration", ""),

        # Patient Population
        indication=d.get("indication", ""),
        indication_detail=d.get("indication_detail", ""),
        age_range=d.get("age_range", ""),
        age_min=d.get("age_min"),
        age_max=d.get("age_max"),
        sex_eligibility=d.get("sex_eligibility", ""),
        enrollment_target=d.get("enrollment_target"),
        patients_per_site=d.get("patients_per_site"),
        target_countries=d.get("target_countries", []),

        # Eligibility
        inclusion_criteria=d.get("inclusion_criteria", []),
        exclusion_criteria=d.get("exclusion_criteria", []),

        # Timeline
        screening_period=d.get("screening_period", ""),
        treatment_duration=d.get("treatment_duration", ""),
        follow_up_duration=d.get("follow_up_duration", ""),
        total_duration=d.get("total_duration", ""),
        duration=d.get("duration", ""),
        duration_weeks=d.get("duration_weeks"),
        total_visits=d.get("total_visits"),
        visit_count=d.get("visit_count"),
        visit_frequency=d.get("visit_frequency", ""),

        # Endpoints
        primary_endpoint=d.get("primary_endpoint", ""),
        secondary_endpoints=d.get("secondary_endpoints", []),
        primary_assessment=d.get("primary_assessment", ""),

        # Site Requirements
        required_equipment=d.get("required_equipment", []),
        required_staff=d.get("required_staff", []),
        procedures=d.get("procedures", []),

        # Site Capability Flags
        requires_endoscopy=d.get("requires_endoscopy", False),
        requires_infusion=d.get("requires_infusion", False),
        requires_imaging=d.get("requires_imaging", []),
        requires_biopsy=d.get("requires_biopsy", False),
        storage_requirements=d.get("storage_requirements", []),
        sample_processing=d.get("sample_processing", []),
        lab_requirements=d.get("lab_requirements", []),
        ecg_required=d.get("ecg_required", False),

        # Safety
        dsmb_required=d.get("dsmb_required", False),
        safety_monitoring=d.get("safety_monitoring", ""),

        # Metadata
        extraction_confidence=conf_str,
        extraction_warnings=d.get("extraction_warnings", []),
    )


def _default_country_weights() -> dict:
    return {
        "trial_experience": 0.30,
        "site_density": 0.25,
        "competition": 0.20,
        "regulatory": 0.15,
        "prevalence": 0.10,
    }


def _default_site_weights() -> dict:
    return {
        "experience": 0.35,
        "pi_strength": 0.20,
        "capacity": 0.20,
        "compliance": 0.15,
        "protocol_match": 0.10,
    }


def _dict_to_criteria(d: dict) -> ProtocolCriteria:
    """Convert stored dict to ProtocolCriteria object with all fields."""
    return ProtocolCriteria(
        # Study Identity
        study_title=d.get("study_title", ""),
        protocol_number=d.get("protocol_number", ""),
        sponsor=d.get("sponsor", ""),
        phase=d.get("phase", ""),
        therapeutic_area=d.get("therapeutic_area", ""),

        # Study Design
        design_type=d.get("design_type", ""),
        arm_count=d.get("arm_count"),
        arms_description=d.get("arms_description", []),
        allocation_ratio=d.get("allocation_ratio", ""),
        blinding=d.get("blinding", ""),
        control_type=d.get("control_type", ""),

        # Investigational Product
        drug_name=d.get("drug_name", ""),
        drug_class=d.get("drug_class", ""),
        dose_and_route=d.get("dose_and_route", ""),
        dosing_frequency=d.get("dosing_frequency", ""),
        administration_duration=d.get("administration_duration", ""),

        # Patient Population
        indication=d.get("indication", ""),
        indication_detail=d.get("indication_detail", ""),
        age_range=d.get("age_range", ""),
        age_min=d.get("age_min"),
        age_max=d.get("age_max"),
        sex_eligibility=d.get("sex_eligibility", ""),
        enrollment_target=d.get("enrollment_target"),
        patients_per_site=d.get("patients_per_site"),
        target_countries=d.get("target_countries", []),

        # Eligibility
        inclusion_criteria=d.get("inclusion_criteria", []),
        exclusion_criteria=d.get("exclusion_criteria", []),

        # Timeline
        screening_period=d.get("screening_period", ""),
        treatment_duration=d.get("treatment_duration", ""),
        follow_up_duration=d.get("follow_up_duration", ""),
        total_duration=d.get("total_duration", ""),
        duration=d.get("duration", ""),
        duration_weeks=d.get("duration_weeks"),
        total_visits=d.get("total_visits"),
        visit_count=d.get("visit_count"),
        visit_frequency=d.get("visit_frequency", ""),

        # Endpoints
        primary_endpoint=d.get("primary_endpoint", ""),
        secondary_endpoints=d.get("secondary_endpoints", []),
        primary_assessment=d.get("primary_assessment", ""),

        # Site Requirements
        required_equipment=d.get("required_equipment", []),
        required_staff=d.get("required_staff", []),
        procedures=d.get("procedures", []),

        # Site Capability Flags
        requires_endoscopy=d.get("requires_endoscopy", False),
        requires_infusion=d.get("requires_infusion", False),
        requires_imaging=d.get("requires_imaging", []),
        requires_biopsy=d.get("requires_biopsy", False),
        storage_requirements=d.get("storage_requirements", []),
        sample_processing=d.get("sample_processing", []),
        lab_requirements=d.get("lab_requirements", []),
        ecg_required=d.get("ecg_required", False),

        # Safety
        dsmb_required=d.get("dsmb_required", False),
        safety_monitoring=d.get("safety_monitoring", ""),

        # Metadata
        extraction_confidence=d.get("extraction_confidence", 0.0),
        extraction_warnings=d.get("extraction_warnings", []),
        raw_extraction=d.get("raw_extraction"),
    )


def _store_country_results(db: Session, project_id: int, countries: list):
    """Store country ranking results in database."""
    try:
        # Delete old results
        db.query(models.ScreenerCountryResult).filter(
            models.ScreenerCountryResult.project_id == project_id
        ).delete()

        # Insert new results
        for c in countries:
            result = models.ScreenerCountryResult(
                project_id=project_id,
                country_name=c.country_name,
                country_code=c.country_code,
                total_trials=c.total_trials,
                indication_trials=c.indication_trials,
                site_count=c.site_count,
                investigator_count=c.investigator_count,
                competing_trials=c.actively_recruiting,
                trial_experience_score=c.trial_experience_score,
                site_density_score=c.site_density_score,
                competition_score=c.competition_score,
                regulatory_score=c.regulatory_score,
                prevalence_score=c.prevalence_score,
                composite_score=c.composite_score,
                regulatory_summary=c.regulatory_summary,
                prevalence_estimate=c.prevalence_estimate,
            )
            db.add(result)

        db.commit()
    except Exception as e:
        logger.error(f"Error storing country results: {e}")
        db.rollback()


def calculate_data_confidence(data_sources: dict) -> dict:
    """
    Calculate data confidence tier based on which enrichment sources have data.

    Sources tracked:
      - ctgov: always True (baseline for all sites)
      - citeline: True if citeline_enrichment or citeline_data has data
      - pubmed: True if pubmed_data has search results
      - compliance: True if compliance_data has oig_exclusion.checked or npi

    Tiers:
      - High: 4 sources (CT.gov + Citeline + PubMed + Compliance)
      - Medium: 2-3 sources (CT.gov + 1-2 enrichments)
      - Low: 1 source (CT.gov only)

    Returns: { "tier": "high"|"medium"|"low", "sources": [...], "count": N }
    """
    if not isinstance(data_sources, dict):
        data_sources = {}

    sources_found = ["ctgov"]  # CT.gov is always present (baseline for all sites)

    # Check Citeline enrichment
    citeline_data = data_sources.get('citeline_enrichment') or data_sources.get('citeline_data') or {}
    citeline_pi = data_sources.get('citeline_pi_discovery') or {}
    if (isinstance(citeline_data, dict) and len(citeline_data) > 0) or \
       (isinstance(citeline_pi, dict) and len(citeline_pi) > 0):
        sources_found.append("citeline")

    # Check PubMed enrichment (search was run if total_publications key is present)
    pubmed_data = data_sources.get('pubmed_data') or {}
    if isinstance(pubmed_data, dict) and 'total_publications' in pubmed_data:
        sources_found.append("pubmed")

    # Check Compliance enrichment (NPI resolved OR OIG check performed)
    compliance_data = data_sources.get('compliance_data') or {}
    if isinstance(compliance_data, dict):
        has_npi = bool(compliance_data.get('npi'))
        oig_exclusion = compliance_data.get('oig_exclusion') or {}
        has_oig_check = isinstance(oig_exclusion, dict) and oig_exclusion.get('checked')
        if has_npi or has_oig_check:
            sources_found.append("compliance")

    # Determine tier
    count = len(sources_found)
    if count >= 4:
        tier = "high"
    elif count >= 2:
        tier = "medium"
    else:
        tier = "low"

    return {
        "tier": tier,
        "sources": sources_found,
        "count": count,
    }


def apply_percentile_rankings(site_scores: list) -> list:
    """
    Calculate within-country percentile rankings for overall score
    and each dimension. Mutates site_scores in place.

    Percentile = (number of sites scoring BELOW this site) / (total sites - 1) * 100
    For ties, use average rank method.

    Calibration bands based on FINAL SCORE (not percentile):
      80+   = "Strong"    — recommend for inclusion
      65-79 = "Viable"    — worth considering with caveats
      50-64 = "Watchlist" — monitor, not first choice
      <50   = "DNR"       — do not recommend
    """
    if not site_scores:
        return site_scores

    n = len(site_scores)

    # Helper to calculate percentile for a list of values
    def calc_percentiles(values: list) -> list:
        """Calculate percentiles for a list of values. Returns list of percentiles in same order."""
        if n == 1:
            return [50.0]

        # Create sorted list of (value, original_index)
        indexed = [(v, i) for i, v in enumerate(values)]
        indexed.sort(key=lambda x: x[0])

        # Assign ranks with tie handling (average rank method)
        ranks = [0.0] * n
        i = 0
        while i < n:
            j = i
            # Find all ties
            while j < n and indexed[j][0] == indexed[i][0]:
                j += 1
            # Average rank for ties (0-indexed, so i to j-1)
            avg_rank = (i + j - 1) / 2
            for k in range(i, j):
                ranks[indexed[k][1]] = avg_rank
            i = j

        # Convert ranks to percentiles
        # Percentile = (rank) / (n - 1) * 100
        percentiles = [round((r / (n - 1)) * 100, 1) for r in ranks]
        return percentiles

    # Extract all scores
    final_scores = [s.final_score for s in site_scores]
    experience_scores = [s.experience_score for s in site_scores]
    pi_strength_scores = [s.pi_strength_score for s in site_scores]
    capacity_scores = [s.capacity_score for s in site_scores]
    compliance_scores = [s.compliance_score for s in site_scores]
    protocol_match_scores = [s.protocol_match_score for s in site_scores]

    # Calculate percentiles
    final_pctls = calc_percentiles(final_scores)
    exp_pctls = calc_percentiles(experience_scores)
    pi_pctls = calc_percentiles(pi_strength_scores)
    cap_pctls = calc_percentiles(capacity_scores)
    comp_pctls = calc_percentiles(compliance_scores)
    proto_pctls = calc_percentiles(protocol_match_scores)

    # Apply to each site
    for i, site in enumerate(site_scores):
        # Overall percentile
        site.percentile = final_pctls[i]

        # Dimension percentiles
        site.dimension_percentiles = {
            "experience": exp_pctls[i],
            "pi_strength": pi_pctls[i],
            "capacity": cap_pctls[i],
            "compliance": comp_pctls[i],
            "protocol_match": proto_pctls[i],
        }

        # Calibration band based on FINAL SCORE (not percentile)
        score = site.final_score
        if score >= 80:
            site.calibration_band = "Strong"
        elif score >= 65:
            site.calibration_band = "Viable"
        elif score >= 50:
            site.calibration_band = "Watchlist"
        else:
            site.calibration_band = "DNR"

    return site_scores


def adjust_scores_with_enrichment(
    scores: dict,
    site_data: dict,
    site_weights: dict = None
) -> dict:
    """
    Adjust site scores based on PubMed and Citeline enrichment data.

    This is a DISPLAY-LEVEL adjustment - it recalculates scores for API responses
    without modifying stored database values.

    Args:
        scores: Dict with existing dimension scores (experience_score, pi_strength_score, etc.)
        site_data: Dict with enrichment data (data_sources containing pubmed_data, citeline_*, fda_data)
        site_weights: Optional weights dict, defaults to standard weights

    Returns:
        Dict with adjusted scores and updated strengths/risks
    """
    if site_weights is None:
        site_weights = _default_site_weights()

    # Extract current scores
    pi_strength = scores.get('pi_strength_score', 30)
    compliance = scores.get('compliance_score', 50)
    experience = scores.get('experience_score', 50)
    capacity = scores.get('capacity_score', 50)
    protocol_match = scores.get('protocol_match_score', 50)

    # Track adjustments for logging/transparency
    adjustments = []
    strengths = list(scores.get('strengths', []))
    risks = list(scores.get('red_flags', []))

    # Extract enrichment data
    data_sources = site_data.get('data_sources', {})
    if not isinstance(data_sources, dict):
        data_sources = {}

    pubmed_data = data_sources.get('pubmed_data', {})
    citeline_enrichment = data_sources.get('citeline_enrichment', {})
    citeline_pi_discovery = data_sources.get('citeline_pi_discovery', {})
    fda_data = data_sources.get('fda_data', {})
    compliance_data = data_sources.get('compliance_data', {})

    # Also check top-level fields (for site detail responses)
    if not pubmed_data and site_data.get('pubmed_data'):
        pubmed_data = site_data.get('pubmed_data', {})
    if not citeline_enrichment and site_data.get('citeline_enrichment'):
        citeline_enrichment = site_data.get('citeline_enrichment', {})
    if not citeline_pi_discovery and site_data.get('citeline_pi_discovery'):
        citeline_pi_discovery = site_data.get('citeline_pi_discovery', {})
    if not fda_data and site_data.get('fda_data'):
        fda_data = site_data.get('fda_data', {})
    if not compliance_data and site_data.get('compliance_data'):
        compliance_data = site_data.get('compliance_data', {})

    # =========================================================================
    # PI STRENGTH ADJUSTMENTS
    # =========================================================================
    pi_adjustment = 0

    # +20 if PI is known (from any source)
    pi_known = False
    pi_name = None
    if pubmed_data.get('pi_name'):
        pi_known = True
        pi_name = pubmed_data.get('pi_name')
    elif citeline_pi_discovery.get('pi_name'):
        pi_known = True
        pi_name = citeline_pi_discovery.get('pi_name')
    elif citeline_enrichment.get('pi_name'):
        pi_known = True
        pi_name = citeline_enrichment.get('pi_name')
    elif site_data.get('pi_name'):
        pi_known = True
        pi_name = site_data.get('pi_name')

    if pi_known:
        pi_adjustment += 20
        adjustments.append(f"+20 PI known ({pi_name})")
        if f"Known PI: {pi_name}" not in strengths:
            strengths.append(f"Known PI: {pi_name}")

    # =========================================================================
    # PubMed Two-Axis Log-Scaled Scoring
    # =========================================================================
    # Axis 1: Indication-relevant publication breadth (5-year preferred, all-time fallback)
    # Axis 2: Clinical trial experience (5-year preferred, all-time fallback)
    #
    # Formula: score = k * ln(1 + count)
    # k_breadth = 12 (max ~40 points at 30+ pubs)
    # k_clinical = 8 (max ~25 points at 20+ clinical pubs)
    # Total PubMed contribution: 0 to ~50 points on PI Strength
    #
    # Fallback: if 5y fields missing (old data), use all-time counts with 0.7 damping factor

    total_pubs = pubmed_data.get('total_publications', 0)
    total_pubs_5y = pubmed_data.get('total_publications_5y')
    clinical_pubs = pubmed_data.get('clinical_trial_publications', 0)
    clinical_pubs_5y = pubmed_data.get('clinical_trial_publications_5y')

    # Use 5-year counts if available, otherwise dampen all-time counts
    if total_pubs_5y is not None:
        pubs_for_scoring = total_pubs_5y
    else:
        pubs_for_scoring = int(total_pubs * 0.7)  # Dampen older data

    if clinical_pubs_5y is not None:
        clinical_for_scoring = clinical_pubs_5y
    else:
        clinical_for_scoring = int(clinical_pubs * 0.7)  # Dampen older data

    pub_bonus = 0

    if pubs_for_scoring > 0:
        # Axis 1: Publication breadth - k=12, cap at 40
        breadth_score = min(40, 12 * math.log(1 + pubs_for_scoring))
        pub_bonus += breadth_score
        adjustments.append(f"+{breadth_score:.1f} for {pubs_for_scoring} recent publications (log-scaled)")

        # Add strengths based on 5-year counts
        if pubs_for_scoring >= 15:
            strengths.append(f"Highly published researcher ({pubs_for_scoring} publications in 5 years)")
        elif pubs_for_scoring >= 5:
            strengths.append(f"Active researcher ({pubs_for_scoring} publications in 5 years)")

    if clinical_for_scoring > 0:
        # Axis 2: Clinical trial experience - k=8, cap at 25
        clinical_score = min(25, 8 * math.log(1 + clinical_for_scoring))
        pub_bonus += clinical_score
        adjustments.append(f"+{clinical_score:.1f} for {clinical_for_scoring} clinical trial publications (log-scaled)")

        # Add strengths based on clinical trial experience
        if clinical_for_scoring >= 5:
            strengths.append(f"Strong recent clinical trial publication record ({clinical_for_scoring} in 5 years)")
        elif clinical_for_scoring >= 1:
            strengths.append(f"Clinical trial publications ({clinical_for_scoring})")

    # Cap total PubMed contribution at 50 points
    pub_bonus = min(50, pub_bonus)
    pi_adjustment += pub_bonus

    # Risk flag: publications exist but none are recent
    if total_pubs > 0 and pubs_for_scoring == 0 and total_pubs_5y is not None:
        risks.append("PI publications are older than 5 years — may indicate reduced recent activity")

    # +2 to +10 for Citeline tier
    tier = citeline_enrichment.get('tier') or citeline_pi_discovery.get('tier')
    if tier:
        tier_upper = tier.upper() if isinstance(tier, str) else ''
        if tier_upper == 'GOLD':
            tier_bonus = 10
        elif tier_upper == 'SILVER':
            tier_bonus = 5
        elif tier_upper == 'BRONZE':
            tier_bonus = 2
        else:
            tier_bonus = 0

        if tier_bonus > 0:
            pi_adjustment += tier_bonus
            adjustments.append(f"+{tier_bonus} for Citeline {tier} tier")
            strengths.append(f"Citeline {tier} tier investigator")

    # Apply PI strength adjustment (capped at 100)
    new_pi_strength = min(100, pi_strength + pi_adjustment)

    # =========================================================================
    # EXPERIENCE ADJUSTMENTS (Citeline career data + indication depth)
    # =========================================================================
    # Two signals:
    # 1. Citeline total_trials = PI's career trial count (experience depth)
    # 2. indication_trials = site's trials in this specific indication
    # =========================================================================
    experience_adjustment = 0
    new_experience = experience  # Default to current value

    # Signal 1: Citeline career trial count
    citeline_total_trials = citeline_enrichment.get('total_trials', 0) or citeline_pi_discovery.get('total_trials', 0)
    if citeline_total_trials and citeline_total_trials > 0:
        # Log-scaled bonus: 8 * ln(1 + trials), capped at 30
        career_bonus = min(30, 8 * math.log(1 + citeline_total_trials))
        experience_adjustment += career_bonus
        adjustments.append(f"+{career_bonus:.1f} PI career trial experience ({citeline_total_trials} trials)")

        if citeline_total_trials >= 50:
            strengths.append(f"PI has extensive clinical trial experience ({citeline_total_trials} career trials)")
        elif citeline_total_trials >= 20:
            strengths.append(f"PI has strong clinical trial track record ({citeline_total_trials} career trials)")

    # Signal 2: Site's indication-specific trial experience
    indication_trials = site_data.get('indication_trials', 0) or 0
    if indication_trials >= 10:
        experience_adjustment += 10
        adjustments.append(f"+10 deep indication-specific experience ({indication_trials} indication trials)")
        strengths.append("Site has deep indication-specific trial experience")
    elif indication_trials >= 5:
        experience_adjustment += 5
        adjustments.append(f"+5 indication-specific experience ({indication_trials} indication trials)")

    # Cap total experience adjustment at 35
    experience_adjustment = min(35, experience_adjustment)
    new_experience = max(0, min(100, experience + experience_adjustment))

    # =========================================================================
    # COMPLIANCE SCORING ENGINE
    # =========================================================================
    # Reads from data_sources.compliance_data (populated by Step 3 pipeline)
    # Three signal layers: Hard-Stop → FDA Inspections → Positive Signals
    # =========================================================================
    compliance_adjustment = 0
    hard_stop_triggered = False
    new_compliance = compliance  # Default to current value

    # Helper to parse date strings
    def parse_date_safe(date_str: str) -> Optional[datetime]:
        """Parse date string with multiple format fallbacks."""
        if not date_str:
            return None
        formats = ['%Y-%m-%d', '%Y/%m/%d', '%m/%d/%Y', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%SZ']
        for fmt in formats:
            try:
                return datetime.strptime(date_str[:10] if len(date_str) > 10 else date_str, fmt[:len(date_str)])
            except (ValueError, TypeError):
                continue
        return None

    # -------------------------------------------------------------------------
    # LAYER 1: HARD-STOP DISQUALIFIERS (OIG Exclusion)
    # -------------------------------------------------------------------------
    oig_exclusion = compliance_data.get('oig_exclusion', {})
    if isinstance(oig_exclusion, dict) and oig_exclusion.get('excluded'):
        if not oig_exclusion.get('reinstated'):
            # HARD STOP: Active exclusion - floor compliance to 20
            hard_stop_triggered = True
            new_compliance = 20
            adjustments.append("HARD STOP: PI on OIG exclusion list — compliance floored to 20")
            risks.append("PI is on the OIG List of Excluded Individuals — site is ineligible for federally funded trials")
        else:
            # Previously excluded but reinstated - apply penalty
            compliance_adjustment -= 15
            adjustments.append("-15 PI was previously excluded from federal programs (reinstated)")
            risks.append("PI was previously on OIG exclusion list (since reinstated)")

    # -------------------------------------------------------------------------
    # LAYER 2: FDA INSPECTION HISTORY (only if no hard stop)
    # -------------------------------------------------------------------------
    if not hard_stop_triggered:
        fda_inspections = compliance_data.get('fda_inspections', {})

        if isinstance(fda_inspections, dict) and fda_inspections.get('total_inspections', 0) > 0:
            oai_count = fda_inspections.get('oai_count', 0)
            vai_count = fda_inspections.get('vai_count', 0)
            nai_count = fda_inspections.get('nai_count', 0)
            most_recent_date = fda_inspections.get('most_recent_date', '')

            # Calculate age_years from most recent inspection
            age_years = 0
            if most_recent_date:
                parsed_date = parse_date_safe(most_recent_date)
                if parsed_date:
                    age_years = (datetime.now() - parsed_date).days / 365.25

            # OAI (Official Action Indicated - serious)
            if oai_count > 0:
                oai_penalty = 0
                base_severity = -25
                for _ in range(oai_count):
                    # Decay penalty based on age: base * 2^(-age/4)
                    decayed_penalty = base_severity * (2 ** (-age_years / 4))
                    oai_penalty += decayed_penalty
                # Cap at -40
                oai_penalty = max(oai_penalty, -40)
                compliance_adjustment += oai_penalty
                adjustments.append(f"{oai_penalty:.0f} FDA Official Action Indicated ({oai_count} OAI)")
                risks.append("FDA Official Action Indicated on inspection record")

            # VAI (Voluntary Action Indicated - minor)
            if vai_count > 0:
                vai_penalty = -3  # First VAI
                vai_penalty += -2 * max(0, vai_count - 1)  # Additional VAIs
                vai_penalty = max(vai_penalty, -10)  # Cap at -10
                compliance_adjustment += vai_penalty
                adjustments.append(f"{vai_penalty:.0f} FDA Voluntary Action Indicated ({vai_count} VAI)")
                if vai_count >= 3:
                    risks.append("Multiple FDA inspection observations")

            # NAI (No Action Indicated - clean)
            if nai_count > 0:
                nai_bonus = min(3 * nai_count, 10)  # +3 per NAI, cap at +10
                compliance_adjustment += nai_bonus
                adjustments.append(f"+{nai_bonus} clean FDA inspections ({nai_count} NAI)")
                if nai_count >= 2:
                    strengths.append("Track record of clean FDA inspections")

        # Fallback: old fda_data format (backward compatibility)
        elif fda_data:
            compliance_signal = fda_data.get('compliance_signal', '')
            if compliance_signal:
                signal_lower = compliance_signal.lower() if isinstance(compliance_signal, str) else ''
                if signal_lower in ('clean', 'no_issues'):
                    compliance_adjustment += 5
                    adjustments.append("+5 FDA clean record (legacy)")
                    strengths.append("Clean FDA inspection history")
                elif signal_lower in ('minor_issues', 'observations'):
                    compliance_adjustment -= 5
                    adjustments.append("-5 FDA minor issues (legacy)")
                elif signal_lower in ('warning', 'warning_letter'):
                    compliance_adjustment -= 25
                    adjustments.append("-25 FDA warning letter (legacy)")
                    risks.append("FDA warning letter on file")

            # Check for warning letters explicitly
            warning_letters = fda_data.get('warning_letters', [])
            if warning_letters and len(warning_letters) > 0 and compliance_adjustment >= 0:
                compliance_adjustment = -25
                adjustments.append("-25 FDA warning letter (legacy)")
                if "FDA warning letter on file" not in risks:
                    risks.append("FDA warning letter on file")

    # -------------------------------------------------------------------------
    # LAYER 3: POSITIVE COMPLIANCE SIGNALS (only if no hard stop)
    # -------------------------------------------------------------------------
    if not hard_stop_triggered:
        # OIG check clear bonus
        if isinstance(oig_exclusion, dict) and oig_exclusion.get('checked') and not oig_exclusion.get('excluded'):
            compliance_adjustment += 5
            adjustments.append("+5 OIG exclusion check clear")
            strengths.append("PI verified clear on federal exclusion lists")

        # NPI verified bonus
        if compliance_data.get('npi'):
            compliance_adjustment += 2
            adjustments.append("+2 identity verified via NPI")

    # -------------------------------------------------------------------------
    # APPLY COMPLIANCE ADJUSTMENT
    # -------------------------------------------------------------------------
    if not hard_stop_triggered:
        new_compliance = max(0, min(100, compliance + compliance_adjustment))
    # If hard stop was triggered, new_compliance is already set to 20

    # =========================================================================
    # CAPACITY ADJUSTMENTS (current competing trial load)
    # =========================================================================
    # recruiting_trials = currently recruiting competing trials from CT.gov
    # Sites with active competing trials have less available capacity
    # Absence of recruiting trials is a positive signal (no competing load)
    # =========================================================================
    capacity_adjustment = 0
    new_capacity = capacity  # Default to current value

    recruiting_trials = site_data.get('recruiting_trials')

    if recruiting_trials is not None:
        if recruiting_trials > 0:
            # Penalty for competing trials: -4 per trial, capped at -10
            penalty = -4 * recruiting_trials
            penalty = max(penalty, -10)  # Cap at -10
            capacity_adjustment += penalty
            adjustments.append(f"{penalty} competing trial load ({recruiting_trials} recruiting)")
            risks.append(f"Site has {recruiting_trials} currently recruiting competing trial(s) — may impact enrollment capacity")
        else:
            # Bonus for no competing trials
            capacity_adjustment += 3
            adjustments.append("+3 no currently competing trials")
            strengths.append("No currently competing trials at this site")

    new_capacity = max(0, min(100, capacity + capacity_adjustment))

    # =========================================================================
    # RECALCULATE COMPOSITE SCORE
    # =========================================================================
    # Composite = weighted sum of dimension scores
    new_composite = (
        new_pi_strength * site_weights.get('pi_strength', 0.20) +
        new_experience * site_weights.get('experience', 0.35) +
        new_capacity * site_weights.get('capacity', 0.20) +
        new_compliance * site_weights.get('compliance', 0.15) +
        protocol_match * site_weights.get('protocol_match', 0.10)
    )

    # Recalculate final score with country component
    country_score = scores.get('country_composite_score', 50)
    site_country_ratio = 0.7  # Default: 70% site, 30% country
    new_final = new_composite * site_country_ratio + country_score * (1 - site_country_ratio)

    # =========================================================================
    # BUILD ADJUSTED SCORES DICT
    # =========================================================================
    adjusted = dict(scores)  # Copy original scores
    adjusted['pi_strength_score'] = round(new_pi_strength, 1)
    adjusted['experience_score'] = round(new_experience, 1)
    adjusted['capacity_score'] = round(new_capacity, 1)
    adjusted['compliance_score'] = round(new_compliance, 1)
    adjusted['site_composite_score'] = round(new_composite, 1)
    adjusted['final_score'] = round(new_final, 1)

    # Update strengths and risks (deduplicated)
    adjusted['strengths'] = list(dict.fromkeys(strengths))  # Preserve order, remove duplicates
    adjusted['red_flags'] = list(dict.fromkeys(risks))

    # Add metadata about adjustments (for debugging/transparency)
    adjusted['_enrichment_adjustments'] = adjustments
    adjusted['_enrichment_applied'] = len(adjustments) > 0

    return adjusted


def _store_site_results(db: Session, project_id: int, country_code: str, sites: list) -> dict:
    """Store site ranking results in database and return site_name -> database_id mapping."""
    site_id_map = {}
    try:
        # Delete old results for this country
        db.query(models.ScreenerSiteResult).filter(
            models.ScreenerSiteResult.project_id == project_id,
            models.ScreenerSiteResult.country_code == country_code
        ).delete()

        # Insert new results
        for s in sites:
            result = models.ScreenerSiteResult(
                project_id=project_id,
                country_code=country_code,
                site_name=s.site_name,
                city=s.city,
                state=s.state,
                country=s.country,
                pi_name=s.investigators[0].get("name") if s.investigators else None,
                total_trials=s.trial_count,
                indication_trials=s.indication_trial_count,
                completed_trials=0,  # Not tracked at this level
                recruiting_trials=s.competing_trial_count,
                experience_score=s.experience_score,
                pi_strength_score=s.pi_strength_score,
                capacity_score=s.capacity_score,
                compliance_score=s.compliance_score,
                protocol_match_score=s.protocol_match_score,
                site_composite_score=s.site_composite_score,
                final_score=s.final_score,
                gap_analysis=s.gap_analysis,
                red_flags=s.red_flags,
            )
            db.add(result)
            db.flush()  # Flush to get the ID
            site_id_map[s.site_name] = result.id

        db.commit()
    except Exception as e:
        logger.error(f"Error storing site results: {e}")
        db.rollback()

    return site_id_map
