"""
Base data source abstraction for SiteSync Screener.

All data sources (ClinicalTrials.gov, openFDA, PubMed, Citeline imports)
implement this interface so the scoring engine treats them uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime


@dataclass
class TrialRecord:
    """A clinical trial from any data source."""
    nct_id: Optional[str] = None
    title: str = ""
    phase: str = ""
    status: str = ""  # recruiting, completed, terminated, etc.
    condition: str = ""
    conditions: List[str] = field(default_factory=list)
    intervention: str = ""
    sponsor: str = ""
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    country: str = ""
    sites: List[Dict] = field(default_factory=list)  # [{name, city, country, pi}]
    source: str = ""  # 'ctgov', 'citeline', etc.

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class InvestigatorRecord:
    """A principal investigator / site investigator."""
    name: str = ""
    site_name: str = ""
    city: str = ""
    state: str = ""
    country: str = ""
    trial_count: int = 0
    indication_trial_count: int = 0
    phase_match_count: int = 0
    therapeutic_areas: List[str] = field(default_factory=list)
    publications: int = 0
    fda_inspections: int = 0
    fda_warnings: int = 0
    is_debarred: bool = False
    last_trial_date: Optional[str] = None
    source: str = ""
    raw_data: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SiteRecord:
    """A clinical trial site from any data source."""
    site_name: str = ""
    site_id: Optional[str] = None  # Source-specific ID
    city: str = ""
    state: Optional[str] = None
    country: str = ""
    country_code: Optional[str] = None
    investigators: List[InvestigatorRecord] = field(default_factory=list)
    trial_count: int = 0
    indication_trial_count: int = 0
    phase_match_count: int = 0
    completed_trials: int = 0
    terminated_trials: int = 0
    recruiting_trials: int = 0  # current competing workload
    avg_enrollment: Optional[float] = None
    therapeutic_areas: List[str] = field(default_factory=list)
    last_active: Optional[str] = None
    fda_warnings: int = 0
    publications: int = 0
    source: str = ""
    raw_data: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        # Convert nested InvestigatorRecords to dicts
        result["investigators"] = [
            inv.to_dict() if hasattr(inv, 'to_dict') else inv
            for inv in self.investigators
        ]
        return result


@dataclass
class CountryRecord:
    """Country-level feasibility data."""
    country_name: str = ""
    country_code: str = ""
    site_count: int = 0
    investigator_count: int = 0
    total_trials: int = 0
    indication_trials: int = 0
    phase_match_trials: int = 0

    # Weighted trial experience (recency, phase match, completion status)
    weighted_experience: float = 0.0          # Sum of weighted trial scores
    experience_weights_used: bool = False     # Whether weights were applied
    experience_trial_count: int = 0           # Raw count (for display alongside weighted)
    actively_recruiting: int = 0  # competing trials
    completed_trials: int = 0
    terminated_trials: int = 0
    avg_enrollment_per_site: Optional[float] = None
    regulatory_summary: Optional[str] = None  # AI-generated explanation
    prevalence_estimate: Optional[str] = None  # AI-generated
    soc_available: Optional[bool] = None
    source: str = ""

    # Scoring fields (populated by country_feasibility.py)
    trial_experience_score: float = 0.0
    site_density_score: float = 0.0
    competition_score: float = 0.0
    regulatory_score: float = 0.0
    prevalence_score: float = 0.0
    composite_score: float = 0.0

    # World Bank indicator raw values (for display/transparency)
    regulatory_quality_raw: Optional[float] = None  # RQ.EST (-2.5 to 2.5)
    physician_density: Optional[float] = None       # Physicians per 1,000 people
    logistics_index: Optional[float] = None         # LPI (1-5 scale)
    health_expenditure_pct: Optional[float] = None  # Health exp % of GDP

    # WHO GBT / SRA regulatory maturity bonus (for transparency)
    regulatory_gbt_bonus: Optional[float] = None    # Bonus points (0, 8, 12, or 15)
    regulatory_gbt_tier: Optional[str] = None       # 'SRA', 'WHO GBT ML4', 'WHO GBT ML3', 'Unclassified'
    regulatory_gbt_authority: Optional[str] = None  # e.g., 'FDA (ICH Founding Member)'
    regulatory_base_score: Optional[float] = None   # World Bank composite before bonus

    # Missing data flags for re-weighting
    regulatory_missing: bool = False
    prevalence_missing: bool = False

    # Population data (from World Bank)
    population: Optional[int] = None

    # Prevalence data (from GPT epidemiology lookup)
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

    # Per-trial competing data (from CT.gov, for accurate demand calculation)
    competing_trial_details: List[Dict] = field(default_factory=list)  # [{nct_id, enrollment, sites_in_country, sites_total}]
    avg_competing_enrollment: Optional[float] = None  # Average enrollment across competing trials

    # Dimension breakdown for transparent scoring (populated by country_feasibility.py)
    dimension_breakdown: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProtocolCriteria:
    """
    Structured protocol requirements - SPIRIT/ICH M11 aligned.
    Comprehensive extraction for sponsor/consultant feasibility decisions.
    """
    # === Study Identity ===
    study_title: str = ""           # Full descriptive title
    protocol_number: str = ""       # e.g., CTJ301UC201
    sponsor: str = ""
    phase: str = ""
    therapeutic_area: str = ""

    # === Study Design ===
    design_type: str = ""           # e.g., "Randomized, double-blind, placebo-controlled"
    arm_count: Optional[int] = None # e.g., 3
    arms_description: List[str] = field(default_factory=list)  # ["Drug 300mg", "Drug 600mg", "Placebo"]
    allocation_ratio: str = ""      # e.g., "1:1:1"
    blinding: str = ""              # "Double-blind", "Open-label", "Single-blind"
    control_type: str = ""          # "Placebo-controlled", "Active-controlled", "No control"

    # === Investigational Product ===
    drug_name: str = ""             # e.g., "CTJ301" or "sutimlimab"
    drug_class: str = ""            # e.g., "monoclonal antibody", "small molecule"
    dose_and_route: str = ""        # e.g., "300mg or 600mg IV infusion"
    dosing_frequency: str = ""      # e.g., "Q2W (every 2 weeks)"
    administration_duration: str = "" # e.g., "60-minute IV infusion"

    # === Patient Population ===
    indication: str = ""
    indication_detail: str = ""     # e.g., "Moderate-to-severe active UC with Mayo score ≥6"
    age_range: str = ""             # e.g., "18-75 years"
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    sex_eligibility: str = ""       # e.g., "All", "Male only", "Female only"
    enrollment_target: Optional[int] = None
    patients_per_site: Optional[int] = None
    target_countries: List[str] = field(default_factory=list)

    # === Eligibility Criteria ===
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)

    # === Study Timeline ===
    screening_period: str = ""      # e.g., "Up to 4 weeks"
    treatment_duration: str = ""    # e.g., "12 weeks"
    follow_up_duration: str = ""    # e.g., "4 weeks safety follow-up"
    total_duration: str = ""        # e.g., "~20 weeks per patient"
    duration: str = ""              # Legacy field - total duration string
    duration_weeks: Optional[int] = None
    total_visits: Optional[int] = None  # e.g., 10
    visit_count: Optional[int] = None   # Legacy alias
    visit_frequency: str = ""       # e.g., "Every 2 weeks during treatment"

    # === Endpoints ===
    primary_endpoint: str = ""      # e.g., "Clinical and endoscopic remission at Week 12"
    secondary_endpoints: List[str] = field(default_factory=list)
    primary_assessment: str = ""    # e.g., "Mayo Score" or "RECIST 1.1"

    # === Site Requirements ===
    required_equipment: List[str] = field(default_factory=list)
    required_staff: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)

    # === Site Capability Flags ===
    requires_endoscopy: bool = False
    requires_infusion: bool = False
    requires_imaging: List[str] = field(default_factory=list)  # ["MRI", "CT", "PET"]
    requires_biopsy: bool = False
    storage_requirements: List[str] = field(default_factory=list)  # ["-20°C", "-80°C"]
    sample_processing: List[str] = field(default_factory=list)  # ["centrifuge", "PK processing"]
    lab_requirements: List[str] = field(default_factory=list)   # ["hematology", "chemistry"]
    ecg_required: bool = False

    # === Safety & Oversight ===
    dsmb_required: bool = False
    safety_monitoring: str = ""     # e.g., "Independent DSMB reviews after every 30 patients"

    # === Metadata ===
    extraction_confidence: float = 0.0
    extraction_warnings: List[str] = field(default_factory=list)
    raw_extraction: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_phase_filter(self) -> Optional[List[str]]:
        """Convert phase string to CT.gov API filter format."""
        phase_lower = self.phase.lower().strip()

        # Map common phase formats to CT.gov API values
        phase_map = {
            "phase i": ["PHASE1"],
            "phase 1": ["PHASE1"],
            "phase ii": ["PHASE2"],
            "phase 2": ["PHASE2"],
            "phase iii": ["PHASE3"],
            "phase 3": ["PHASE3"],
            "phase iv": ["PHASE4"],
            "phase 4": ["PHASE4"],
            "phase i/ii": ["PHASE1", "PHASE2"],
            "phase 1/2": ["PHASE1", "PHASE2"],
            "phase ii/iii": ["PHASE2", "PHASE3"],
            "phase 2/3": ["PHASE2", "PHASE3"],
        }

        return phase_map.get(phase_lower)


class DataSource(ABC):
    """Abstract interface for all Screener data sources."""

    source_name: str = "unknown"

    @abstractmethod
    async def search_trials_by_condition(
        self,
        condition: str,
        phase: Optional[List[str]] = None,
        status: Optional[List[str]] = None,
        country: Optional[str] = None,
        max_results: int = 500
    ) -> List[TrialRecord]:
        """Search for trials matching condition/indication."""
        pass

    @abstractmethod
    async def get_sites_for_condition(
        self,
        condition: str,
        phase: Optional[List[str]] = None,
        country: Optional[str] = None,
        max_results: int = 500
    ) -> List[SiteRecord]:
        """Get sites that have participated in trials for this condition."""
        pass

    @abstractmethod
    async def get_country_summary(
        self,
        condition: str,
        phase: Optional[List[str]] = None
    ) -> List[CountryRecord]:
        """Get country-level trial activity summary."""
        pass

    @abstractmethod
    async def get_competing_trials(
        self,
        condition: str,
        country: Optional[str] = None
    ) -> List[TrialRecord]:
        """Get currently recruiting trials competing for same patient pool."""
        pass


# ISO 3166-1 alpha-2 country code mapping (common clinical trial countries)
COUNTRY_CODE_MAP = {
    "united states": "US",
    "united states of america": "US",
    "usa": "US",
    "united kingdom": "GB",
    "uk": "GB",
    "great britain": "GB",
    "germany": "DE",
    "france": "FR",
    "italy": "IT",
    "spain": "ES",
    "canada": "CA",
    "australia": "AU",
    "japan": "JP",
    "china": "CN",
    "south korea": "KR",
    "korea, republic of": "KR",
    "india": "IN",
    "brazil": "BR",
    "mexico": "MX",
    "netherlands": "NL",
    "belgium": "BE",
    "switzerland": "CH",
    "austria": "AT",
    "poland": "PL",
    "czech republic": "CZ",
    "czechia": "CZ",
    "hungary": "HU",
    "israel": "IL",
    "south africa": "ZA",
    "argentina": "AR",
    "russia": "RU",
    "russian federation": "RU",
    "taiwan": "TW",
    "taiwan, province of china": "TW",
    "hong kong": "HK",
    "singapore": "SG",
    "new zealand": "NZ",
    "ireland": "IE",
    "denmark": "DK",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "portugal": "PT",
    "greece": "GR",
    "turkey": "TR",
    "ukraine": "UA",
    "romania": "RO",
    "bulgaria": "BG",
    "croatia": "HR",
    "slovakia": "SK",
    "slovenia": "SI",
    "serbia": "RS",
    "malaysia": "MY",
    "thailand": "TH",
    "philippines": "PH",
    "indonesia": "ID",
    "vietnam": "VN",
    "egypt": "EG",
    "saudi arabia": "SA",
    "united arab emirates": "AE",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE",
    # Additional countries and alternate spellings
    "türkiye": "TR",  # New official name for Turkey
    "turkiye": "TR",
    "puerto rico": "PR",
    "lithuania": "LT",
    "latvia": "LV",
    "estonia": "EE",
    "cyprus": "CY",
    "malta": "MT",
    "luxembourg": "LU",
    "iceland": "IS",
    "liechtenstein": "LI",
    "monaco": "MC",
    "macau": "MO",
    "macao": "MO",
    "laos": "LA",
    "lao people's democratic republic": "LA",
    "cambodia": "KH",
    "myanmar": "MM",
    "bangladesh": "BD",
    "pakistan": "PK",
    "sri lanka": "LK",
    "nepal": "NP",
    "mongolia": "MN",
    "kazakhstan": "KZ",
    "uzbekistan": "UZ",
    "georgia": "GE",
    "armenia": "AM",
    "azerbaijan": "AZ",
    "belarus": "BY",
    "moldova": "MD",
    "republic of moldova": "MD",
    "north macedonia": "MK",
    "bosnia and herzegovina": "BA",
    "montenegro": "ME",
    "kosovo": "XK",
    "albania": "AL",
    "morocco": "MA",
    "tunisia": "TN",
    "algeria": "DZ",
    "nigeria": "NG",
    "kenya": "KE",
    "ghana": "GH",
    "ethiopia": "ET",
    "tanzania": "TZ",
    "uganda": "UG",
    "zimbabwe": "ZW",
    "jordan": "JO",
    "lebanon": "LB",
    "iraq": "IQ",
    "iran": "IR",
    "iran, islamic republic of": "IR",
    "kuwait": "KW",
    "qatar": "QA",
    "bahrain": "BH",
    "oman": "OM",
    "ecuador": "EC",
    "venezuela": "VE",
    "bolivia": "BO",
    "paraguay": "PY",
    "uruguay": "UY",
    "costa rica": "CR",
    "panama": "PA",
    "guatemala": "GT",
    "honduras": "HN",
    "el salvador": "SV",
    "nicaragua": "NI",
    "dominican republic": "DO",
    "jamaica": "JM",
    "trinidad and tobago": "TT",
    "cuba": "CU",
}


def get_country_code(country_name: str) -> str:
    """Get ISO 3166-1 alpha-2 country code from country name.

    Returns empty string for unknown countries instead of invalid codes.
    """
    if not country_name:
        return ""

    # Normalize: lowercase, strip whitespace
    normalized = country_name.lower().strip()

    # Direct lookup
    if normalized in COUNTRY_CODE_MAP:
        return COUNTRY_CODE_MAP[normalized]

    # Try removing common suffixes/variations
    # e.g., "Korea, Republic of" -> check "korea"
    for variant in [
        normalized,
        normalized.replace(",", "").strip(),
        normalized.split(",")[0].strip(),  # Take before comma
        normalized.replace("the ", "").strip(),
    ]:
        if variant in COUNTRY_CODE_MAP:
            return COUNTRY_CODE_MAP[variant]

    # Check if input looks like a valid 2-letter code already
    if len(country_name) == 2 and country_name.isalpha():
        return country_name.upper()

    # Unknown country - log and return empty (better than invalid code)
    import logging
    logging.getLogger(__name__).warning(f"Unknown country: '{country_name}' - no ISO code mapping")
    return ""
