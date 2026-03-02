"""
Pydantic schemas for SiteSync Screener API.

Defines request/response models for all Screener endpoints.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Project Schemas
# =============================================================================

class ScreenerProjectCreate(BaseModel):
    """Request to create a new screener project."""
    name: str = Field(..., description="Project name")
    description: Optional[str] = Field(None, description="Project description")


class ScreenerProjectResponse(BaseModel):
    """Response for a screener project."""
    id: int
    name: str
    status: str  # draft, analyzing, countries_ready, complete
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Protocol data (if uploaded)
    protocol_file_path: Optional[str] = None
    protocol_criteria: Optional[Dict[str, Any]] = None

    # Scoring weights
    country_weights: Dict[str, float]
    site_weights: Dict[str, float]
    site_country_ratio: float

    # Summary stats
    countries_analyzed: int = 0
    sites_shortlisted: int = 0

    # Enrichment data (Citeline TrialTrove, SiteTrove, etc.)
    extra_data: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ScreenerProjectListResponse(BaseModel):
    """Response for listing projects."""
    projects: List[ScreenerProjectResponse]
    total: int


# =============================================================================
# Protocol Criteria Schemas - SPIRIT/ICH M11 Aligned
# =============================================================================

class ProtocolCriteriaResponse(BaseModel):
    """Comprehensive protocol criteria extracted from PDF - SPIRIT/ICH M11 aligned."""

    # === Study Identity ===
    study_title: str = ""
    protocol_number: str = ""
    sponsor: str = ""
    phase: str = ""
    therapeutic_area: str = ""

    # === Study Design ===
    design_type: str = ""           # e.g., "Randomized, double-blind, placebo-controlled"
    arm_count: Optional[int] = None
    arms_description: List[str] = []
    allocation_ratio: str = ""
    blinding: str = ""              # "Double-blind", "Open-label", "Single-blind"
    control_type: str = ""          # "Placebo-controlled", "Active-controlled"

    # === Investigational Product ===
    drug_name: str = ""
    drug_class: str = ""
    dose_and_route: str = ""
    dosing_frequency: str = ""
    administration_duration: str = ""

    # === Patient Population ===
    indication: str = ""
    indication_detail: str = ""
    age_range: str = ""
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    sex_eligibility: str = ""
    enrollment_target: Optional[int] = None
    patients_per_site: Optional[int] = None
    target_countries: List[str] = []

    # === Eligibility Criteria ===
    inclusion_criteria: List[str] = []
    exclusion_criteria: List[str] = []

    # === Study Timeline ===
    screening_period: str = ""
    treatment_duration: str = ""
    follow_up_duration: str = ""
    total_duration: str = ""
    duration: str = ""              # Legacy
    duration_weeks: Optional[int] = None
    total_visits: Optional[int] = None
    visit_count: Optional[int] = None
    visit_frequency: str = ""

    # === Endpoints ===
    primary_endpoint: str = ""
    secondary_endpoints: List[str] = []
    primary_assessment: str = ""

    # === Site Requirements ===
    required_equipment: List[str] = []
    required_staff: List[str] = []
    procedures: List[str] = []

    # === Site Capability Flags ===
    requires_endoscopy: bool = False
    requires_infusion: bool = False
    requires_imaging: List[str] = []
    requires_biopsy: bool = False
    storage_requirements: List[str] = []
    sample_processing: List[str] = []
    lab_requirements: List[str] = []
    ecg_required: bool = False

    # === Safety & Oversight ===
    dsmb_required: bool = False
    safety_monitoring: str = ""

    # === Extraction Metadata ===
    extraction_confidence: str = "high"
    extraction_warnings: List[str] = []


class ProtocolUploadResponse(BaseModel):
    """Response after uploading protocol PDF."""
    project_id: int
    status: str
    extracted_criteria: ProtocolCriteriaResponse
    message: str


class ProtocolConfirmRequest(BaseModel):
    """Request to confirm/edit protocol criteria - all fields editable."""

    # Study Identity
    study_title: Optional[str] = None
    protocol_number: Optional[str] = None
    sponsor: Optional[str] = None
    phase: Optional[str] = None
    therapeutic_area: Optional[str] = None

    # Study Design
    design_type: Optional[str] = None
    arm_count: Optional[int] = None
    arms_description: Optional[List[str]] = None
    allocation_ratio: Optional[str] = None
    blinding: Optional[str] = None
    control_type: Optional[str] = None

    # Investigational Product
    drug_name: Optional[str] = None
    drug_class: Optional[str] = None
    dose_and_route: Optional[str] = None
    dosing_frequency: Optional[str] = None
    administration_duration: Optional[str] = None

    # Patient Population
    indication: Optional[str] = None
    indication_detail: Optional[str] = None
    age_range: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    sex_eligibility: Optional[str] = None
    enrollment_target: Optional[int] = None
    patients_per_site: Optional[int] = None
    target_countries: Optional[List[str]] = None

    # Eligibility
    inclusion_criteria: Optional[List[str]] = None
    exclusion_criteria: Optional[List[str]] = None

    # Timeline
    screening_period: Optional[str] = None
    treatment_duration: Optional[str] = None
    follow_up_duration: Optional[str] = None
    total_duration: Optional[str] = None
    duration: Optional[str] = None
    total_visits: Optional[int] = None
    visit_frequency: Optional[str] = None

    # Endpoints
    primary_endpoint: Optional[str] = None
    secondary_endpoints: Optional[List[str]] = None
    primary_assessment: Optional[str] = None

    # Site Requirements
    required_equipment: Optional[List[str]] = None
    required_staff: Optional[List[str]] = None
    procedures: Optional[List[str]] = None

    # Site Capability Flags
    requires_endoscopy: Optional[bool] = None
    requires_infusion: Optional[bool] = None
    requires_imaging: Optional[List[str]] = None
    requires_biopsy: Optional[bool] = None
    storage_requirements: Optional[List[str]] = None
    sample_processing: Optional[List[str]] = None
    lab_requirements: Optional[List[str]] = None
    ecg_required: Optional[bool] = None

    # Safety
    dsmb_required: Optional[bool] = None
    safety_monitoring: Optional[str] = None


# =============================================================================
# Country Ranking Schemas
# =============================================================================

class CountryScore(BaseModel):
    """Individual country in ranking."""
    country_name: str
    country_code: str
    composite_score: float
    rank: int

    # Raw data
    total_trials: int
    indication_trials: int
    site_count: int
    investigator_count: int
    actively_recruiting: int  # competing trials
    completed_trials: int

    # Component scores (0-100) - may be None if data unavailable
    trial_experience_score: Optional[float] = None
    site_density_score: Optional[float] = None
    competition_score: Optional[float] = None
    regulatory_score: Optional[float] = None
    prevalence_score: Optional[float] = None

    # AI-generated summaries (optional)
    regulatory_summary: Optional[str] = None
    prevalence_estimate: Optional[str] = None

    # World Bank indicator raw values (for transparency in UI)
    regulatory_quality_raw: Optional[float] = None  # RQ.EST (-2.5 to 2.5)
    physician_density: Optional[float] = None       # Physicians per 1,000 people
    logistics_index: Optional[float] = None         # Logistics Performance Index (1-5)
    health_expenditure_pct: Optional[float] = None  # Health expenditure % of GDP

    # Population data (from World Bank)
    population: Optional[int] = None

    # Prevalence data (data-driven from GPT epidemiology lookup)
    prevalence_per_100k: Optional[float] = None     # Published prevalence rate
    incidence_per_100k: Optional[float] = None      # Annual incidence rate
    prevalence_source: Optional[str] = None         # Citation string (e.g., "Ng et al. Lancet 2017")
    prevalence_confidence: str = "modeled"          # 'published', 'regional_estimate', 'modeled'
    prevalence_data_year: Optional[int] = None

    # Addressable patient pool (calculated)
    estimated_patients: Optional[int] = None        # Total patients in country
    eligibility_fraction: float = 1.0               # Fraction after exclusion criteria
    addressable_pool: Optional[int] = None          # Patients eligible for trial

    # Competition pressure (demand/supply model)
    competition_demand: Optional[int] = None        # Estimated recruiting demand from trials
    competition_ratio: Optional[float] = None       # demand / supply ratio
    competition_pressure: str = "unknown"           # 'low', 'moderate', 'high', 'extreme'
    competing_trial_details: list = []              # List of {nct_id, enrollment, sites_in_country, sites_total}

    # Dimension breakdown for transparent scoring (optional for backward compatibility)
    dimension_breakdown: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class CountryRankingResponse(BaseModel):
    """Response for country rankings."""
    project_id: int
    indication: str
    phase: str
    total_countries: int
    countries: List[CountryScore]
    generated_at: datetime

    # Current weights used
    weights: Dict[str, float]


# =============================================================================
# Site Ranking Schemas
# =============================================================================

class InvestigatorInfo(BaseModel):
    """Investigator information."""
    name: str
    trial_count: int = 0
    publications: int = 0
    primary_role: str = ""
    specialty: str = ""
    role: str = ""  # Legacy field for backwards compatibility


class SiteScore(BaseModel):
    """Individual site in ranking."""
    site_id: str
    site_name: str
    city: str
    state: Optional[str] = None
    country: str
    country_code: str

    # Scores
    final_score: float
    site_composite_score: float
    country_composite_score: float
    rank: int

    # Component scores (0-100)
    experience_score: float
    pi_strength_score: float
    capacity_score: float
    compliance_score: float
    protocol_match_score: float

    # Trial data
    trial_count: int
    indication_trial_count: int
    completion_rate: float
    competing_trial_count: int

    # Top investigators
    investigators: List[InvestigatorInfo] = []

    # Flags
    red_flags: List[str] = []
    yellow_flags: List[str] = []
    strengths: List[str] = []

    # Shortlist status
    is_shortlisted: bool = False

    # Citeline enrichment status
    citeline_enriched: bool = False
    citeline_match_type: Optional[str] = None  # 'pi_confirmed', 'pi_discovery', 'org_city_fuzzy', etc.
    citeline_tier: Optional[str] = None        # Gold/Silver/Bronze from Citeline
    citeline_pi_discovery: Optional[Dict[str, Any]] = None  # Discovered PI data if site had no PI

    # Data confidence tier (based on enrichment sources)
    data_confidence: str = "low"  # "high", "medium", "low"
    data_sources_checked: List[str] = ["ctgov"]  # e.g. ["ctgov", "citeline", "pubmed", "compliance"]
    data_source_count: int = 1  # Number of sources with data

    # Percentile rankings (within-country)
    percentile: float = 0.0  # 0-100, percentile rank within this country
    calibration_band: str = "Watchlist"  # "Strong", "Viable", "Watchlist", or "DNR"
    dimension_percentiles: Dict[str, float] = {}  # percentile for each of the 5 dimensions

    class Config:
        from_attributes = True


class SiteRankingResponse(BaseModel):
    """Response for site rankings within a country."""
    project_id: int
    country_code: str
    country_name: str
    indication: str
    total_sites: int
    sites: List[SiteScore]
    generated_at: datetime

    # Current weights used
    weights: Dict[str, float]


# =============================================================================
# Site Detail Schemas
# =============================================================================

class TrialHistoryItem(BaseModel):
    """Trial in site's history."""
    nct_id: str
    title: str
    phase: str
    status: str
    enrollment: Optional[int] = None
    conditions: List[str] = []


class SiteDetailResponse(BaseModel):
    """Full detail card for a single site."""
    site_id: str
    site_name: str
    city: str
    state: Optional[str] = None
    country: str
    country_code: str

    # All scores
    final_score: float
    site_composite_score: float
    country_composite_score: float
    experience_score: float
    pi_strength_score: float
    capacity_score: float
    compliance_score: float
    protocol_match_score: float

    # Trial analytics
    trial_count: int
    indication_trial_count: int
    phase_match_trials: int = 0
    completed_trials: int
    terminated_trials: int = 0
    completion_rate: float
    competing_trial_count: int

    # Investigators
    investigators: List[InvestigatorInfo] = []

    # Trial history
    trial_history: List[TrialHistoryItem] = []
    therapeutic_areas: List[str] = []

    # Analysis
    red_flags: List[str] = []
    yellow_flags: List[str] = []
    strengths: List[str] = []
    gap_analysis: Optional[str] = None

    # Enrichment status
    fda_enriched: bool = False
    pubmed_enriched: bool = False

    # Shortlist
    is_shortlisted: bool = False

    # Citeline enrichment status
    citeline_enriched: bool = False
    citeline_match_type: Optional[str] = None
    citeline_tier: Optional[str] = None
    citeline_pi_discovery: Optional[Dict[str, Any]] = None

    # Enrichment data
    pubmed_data: Optional[Dict[str, Any]] = None  # PubMed publication data
    fda_data: Optional[Dict[str, Any]] = None     # FDA inspection/warning data
    citeline_enrichment: Optional[Dict[str, Any]] = None  # Full Citeline enrichment data
    compliance_data: Optional[Dict[str, Any]] = None  # Compliance data (NPI, OIG, FDA inspections)

    # Data sources (list of source names for display)
    data_sources: List[str] = ["ClinicalTrials.gov"]


# =============================================================================
# Weight Adjustment Schemas
# =============================================================================

class CountryWeights(BaseModel):
    """Country scoring weights (must sum to 1.0)."""
    trial_experience: float = Field(0.30, ge=0, le=1)
    site_density: float = Field(0.25, ge=0, le=1)
    competition: float = Field(0.20, ge=0, le=1)
    regulatory: float = Field(0.15, ge=0, le=1)
    prevalence: float = Field(0.10, ge=0, le=1)


class SiteWeights(BaseModel):
    """Site scoring weights (must sum to 1.0)."""
    experience: float = Field(0.35, ge=0, le=1)
    pi_strength: float = Field(0.20, ge=0, le=1)
    capacity: float = Field(0.20, ge=0, le=1)
    compliance: float = Field(0.15, ge=0, le=1)
    protocol_match: float = Field(0.10, ge=0, le=1)


class WeightAdjustmentRequest(BaseModel):
    """Request to adjust scoring weights."""
    country_weights: Optional[CountryWeights] = None
    site_weights: Optional[SiteWeights] = None
    site_country_ratio: Optional[float] = Field(
        None, ge=0, le=1,
        description="How much to weight site vs country (0.7 = 70% site, 30% country)"
    )


class WeightAdjustmentResponse(BaseModel):
    """Response after weight adjustment."""
    project_id: int
    country_weights: Dict[str, float]
    site_weights: Dict[str, float]
    site_country_ratio: float
    message: str


class SiteWeightsUpdateRequest(BaseModel):
    """Request to update site scoring weights with optional preset name."""
    weights: SiteWeights
    preset_name: Optional[str] = Field(
        None,
        description="Preset name: 'phase_1', 'phase_2', 'phase_3', or 'custom'"
    )


class SiteWeightsUpdateResponse(BaseModel):
    """Response after site weights update."""
    status: str
    weights: Dict[str, float]
    preset_name: Optional[str] = None


# =============================================================================
# Shortlist Schemas
# =============================================================================

class ShortlistAction(BaseModel):
    """Request to add/remove site from shortlist."""
    site_id: str
    action: str = Field(..., pattern="^(add|remove)$")
    notes: Optional[str] = None


class ShortlistResponse(BaseModel):
    """Response for shortlist operations."""
    project_id: int
    site_id: str
    is_shortlisted: bool
    message: str


class ShortlistSummary(BaseModel):
    """Summary of all shortlisted sites."""
    project_id: int
    total_shortlisted: int
    sites: List[SiteScore]
    countries_represented: List[str]


# =============================================================================
# Export Schemas
# =============================================================================

class ExportRequest(BaseModel):
    """Request to export project data."""
    format: str = Field("excel", pattern="^(excel|pdf|csv)$")
    include_countries: bool = True
    include_sites: bool = True
    include_shortlisted_only: bool = False
    country_codes: Optional[List[str]] = None  # Filter to specific countries


class ExportResponse(BaseModel):
    """Response with export file info."""
    project_id: int
    format: str
    file_path: str
    file_size_bytes: int
    download_url: str
    generated_at: datetime


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
