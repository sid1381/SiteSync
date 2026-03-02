# SiteSync Screener — Architecture & Build Specification
## For Claude Code Implementation

---

## WORKFLOW DIAGRAM

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SITESYNC SCREENER WORKFLOW                        │
│                  (Sponsor / Consultant Facing)                      │
└─────────────────────────────────────────────────────────────────────┘

  USER ENTRY
  ─────────
  Screener Dashboard → [New Project] button
  └── Shows past projects, status, dates


  STEP 1: PROTOCOL UPLOAD & AI EXTRACTION
  ────────────────────────────────────────
  ┌──────────────┐     ┌──────────────────────────┐     ┌─────────────────┐
  │  Upload PDF  │ ──► │ protocol_requirement_     │ ──► │ User Reviews &  │
  │  (Protocol)  │     │ extractor.py (EXISTING)   │     │ Confirms        │
  └──────────────┘     │ + screener_protocol_      │     └─────────────────┘
                       │   analyzer.py (NEW)       │
                       └──────────────────────────┘

  Extracted output (displayed for confirmation):
  ├── indication: "NASH with liver fibrosis (F2-F3)"
  ├── phase: "Phase II"
  ├── enrollment_target: 450 total, ~8 per site
  ├── inclusion_criteria: ["Age 18-75", "Biopsy-confirmed NASH", ...]
  ├── exclusion_criteria: ["Decompensated cirrhosis", ...]
  ├── required_equipment: ["FibroScan", "MRI-PDFF", "-80°C storage"]
  ├── required_staff: ["Hepatologist PI", "GCP-certified coordinators"]
  ├── procedures: ["Liver biopsy", "FibroScan", "Blood draws Q4W"]
  ├── duration: "48 weeks"
  ├── therapeutic_area: "Gastroenterology / Hepatology"
  └── sponsor: "Example Pharma"


  STEP 2: COUNTRY FEASIBILITY RANKING
  ────────────────────────────────────
  Triggered automatically after Step 1 confirmation.

  ┌────────────────────┐
  │  ClinicalTrials.gov │──► Trial count per country for indication
  │  (ctgov_source.py)  │──► Site count per country
  │                     │──► Competing recruiting trials per country
  │                     │──► Phase-matched trial density
  └────────────────────┘
           │
           ▼
  ┌────────────────────┐
  │  GPT-4o Analysis   │──► Regulatory environment summary per country
  │  (openai_client.py)│──► Disease prevalence estimates
  │                    │──► Standard of care availability assessment
  └────────────────────┘
           │
           ▼
  ┌────────────────────────────────────────────────────────────┐
  │  COUNTRY RANKING TABLE                                      │
  │                                                              │
  │  Rank │ Country │ Trial Exp │ Sites │ Competing │ Score     │
  │  ─────┼─────────┼───────────┼───────┼───────────┼─────────  │
  │  1    │ USA     │ 142 trials│ 387   │ 23 active │ 92/100   │
  │  2    │ Germany │ 38 trials │ 89    │ 8 active  │ 85/100   │
  │  3    │ UK      │ 31 trials │ 67    │ 12 active │ 78/100   │
  │  ...  │ ...     │ ...       │ ...   │ ...       │ ...      │
  │                                                              │
  │  [Adjust Weights] [Filter Region] [Drill Into Country ►]   │
  └────────────────────────────────────────────────────────────┘


  STEP 3: SITE-LEVEL INTELLIGENCE (per country)
  ──────────────────────────────────────────────
  User clicks a country → site list within that country.

  Data Sources (ALL PUBLIC & FREE):

  ┌────────────────────┐
  │  ClinicalTrials.gov│──► Site name, PI, trial history in indication
  │                    │──► Completion rates, enrollment sizes
  │                    │──► Currently recruiting (competing workload)
  └────────────────────┘
           +
  ┌────────────────────┐
  │  openFDA API       │──► Clinical investigator inspection records
  │  (openfda.py)      │──► 483 observations, warning letters
  │                    │──► Debarment list check
  └────────────────────┘
           +
  ┌────────────────────┐
  │  PubMed/NCBI API   │──► PI publication count in therapeutic area
  │  (pubmed.py)       │──► H-index proxy, co-author network
  └────────────────────┘
           +
  ┌────────────────────┐
  │  GPT-4o Analysis   │──► Protocol-specific gap analysis per site
  │                    │──► Red flag identification
  │                    │──► Composite narrative summary
  └────────────────────┘
           │
           ▼
  ┌────────────────────────────────────────────────────────────┐
  │  SITE RANKING TABLE (within selected country)               │
  │                                                              │
  │  Rank │ Site          │ PI          │ Trials │ Score        │
  │  ─────┼───────────────┼─────────────┼────────┼────────────  │
  │  1    │ Mayo Clinic   │ Dr. Smith   │ 12     │ 94/100      │
  │  2    │ Johns Hopkins │ Dr. Chen    │ 9      │ 88/100      │
  │  ...  │ ...           │ ...         │ ...    │ ...         │
  │                                                              │
  │  [View Site Card] [Shortlist] [Export]                      │
  └────────────────────────────────────────────────────────────┘


  STEP 4: OUTPUT & ACTIONS
  ────────────────────────
  ┌────────────────────────────────────────────────┐
  │  Final ranked list: ALL shortlisted sites       │
  │                                                 │
  │  Site Score = (Site × 0.7) + (Country × 0.3)  │
  │  (weights adjustable)                           │
  │                                                 │
  │  Actions:                                       │
  │  ├── Filter / adjust weights                   │
  │  ├── View detailed site cards                  │
  │  ├── Flag / shortlist sites                    │
  │  └── Export to Excel / PDF                     │
  └────────────────────────────────────────────────┘


  OPTIONAL: SITETROVE ENRICHMENT (Future)
  ───────────────────────────────────────
  Separate "Enrich Data" button/screen:
  ├── Upload Citeline CSV/Excel export
  ├── System parses & merges with public data
  ├── Enriched fields get "Citeline" badge
  └── Scores recalculate with additional data
```

---

## FILE STRUCTURE — What To Create

All new files. Do NOT modify existing Core files.

```
app/
  services/
    screener/                         # NEW directory
      __init__.py                     # Package init
      protocol_analyzer.py            # Wraps existing extractor for Screener output
      country_feasibility.py          # Country ranking engine
      site_intelligence.py            # Site-level scoring
      scoring_engine.py               # Composite scoring
      data_sources/                   # NEW directory
        __init__.py
        base.py                       # Abstract base + dataclasses
        ctgov_source.py               # ClinicalTrials.gov queries
        openfda_source.py             # FDA inspection records
        pubmed_source.py              # PI publications
        citeline_import.py            # Future: parse Citeline exports
  routes/
    screener.py                       # NEW - Screener API endpoints
  schemas/
    screener.py                       # NEW - Pydantic models for Screener
  models/
    screener_models.py                # NEW - DB models (or add to models.py)

frontend/
  app/
    screener/
      page.tsx                        # NEW - Screener frontend

migrations/
  versions/
    xxxx_add_screener_tables.py       # NEW - Alembic migration
```

---

## PHASE 1: DATA SOURCES + PROTOCOL ANALYZER

### File: app/services/screener/data_sources/base.py

Purpose: Shared dataclasses and abstract base class for all data sources.

```python
"""
Base data source abstraction for SiteSync Screener.
All data sources (ClinicalTrials.gov, openFDA, PubMed, Citeline imports)
implement this interface so the scoring engine treats them uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime


@dataclass
class TrialRecord:
    """A clinical trial from any data source."""
    nct_id: Optional[str] = None
    title: str = ""
    phase: str = ""
    status: str = ""  # recruiting, completed, terminated, etc.
    condition: str = ""
    intervention: str = ""
    sponsor: str = ""
    enrollment: Optional[int] = None
    start_date: Optional[str] = None
    completion_date: Optional[str] = None
    country: str = ""
    sites: List[Dict] = field(default_factory=list)  # [{name, city, country, pi}]
    source: str = ""  # 'ctgov', 'citeline', etc.


@dataclass
class InvestigatorRecord:
    """A principal investigator / site investigator."""
    name: str = ""
    site_name: str = ""
    city: str = ""
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
    actively_recruiting: int = 0  # competing trials
    completed_trials: int = 0
    avg_enrollment_per_site: Optional[float] = None
    regulatory_summary: Optional[str] = None  # AI-generated
    prevalence_estimate: Optional[str] = None  # AI-generated
    soc_available: Optional[bool] = None
    source: str = ""


@dataclass
class ProtocolCriteria:
    """Structured protocol requirements extracted in Step 1.
    This is the search criteria for the entire Screener workflow."""
    indication: str = ""
    therapeutic_area: str = ""
    phase: str = ""
    sponsor: str = ""
    enrollment_target: Optional[int] = None
    patients_per_site: Optional[int] = None
    duration: str = ""
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)
    required_equipment: List[str] = field(default_factory=list)
    required_staff: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)
    visit_count: Optional[int] = None
    study_title: str = ""
    raw_extraction: Optional[Dict] = None  # Full extraction output


class DataSource(ABC):
    """Abstract interface for all Screener data sources."""

    source_name: str = "unknown"

    @abstractmethod
    async def search_trials_by_condition(
        self,
        condition: str,
        phase: Optional[str] = None,
        status: Optional[str] = None,
        country: Optional[str] = None,
        max_results: int = 100
    ) -> List[TrialRecord]:
        """Search for trials matching condition/indication."""
        pass

    @abstractmethod
    async def get_sites_for_condition(
        self,
        condition: str,
        phase: Optional[str] = None,
        country: Optional[str] = None,
        max_results: int = 200
    ) -> List[SiteRecord]:
        """Get sites that have participated in trials for this condition."""
        pass

    @abstractmethod
    async def get_country_summary(
        self,
        condition: str,
        phase: Optional[str] = None
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
```

### File: app/services/screener/data_sources/ctgov_source.py

Purpose: ClinicalTrials.gov as a Screener data source. This is the PRIMARY
data source. Uses ClinicalTrials.gov API v2.

Key implementation notes:
- Reuse patterns from existing app/services/ctgov.py and ctgov_client.py
- Use the v2 API: https://clinicaltrials.gov/api/v2/studies
- Rate limit: ~3 requests/second (add asyncio.sleep(0.35) between calls)
- Cache results in PostgreSQL to avoid repeated calls for same queries
- Parse the nested JSON response to extract sites, investigators, countries

ClinicalTrials.gov API v2 key endpoints:
```
GET https://clinicaltrials.gov/api/v2/studies
  ?query.cond={condition}
  &filter.overallStatus={RECRUITING,COMPLETED,TERMINATED}
  &filter.phase={PHASE2,PHASE3}
  &countTotal=true
  &pageSize=100
  &fields=NCTId,BriefTitle,Phase,OverallStatus,EnrollmentCount,
          StartDate,CompletionDate,LeadSponsorName,Condition,
          LocationFacility,LocationCity,LocationCountry,
          LocationStatus,OverallOfficialName,OverallOfficialRole
```

The response has `studies[].protocolSection.contactsLocationsModule.locations[]`
which gives us per-site data including facility name, city, country, and status.

The key capability this source provides:
1. Country-level trial counts (group locations by country)
2. Site-level trial history (group locations by facility name + city)
3. Investigator identification (from OverallOfficial fields)
4. Competing trial analysis (filter: status=RECRUITING, same condition)
5. Completion rate analysis (count COMPLETED vs TERMINATED per site)

### File: app/services/screener/data_sources/openfda_source.py

Purpose: FDA clinical investigator inspection data.

API: https://api.fda.gov/other/inspections.json (no key needed for <1000/day)
Also: https://api.fda.gov/other/debarment.json

What this provides:
- Inspection history for clinical investigators (search by name)
- 483 observations (violations found during inspection)
- Warning letters
- Debarment status (investigators barred from conducting trials)

This is a RED FLAG detector — sites/PIs with FDA issues get penalized in scoring.

### File: app/services/screener/data_sources/pubmed_source.py

Purpose: PI publication intelligence via NCBI E-utilities API.

APIs (free, no key needed for <3/sec, key for higher rate):
- Search: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
- Details: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi

What this provides:
- Publication count for PI in therapeutic area
- Recency of publications
- Co-author network (signals collaborative relationships)

This is a PI QUALITY signal — prolific publishers in the indication are stronger PIs.

### File: app/services/screener/protocol_analyzer.py

Purpose: Wraps existing protocol_requirement_extractor.py for Screener use.
Converts the extraction output into a ProtocolCriteria dataclass that
drives the entire Screener workflow.

```python
"""
Protocol Analyzer for Screener.
Reuses existing protocol_requirement_extractor.py but structures output
as ProtocolCriteria for use in country ranking and site intelligence.
"""

from app.services.protocol_requirement_extractor import ProtocolRequirementExtractor
from app.services.openai_client import OpenAIClient
from app.services.screener.data_sources.base import ProtocolCriteria


class ScreenerProtocolAnalyzer:
    """Analyzes protocol PDF and produces structured search criteria."""

    def __init__(self):
        self.extractor = ProtocolRequirementExtractor()
        self.openai = OpenAIClient()

    async def analyze_protocol(self, pdf_bytes: bytes) -> ProtocolCriteria:
        """
        Extract protocol requirements and structure as ProtocolCriteria.

        Uses existing extractor then normalizes output into Screener format.
        """
        # Step 1: Use existing extraction (this already works well)
        raw_extraction = self.extractor.extract_requirements(pdf_bytes)

        # Step 2: Map to ProtocolCriteria dataclass
        criteria = ProtocolCriteria(
            indication=self._extract_indication(raw_extraction),
            therapeutic_area=self._extract_therapeutic_area(raw_extraction),
            phase=raw_extraction.get("study_identification", {}).get("phase", ""),
            sponsor=raw_extraction.get("study_identification", {}).get("sponsor", ""),
            enrollment_target=self._extract_enrollment(raw_extraction),
            duration=raw_extraction.get("timeline", {}).get("duration", ""),
            inclusion_criteria=raw_extraction.get("patient_population", {}).get("inclusion", []),
            exclusion_criteria=raw_extraction.get("patient_population", {}).get("exclusion", []),
            required_equipment=raw_extraction.get("equipment_required", []),
            required_staff=raw_extraction.get("staff_requirements", []),
            procedures=raw_extraction.get("procedures", []),
            study_title=raw_extraction.get("study_identification", {}).get("title", ""),
            raw_extraction=raw_extraction
        )

        # Step 3: If indication is vague, use GPT to refine search terms
        if not criteria.indication or len(criteria.indication) < 3:
            criteria = await self._refine_with_ai(criteria, raw_extraction)

        return criteria

    def _extract_indication(self, raw: dict) -> str:
        """Pull primary indication from extraction."""
        pop = raw.get("patient_population", {})
        return (
            pop.get("primary_indication", "") or
            pop.get("condition", "") or
            pop.get("disease", "") or
            raw.get("study_identification", {}).get("condition", "")
        )

    def _extract_therapeutic_area(self, raw: dict) -> str:
        """Determine therapeutic area."""
        return raw.get("study_identification", {}).get("therapeutic_area", "")

    def _extract_enrollment(self, raw: dict) -> Optional[int]:
        """Extract enrollment target as integer."""
        timeline = raw.get("timeline", {})
        target = timeline.get("enrollment_target", None)
        if isinstance(target, int):
            return target
        if isinstance(target, str):
            import re
            numbers = re.findall(r'\d+', target)
            return int(numbers[0]) if numbers else None
        return None

    async def _refine_with_ai(self, criteria: ProtocolCriteria, raw: dict) -> ProtocolCriteria:
        """Use GPT-4o to extract better search terms from raw extraction."""
        prompt = f"""Given this protocol extraction, identify:
1. The primary disease indication (specific, e.g., "NASH with liver fibrosis F2-F3")
2. The therapeutic area (e.g., "Hepatology", "Oncology")
3. MeSH-compatible search terms for ClinicalTrials.gov

Protocol data: {str(raw)[:3000]}

Respond as JSON: {{"indication": "...", "therapeutic_area": "...", "search_terms": ["...", "..."]}}"""

        response = await self.openai.create_json_completion(
            system_prompt="You are a clinical trial protocol analyst.",
            user_prompt=prompt,
            max_tokens=500
        )

        if response:
            criteria.indication = response.get("indication", criteria.indication)
            criteria.therapeutic_area = response.get("therapeutic_area", criteria.therapeutic_area)

        return criteria
```

---

## PHASE 2: COUNTRY FEASIBILITY ENGINE

### File: app/services/screener/country_feasibility.py

Purpose: Takes ProtocolCriteria → returns ranked list of CountryRecords.

Logic:
1. Query ClinicalTrials.gov for all trials matching indication
2. Aggregate by country: trial count, site count, investigator count
3. Query for competing trials (same condition, status=RECRUITING)
4. Use GPT-4o to generate regulatory summaries & prevalence estimates
5. Score each country and return ranked list

Scoring formula (each factor 0-100, then weighted):
- trial_experience_score (30%): Normalized trial count in indication
- site_density_score (25%): Number of qualified sites
- competition_score (20%): INVERSE — more competing = lower score
- regulatory_score (15%): AI-assessed regulatory friendliness
- prevalence_score (10%): Disease prevalence estimate

Country Feasibility Score = weighted sum of above factors.

### File: app/services/screener/site_intelligence.py

Purpose: Takes ProtocolCriteria + country → returns ranked SiteRecords.

Logic:
1. Get all sites in that country from ClinicalTrials.gov
2. For each site: count trials, indication matches, phase matches
3. Check FDA records for red flags (openFDA)
4. Check PI publications (PubMed)
5. Use GPT-4o for protocol-specific gap analysis
6. Score each site

Site scoring components:
- experience_score (35%): Trial count, indication match, phase match, recency
- pi_strength_score (20%): Publications, trial experience, specialization
- capacity_score (20%): Historical enrollment sizes, current workload
- compliance_score (15%): FDA record clean, no debarments
- protocol_match_score (10%): AI gap analysis vs protocol requirements

### File: app/services/screener/scoring_engine.py

Purpose: Combines country + site scores into final ranking.

Final Score = (Site Score × 0.7) + (Country Score × 0.3)
Weights adjustable by user.

---

## PHASE 3: API ROUTES

### File: app/routes/screener.py

Endpoints:
```
POST /screener/projects                    # Create new screener project
GET  /screener/projects                    # List all projects
GET  /screener/projects/{id}               # Get project details

POST /screener/projects/{id}/upload-protocol   # Upload & analyze protocol
POST /screener/projects/{id}/confirm-protocol  # User confirms extraction

GET  /screener/projects/{id}/countries     # Get country rankings
POST /screener/projects/{id}/countries/refresh  # Re-run with adjusted weights

GET  /screener/projects/{id}/countries/{code}/sites  # Sites in country
GET  /screener/projects/{id}/sites/{site_id}         # Detailed site card

POST /screener/projects/{id}/shortlist     # Add/remove from shortlist
GET  /screener/projects/{id}/shortlist     # Get shortlisted sites

GET  /screener/projects/{id}/export        # Export to Excel/PDF
```

---

## PHASE 4: DATABASE MODELS

### Add to app/models.py (or new file app/models/screener_models.py)

```python
class ScreenerProject(Base):
    __tablename__ = "screener_projects"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, default="draft")  # draft, analyzing, countries_ready, complete
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Protocol extraction results
    protocol_file_path = Column(String, nullable=True)
    protocol_criteria = Column(JSON, nullable=True)  # ProtocolCriteria as dict

    # Scoring weights (user-adjustable)
    country_weights = Column(JSON, default={
        "trial_experience": 0.30,
        "site_density": 0.25,
        "competition": 0.20,
        "regulatory": 0.15,
        "prevalence": 0.10
    })
    site_weights = Column(JSON, default={
        "experience": 0.35,
        "pi_strength": 0.20,
        "capacity": 0.20,
        "compliance": 0.15,
        "protocol_match": 0.10
    })
    site_country_ratio = Column(Float, default=0.7)  # site weight in final score


class ScreenerCountryResult(Base):
    __tablename__ = "screener_country_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("screener_projects.id"))
    country_name = Column(String)
    country_code = Column(String)

    # Raw data
    total_trials = Column(Integer, default=0)
    indication_trials = Column(Integer, default=0)
    site_count = Column(Integer, default=0)
    investigator_count = Column(Integer, default=0)
    competing_trials = Column(Integer, default=0)

    # Scores (0-100)
    trial_experience_score = Column(Float, default=0)
    site_density_score = Column(Float, default=0)
    competition_score = Column(Float, default=0)
    regulatory_score = Column(Float, default=0)
    prevalence_score = Column(Float, default=0)
    composite_score = Column(Float, default=0)

    # AI-generated content
    regulatory_summary = Column(Text, nullable=True)
    prevalence_estimate = Column(Text, nullable=True)

    data_sources = Column(JSON, nullable=True)  # Which sources contributed


class ScreenerSiteResult(Base):
    __tablename__ = "screener_site_results"

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("screener_projects.id"))
    country_code = Column(String)

    # Site identification
    site_name = Column(String)
    city = Column(String)
    state = Column(String, nullable=True)
    country = Column(String)

    # PI info
    pi_name = Column(String, nullable=True)
    pi_publications = Column(Integer, default=0)

    # Trial history
    total_trials = Column(Integer, default=0)
    indication_trials = Column(Integer, default=0)
    phase_match_trials = Column(Integer, default=0)
    completed_trials = Column(Integer, default=0)
    terminated_trials = Column(Integer, default=0)
    recruiting_trials = Column(Integer, default=0)

    # FDA
    fda_inspections = Column(Integer, default=0)
    fda_warnings = Column(Integer, default=0)
    is_debarred = Column(Boolean, default=False)

    # Scores (0-100)
    experience_score = Column(Float, default=0)
    pi_strength_score = Column(Float, default=0)
    capacity_score = Column(Float, default=0)
    compliance_score = Column(Float, default=0)
    protocol_match_score = Column(Float, default=0)
    site_composite_score = Column(Float, default=0)
    final_score = Column(Float, default=0)  # site + country weighted

    # AI analysis
    gap_analysis = Column(Text, nullable=True)
    red_flags = Column(JSON, nullable=True)

    # Shortlist
    is_shortlisted = Column(Boolean, default=False)

    data_sources = Column(JSON, nullable=True)
```

---

## PHASE 5: FRONTEND

### File: frontend/app/screener/page.tsx

Four main views matching the workflow:
1. Dashboard — project list, create new
2. Protocol Review — show extraction, let user edit/confirm
3. Country Ranking — table with scores, drill-down capability
4. Site Intelligence — site list per country, site detail cards

Design notes:
- Keep consistent with existing SiteSync UI style (Tailwind, Lucide icons)
- Use the same color palette and layout patterns as page.tsx
- The Screener is a SEPARATE page/route, not added to the Core interface
- Navigation: top-level tab or sidebar link to switch between Core and Screener

---

## INTEGRATION WITH EXISTING CODEBASE

### app/main.py — Add one line:
```python
from app.routes import screener as screener_routes
app.include_router(screener_routes.router)
```

### requirements.txt — Add:
```
httpx>=0.25.0       # Async HTTP client for API calls (ClinicalTrials.gov, FDA, PubMed)
```
Note: requests is sync — we should use httpx for async API calls in the Screener
since we're making multiple concurrent external API requests.

### docker-compose.yml — No changes needed (same backend/frontend containers)

### Alembic migration — New migration for screener_projects,
screener_country_results, screener_site_results tables.

---

## BUILD ORDER FOR CLAUDE CODE

1. Create directory structure: app/services/screener/ and app/services/screener/data_sources/
2. Create base.py with all dataclasses
3. Create ctgov_source.py (primary data source — most critical)
4. Create protocol_analyzer.py (wraps existing extractor)
5. Create country_feasibility.py (uses ctgov_source)
6. Create site_intelligence.py (uses ctgov_source + openFDA + pubmed)
7. Create scoring_engine.py (combines country + site scores)
8. Create app/routes/screener.py (API endpoints)
9. Create app/schemas/screener.py (Pydantic models)
10. Add DB models and migration
11. Add to main.py
12. Create frontend/app/screener/page.tsx
13. Test end-to-end

Start with steps 1-5, test that country ranking works, then continue.
