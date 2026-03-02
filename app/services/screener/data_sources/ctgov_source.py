"""
ClinicalTrials.gov Data Source for SiteSync Screener.

Primary data source for trial history, sites, investigators, and country-level analytics.
Uses ClinicalTrials.gov API v2: https://clinicaltrials.gov/api/v2/studies

Rate limit: ~3 requests/second (includes 0.35s delay between calls)
"""

import asyncio
import logging
import hashlib
import re
from typing import List, Dict, Optional, Set
from collections import Counter, defaultdict
from datetime import datetime

import httpx

from app.services.screener.data_sources.base import (
    DataSource,
    TrialRecord,
    InvestigatorRecord,
    SiteRecord,
    CountryRecord,
    get_country_code,
)

logger = logging.getLogger(__name__)


def normalize_indication(indication: str) -> List[str]:
    """
    Normalize indication string for flexible matching against ClinicalTrials.gov conditions.

    Problem: Protocol extractions give specific strings like "Active ulcerative colitis (UC)"
    but CT.gov uses "Colitis, Ulcerative" or "Ulcerative Colitis".

    Solution: Return multiple search variants for flexible matching.

    Returns:
        List of normalized search terms (lowercase)
    """
    if not indication:
        return []

    text = indication.lower().strip()
    variants = set()

    # Original (lowercase)
    variants.add(text)

    # Remove parenthetical abbreviations: "ulcerative colitis (UC)" → "ulcerative colitis"
    text_no_parens = re.sub(r'\s*\([^)]*\)\s*', ' ', text).strip()
    if text_no_parens:
        variants.add(text_no_parens)

    # Remove common modifiers
    modifiers = [
        'active', 'moderate', 'severe', 'mild', 'chronic', 'acute',
        'moderate-to-severe', 'moderate to severe', 'advanced', 'metastatic',
        'refractory', 'relapsed', 'untreated', 'previously treated',
        'newly diagnosed', 'recurrent', 'progressive', 'stable',
    ]
    text_no_mods = text_no_parens
    for mod in modifiers:
        text_no_mods = re.sub(rf'\b{mod}\b', '', text_no_mods, flags=re.IGNORECASE)
    text_no_mods = ' '.join(text_no_mods.split()).strip()  # Normalize whitespace
    if text_no_mods:
        variants.add(text_no_mods)

    # Handle common disease name inversions:
    # "ulcerative colitis" ↔ "colitis, ulcerative"
    # "crohn's disease" ↔ "disease, crohn's"
    for variant in list(variants):
        words = variant.split()
        if len(words) == 2:
            # Try "word2, word1" format
            inverted = f"{words[1]}, {words[0]}"
            variants.add(inverted)
            # Also try just the second word (often the core disease)
            variants.add(words[1])
            variants.add(words[0])

    # Extract core disease name (last significant word for multi-word conditions)
    # e.g., "non-alcoholic steatohepatitis" → "steatohepatitis", "nash"
    words = text_no_mods.split()
    if words:
        variants.add(words[-1])  # Last word often the disease
        if len(words) > 1:
            variants.add(words[0])  # First word too

    # Handle common abbreviations bidirectionally
    abbreviation_map = {
        'uc': ['ulcerative colitis', 'colitis, ulcerative'],
        'cd': ["crohn's disease", 'crohn disease', "disease, crohn's"],
        'ibd': ['inflammatory bowel disease'],
        'nash': ['non-alcoholic steatohepatitis', 'nonalcoholic steatohepatitis', 'steatohepatitis'],
        'nafld': ['non-alcoholic fatty liver disease', 'nonalcoholic fatty liver disease', 'fatty liver'],
        'ra': ['rheumatoid arthritis', 'arthritis, rheumatoid'],
        'ms': ['multiple sclerosis', 'sclerosis, multiple'],
        'copd': ['chronic obstructive pulmonary disease', 'pulmonary disease, chronic obstructive'],
        'nsclc': ['non-small cell lung cancer', 'lung cancer'],
        'hcc': ['hepatocellular carcinoma', 'liver cancer'],
        'crc': ['colorectal cancer', 'colon cancer'],
        't2dm': ['type 2 diabetes', 'diabetes mellitus, type 2', 'diabetes'],
        'ckd': ['chronic kidney disease', 'kidney disease'],
        'chf': ['congestive heart failure', 'heart failure'],
        'ad': ["alzheimer's disease", 'alzheimer disease'],
        'pd': ["parkinson's disease", 'parkinson disease'],
    }

    # Check if any abbreviation is in our text
    for abbrev, expansions in abbreviation_map.items():
        if abbrev in text or any(exp in text for exp in expansions):
            variants.add(abbrev)
            variants.update(expansions)

    # Filter out empty strings and very short terms
    variants = {v for v in variants if v and len(v) > 1}

    logger.debug(f"Normalized indication '{indication}' → {len(variants)} variants: {list(variants)[:5]}...")

    return list(variants)


def indication_matches(trial_conditions: List[str], search_variants: List[str]) -> bool:
    """
    Check if any trial condition matches any of our search variants.

    Uses flexible matching: substring match in either direction.
    """
    for cond in trial_conditions:
        cond_lower = cond.lower()
        for variant in search_variants:
            # Match if variant is in condition OR condition is in variant
            if variant in cond_lower or cond_lower in variant:
                return True
            # Also match if they share the core disease word
            variant_words = set(variant.split())
            cond_words = set(cond_lower.replace(',', ' ').split())
            # If they share any significant word (>3 chars), consider it a match
            shared = variant_words & cond_words
            if any(len(w) > 3 for w in shared):
                return True
    return False


class CTGovDataSource(DataSource):
    """
    ClinicalTrials.gov as a Screener data source.

    Implements the DataSource interface to provide:
    - Trial search by condition/phase/status
    - Site aggregation with investigator data
    - Country-level summaries
    - Competing trial identification
    """

    BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
    source_name = "ClinicalTrials.gov"

    # Status classifications
    COMPLETED_STATUSES = ["COMPLETED"]
    ACTIVE_STATUSES = [
        "RECRUITING",
        "ACTIVE_NOT_RECRUITING",
        "ENROLLING_BY_INVITATION",
        "NOT_YET_RECRUITING",
    ]
    TERMINATED_STATUSES = ["TERMINATED", "WITHDRAWN", "SUSPENDED"]
    ALL_STATUSES = COMPLETED_STATUSES + ACTIVE_STATUSES + TERMINATED_STATUSES

    def __init__(self, timeout: float = 30.0, rate_limit_delay: float = 0.35):
        """
        Initialize CT.gov data source.

        Args:
            timeout: HTTP request timeout in seconds
            rate_limit_delay: Delay between API calls to respect rate limits
        """
        self.timeout = timeout
        self.rate_limit_delay = rate_limit_delay

    async def search_trials_by_condition(
        self,
        condition: str,
        phase: Optional[List[str]] = None,
        status: Optional[List[str]] = None,
        country: Optional[str] = None,
        max_results: int = 500
    ) -> List[TrialRecord]:
        """
        Search ClinicalTrials.gov for trials matching condition.

        Args:
            condition: Disease/condition search term (e.g., "NASH", "NAFLD")
            phase: List of phases to filter ["PHASE1", "PHASE2", "PHASE3", "PHASE4"]
            status: List of statuses ["COMPLETED", "RECRUITING", etc.]
            country: Country filter (e.g., "United States")
            max_results: Maximum number of trials to return

        Returns:
            List of TrialRecord objects
        """
        params = {
            "pageSize": min(100, max_results),
            "format": "json",
            "countTotal": "true",
        }

        if condition:
            params["query.cond"] = condition
        if country:
            params["query.locn"] = country
        # CT.gov API v2 uses query.term with AREA syntax for phase filtering
        # Format: AREA[Phase](PHASE1 OR PHASE2)
        if phase:
            phase_terms = " OR ".join(phase)
            params["query.term"] = f"AREA[Phase]({phase_terms})"
        if status:
            params["filter.overallStatus"] = ",".join(status)

        all_trials = []
        next_page_token = None
        pages_fetched = 0
        max_pages = (max_results // 100) + 1

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while pages_fetched < max_pages and len(all_trials) < max_results:
                try:
                    if next_page_token:
                        params["pageToken"] = next_page_token

                    logger.info(
                        f"CT.gov query page {pages_fetched + 1}: "
                        f"condition={condition}, phase={phase}, status={status}"
                    )

                    response = await client.get(self.BASE_URL, params=params)
                    response.raise_for_status()
                    data = response.json()

                    studies = data.get("studies", [])
                    total_count = data.get("totalCount", 0)
                    logger.info(
                        f"Found {len(studies)} studies on page {pages_fetched + 1} "
                        f"(total available: {total_count})"
                    )

                    for study in studies:
                        trial = self._parse_trial(study)
                        if trial:
                            all_trials.append(trial)

                    next_page_token = data.get("nextPageToken")
                    pages_fetched += 1

                    if not next_page_token:
                        break

                    # Rate limit delay
                    await asyncio.sleep(self.rate_limit_delay)

                except httpx.HTTPError as e:
                    logger.error(f"CT.gov API HTTP error: {e}")
                    break
                except Exception as e:
                    logger.error(f"CT.gov API error: {e}")
                    break

        logger.info(f"Total trials retrieved: {len(all_trials)}")
        return all_trials[:max_results]

    async def get_sites_for_condition(
        self,
        condition: str,
        phase: Optional[List[str]] = None,
        country: Optional[str] = None,
        max_results: int = 500
    ) -> List[SiteRecord]:
        """
        Get sites that have participated in trials for this condition.

        Aggregates trial data into unique site records with investigator info.

        Args:
            condition: Disease/condition search term
            phase: List of phases to filter
            country: Country filter
            max_results: Maximum number of sites to return

        Returns:
            List of SiteRecord objects sorted by trial count
        """
        # Get all trials (completed + active) to build site history
        trials = await self.search_trials_by_condition(
            condition=condition,
            phase=phase,
            status=None,  # Get all statuses for complete history
            country=country,
            max_results=1000,  # Get more trials to aggregate sites
        )

        if not trials:
            logger.warning(f"No trials found for condition={condition}")
            return []

        # Aggregate into sites
        sites = self._aggregate_sites(trials, target_condition=condition)

        # Sort by trial count
        sites.sort(key=lambda s: s.trial_count, reverse=True)

        logger.info(f"Aggregated {len(sites)} unique sites from {len(trials)} trials")
        return sites[:max_results]

    async def get_country_summary(
        self,
        condition: str,
        phase: Optional[List[str]] = None
    ) -> List[CountryRecord]:
        """
        Get country-level trial activity summary.

        Aggregates trial and site data by country for feasibility ranking.

        Args:
            condition: Disease/condition search term
            phase: List of phases to filter

        Returns:
            List of CountryRecord objects sorted by total trials
        """
        # Get trials across all statuses
        trials = await self.search_trials_by_condition(
            condition=condition,
            phase=phase,
            status=None,
            country=None,
            max_results=1000,
        )

        if not trials:
            logger.warning(f"No trials found for condition={condition}")
            return []

        # Also get currently recruiting trials for competition analysis
        recruiting_trials = await self.search_trials_by_condition(
            condition=condition,
            phase=phase,
            status=["RECRUITING"],
            country=None,
            max_results=500,
        )

        # Build country summaries
        countries = self._aggregate_countries(
            trials=trials,
            recruiting_trials=recruiting_trials,
            target_condition=condition,
            target_phase=phase,
        )

        # Sort by total trials
        countries.sort(key=lambda c: c.total_trials, reverse=True)

        logger.info(f"Aggregated {len(countries)} countries from {len(trials)} trials")
        return countries

    async def get_competing_trials(
        self,
        condition: str,
        country: Optional[str] = None
    ) -> List[TrialRecord]:
        """
        Get currently recruiting trials competing for same patient pool.

        Args:
            condition: Disease/condition search term
            country: Optional country filter

        Returns:
            List of TrialRecord for recruiting trials
        """
        return await self.search_trials_by_condition(
            condition=condition,
            phase=None,
            status=["RECRUITING"],
            country=country,
            max_results=200,
        )

    def _parse_trial(self, raw_study: Dict) -> Optional[TrialRecord]:
        """Parse raw CT.gov API response into TrialRecord."""
        try:
            protocol = raw_study.get("protocolSection", {})

            # Identification
            id_module = protocol.get("identificationModule", {})
            nct_id = id_module.get("nctId", "")
            title = id_module.get("briefTitle", id_module.get("officialTitle", ""))

            # Status & Phase
            status_module = protocol.get("statusModule", {})
            status = status_module.get("overallStatus", "UNKNOWN")

            design_module = protocol.get("designModule", {})
            phases = design_module.get("phases", [])
            phase = phases[0] if phases else "N/A"
            # Normalize phase format
            phase = phase.replace("PHASE", "Phase ").replace("_", "/")

            # Dates
            start_date = status_module.get("startDateStruct", {}).get("date")
            completion_date = status_module.get("completionDateStruct", {}).get("date")

            # Conditions
            conditions_module = protocol.get("conditionsModule", {})
            conditions = conditions_module.get("conditions", [])
            condition_str = conditions[0] if conditions else ""

            # Sponsors
            sponsor_module = protocol.get("sponsorCollaboratorsModule", {})
            lead_sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")

            # Enrollment
            enrollment_info = design_module.get("enrollmentInfo", {})
            enrollment = enrollment_info.get("count")

            # Interventions
            interventions_module = protocol.get("armsInterventionsModule", {})
            interventions = interventions_module.get("interventions", [])
            intervention_names = [i.get("name", "") for i in interventions[:3]]
            intervention_str = ", ".join(intervention_names)

            # Locations/Sites
            contacts_module = protocol.get("contactsLocationsModule", {})
            locations = contacts_module.get("locations", [])

            sites = []
            for loc in locations:
                site_info = {
                    "facility": loc.get("facility", "Unknown Facility"),
                    "city": loc.get("city", ""),
                    "state": loc.get("state", ""),
                    "country": loc.get("country", ""),
                    "status": loc.get("status", ""),
                    "investigators": [],
                }

                # Extract investigators from contacts
                for contact in loc.get("contacts", []):
                    role = contact.get("role", "")
                    if role in [
                        "PRINCIPAL_INVESTIGATOR",
                        "SUB_INVESTIGATOR",
                        "STUDY_DIRECTOR",
                        "STUDY_CHAIR",
                    ]:
                        site_info["investigators"].append({
                            "name": contact.get("name", "Unknown"),
                            "role": role,
                        })

                sites.append(site_info)

            return TrialRecord(
                nct_id=nct_id,
                title=title,
                phase=phase,
                status=status,
                condition=condition_str,
                conditions=conditions,
                intervention=intervention_str,
                sponsor=lead_sponsor,
                enrollment=enrollment,
                start_date=start_date,
                completion_date=completion_date,
                country="",  # Set per-site, not per-trial
                sites=sites,
                source=self.source_name,
            )

        except Exception as e:
            logger.error(f"Error parsing trial: {e}")
            return None

    def _calculate_trial_weight(
        self,
        trial: TrialRecord,
        target_phase: Optional[List[str]] = None,
        reference_year: Optional[int] = None,
    ) -> float:
        """
        Calculate a composite weight for a trial based on recency, phase match, and status.

        Weight formula: trial_weight = w_recency × w_phase × w_status

        Args:
            trial: The trial to weight
            target_phase: Target phase(s) for phase matching (e.g., ["PHASE3"])
            reference_year: Year to calculate recency from (defaults to current year)

        Returns:
            Composite weight between 0.0 and 1.0
        """
        if reference_year is None:
            reference_year = datetime.now().year

        # --- Recency weight ---
        # Based on completion_date or start_date
        trial_year = None
        for date_str in [trial.completion_date, trial.start_date]:
            if date_str:
                try:
                    # CT.gov dates are typically "YYYY-MM-DD" or "YYYY-MM" or just "YYYY"
                    year_match = re.match(r"(\d{4})", date_str)
                    if year_match:
                        trial_year = int(year_match.group(1))
                        break
                except (ValueError, AttributeError):
                    pass

        if trial_year:
            years_ago = reference_year - trial_year
            if years_ago <= 3:
                w_recency = 1.0
            elif years_ago <= 5:
                w_recency = 0.8
            elif years_ago <= 10:
                w_recency = 0.5
            else:
                w_recency = 0.2
        else:
            # No date available - assume moderate recency
            w_recency = 0.6

        # --- Phase match weight ---
        # Map phases to numeric values for distance calculation
        phase_order = {
            "PHASE1": 1, "PHASE 1": 1, "Phase 1": 1,
            "PHASE1_PHASE2": 1.5, "PHASE 1/2": 1.5, "Phase 1/Phase 2": 1.5,
            "PHASE2": 2, "PHASE 2": 2, "Phase 2": 2,
            "PHASE2_PHASE3": 2.5, "PHASE 2/3": 2.5, "Phase 2/Phase 3": 2.5,
            "PHASE3": 3, "PHASE 3": 3, "Phase 3": 3,
            "PHASE4": 4, "PHASE 4": 4, "Phase 4": 4,
        }

        trial_phase_num = None
        trial_phase_normalized = trial.phase.upper().replace(" ", "").replace("/", "_")
        for key, val in phase_order.items():
            key_normalized = key.upper().replace(" ", "").replace("/", "_")
            if key_normalized in trial_phase_normalized or trial_phase_normalized in key_normalized:
                trial_phase_num = val
                break

        target_phase_num = None
        if target_phase:
            for tp in target_phase:
                for key, val in phase_order.items():
                    key_normalized = key.upper().replace(" ", "").replace("/", "_")
                    tp_normalized = tp.upper().replace(" ", "").replace("/", "_")
                    if key_normalized in tp_normalized or tp_normalized in key_normalized:
                        target_phase_num = val
                        break
                if target_phase_num:
                    break

        if trial_phase_num and target_phase_num:
            phase_distance = abs(trial_phase_num - target_phase_num)
            if phase_distance == 0:
                w_phase = 1.0   # Exact match
            elif phase_distance <= 1:
                w_phase = 0.7   # Adjacent phase
            elif phase_distance <= 2:
                w_phase = 0.4   # Two phases away
            else:
                w_phase = 0.2   # Distant phase
        else:
            # No phase info or no target - neutral weight
            w_phase = 0.6

        # --- Status weight ---
        status_weights = {
            "COMPLETED": 1.0,
            "RECRUITING": 0.8,
            "ENROLLING_BY_INVITATION": 0.7,
            "ACTIVE_NOT_RECRUITING": 0.5,
            "NOT_YET_RECRUITING": 0.6,
            "SUSPENDED": 0.3,
            "TERMINATED": 0.2,
            "WITHDRAWN": 0.1,
            "UNKNOWN": 0.4,
        }
        w_status = status_weights.get(trial.status.upper(), 0.4)

        # --- Composite weight ---
        composite = w_recency * w_phase * w_status

        return composite

    def _aggregate_sites(
        self,
        trials: List[TrialRecord],
        target_condition: Optional[str] = None
    ) -> List[SiteRecord]:
        """Aggregate trials into unique site records."""
        sites_map: Dict[str, Dict] = {}

        for trial in trials:
            for site in trial.sites:
                facility = site.get("facility", "Unknown")
                city = site.get("city", "")
                state = site.get("state", "")
                country = site.get("country", "")

                # Create unique key for site
                site_key = f"{facility}|{city}|{state}|{country}".lower()
                site_id = hashlib.md5(site_key.encode()).hexdigest()[:12]

                if site_key not in sites_map:
                    sites_map[site_key] = {
                        "site_id": site_id,
                        "site_name": facility,
                        "city": city,
                        "state": state,
                        "country": country,
                        "country_code": get_country_code(country),
                        "investigators": {},
                        "trials": [],
                        "phases": Counter(),
                        "conditions": Counter(),
                        "statuses": Counter(),
                        "enrollments": [],
                    }

                site_data = sites_map[site_key]

                # Add trial info (include conditions for indication matching)
                site_data["trials"].append({
                    "nct_id": trial.nct_id,
                    "title": trial.title,
                    "phase": trial.phase,
                    "status": trial.status,
                    "enrollment": trial.enrollment,
                    "conditions": trial.conditions,  # Store conditions per trial
                })

                site_data["phases"][trial.phase] += 1
                site_data["statuses"][trial.status] += 1

                if trial.enrollment:
                    site_data["enrollments"].append(trial.enrollment)

                for condition in trial.conditions:
                    site_data["conditions"][condition] += 1

                # Track investigators
                for inv in site.get("investigators", []):
                    inv_name = inv.get("name", "Unknown")
                    inv_role = inv.get("role", "UNKNOWN")

                    if inv_name not in site_data["investigators"]:
                        site_data["investigators"][inv_name] = {
                            "name": inv_name,
                            "roles": Counter(),
                            "trial_count": 0,
                        }

                    site_data["investigators"][inv_name]["roles"][inv_role] += 1
                    site_data["investigators"][inv_name]["trial_count"] += 1

        # Convert to SiteRecord objects
        site_records = []

        for site_key, data in sites_map.items():
            # Count statuses
            completed = sum(
                data["statuses"].get(s, 0) for s in self.COMPLETED_STATUSES
            )
            recruiting = sum(
                data["statuses"].get(s, 0) for s in self.ACTIVE_STATUSES
            )
            terminated = sum(
                data["statuses"].get(s, 0) for s in self.TERMINATED_STATUSES
            )

            # Calculate average enrollment
            avg_enrollment = None
            if data["enrollments"]:
                avg_enrollment = sum(data["enrollments"]) / len(data["enrollments"])

            # Get indication match count: count unique TRIALS with at least one matching condition
            # (Previously summed all matching condition occurrences, which overcounted when
            # trials had multiple synonymous conditions like ["NASH", "NAFLD"])
            indication_count = 0
            if target_condition:
                indication_variants = normalize_indication(target_condition)
                for trial_info in data["trials"]:
                    trial_conditions = trial_info.get("conditions", [])
                    # Check if ANY condition in this trial matches the indication
                    if indication_matches(trial_conditions, indication_variants):
                        indication_count += 1

            # Build investigator records
            investigators = []
            for inv_name, inv_data in data["investigators"].items():
                primary_role = (
                    max(inv_data["roles"], key=inv_data["roles"].get)
                    if inv_data["roles"]
                    else "UNKNOWN"
                )
                investigators.append(InvestigatorRecord(
                    name=inv_name,
                    site_name=data["site_name"],
                    city=data["city"],
                    state=data["state"],
                    country=data["country"],
                    trial_count=inv_data["trial_count"],
                    source=self.source_name,
                ))

            # Sort investigators by trial count
            investigators.sort(key=lambda x: x.trial_count, reverse=True)

            # Get last active date
            last_active = None
            for trial_info in data["trials"]:
                # Would need to parse dates for proper sorting
                pass

            # Defensive cap: indication_trial_count can never exceed trial_count
            trial_count = len(data["trials"])
            indication_trial_count = min(indication_count, trial_count)

            site_records.append(SiteRecord(
                site_id=data["site_id"],
                site_name=data["site_name"],
                city=data["city"],
                state=data["state"],
                country=data["country"],
                country_code=data["country_code"],
                investigators=investigators[:10],  # Top 10 investigators
                trial_count=trial_count,
                indication_trial_count=indication_trial_count,
                completed_trials=completed,
                terminated_trials=terminated,
                recruiting_trials=recruiting,
                avg_enrollment=avg_enrollment,
                therapeutic_areas=list(data["conditions"].keys())[:10],
                source=self.source_name,
            ))

        return site_records

    def _aggregate_countries(
        self,
        trials: List[TrialRecord],
        recruiting_trials: List[TrialRecord],
        target_condition: Optional[str] = None,
        target_phase: Optional[List[str]] = None,
    ) -> List[CountryRecord]:
        """Aggregate trial data into country-level summaries."""
        countries_map: Dict[str, Dict] = defaultdict(lambda: {
            "country_name": "",
            "sites": set(),
            "investigators": set(),
            "trials": set(),
            "indication_trials": set(),
            "phase_match_trials": set(),
            "completed_trials": set(),
            "terminated_trials": set(),
            "recruiting_nct_ids": set(),
            "enrollments": [],
            "competing_trial_details": [],  # [{nct_id, enrollment, sites_in_country, sites_total}]
            "trial_weights": {},  # {nct_id: weight} for weighted experience scoring
        })

        # Build nct_id -> TrialRecord lookup for weight calculation
        trial_lookup: Dict[str, TrialRecord] = {t.nct_id: t for t in trials if t.nct_id}

        # Pre-compute indication search variants for flexible matching
        indication_variants = normalize_indication(target_condition) if target_condition else []
        if indication_variants:
            logger.info(
                f"ClinicalTrials.gov indication matching: '{target_condition}' "
                f"→ {len(indication_variants)} variants: {indication_variants[:5]}"
            )

        # Process all trials
        indication_match_count = 0
        for trial in trials:
            for site in trial.sites:
                country = site.get("country", "")
                if not country:
                    continue

                country_lower = country.lower()
                data = countries_map[country_lower]
                data["country_name"] = country

                # Track unique entities
                data["trials"].add(trial.nct_id)

                site_key = f"{site.get('facility', '')}|{site.get('city', '')}".lower()
                data["sites"].add(site_key)

                for inv in site.get("investigators", []):
                    data["investigators"].add(inv.get("name", ""))

                # Track indication matches with flexible matching
                if indication_variants:
                    if indication_matches(trial.conditions, indication_variants):
                        if trial.nct_id not in data["indication_trials"]:
                            indication_match_count += 1
                            # Calculate and store trial weight for this indication trial
                            weight = self._calculate_trial_weight(trial, target_phase)
                            data["trial_weights"][trial.nct_id] = weight
                        data["indication_trials"].add(trial.nct_id)

                # Track phase matches
                if target_phase:
                    trial_phase = trial.phase.upper().replace(" ", "").replace("/", "_")
                    for p in target_phase:
                        if p.upper() in trial_phase or trial_phase in p.upper():
                            data["phase_match_trials"].add(trial.nct_id)
                            break

                # Track status
                if trial.status in self.COMPLETED_STATUSES:
                    data["completed_trials"].add(trial.nct_id)
                elif trial.status in self.TERMINATED_STATUSES:
                    data["terminated_trials"].add(trial.nct_id)

                if trial.enrollment:
                    data["enrollments"].append(trial.enrollment)

        # Process recruiting trials for competition count
        # First, build per-trial site distribution data
        trial_site_distribution: Dict[str, Dict[str, int]] = {}  # nct_id -> {country_lower: site_count}
        trial_metadata: Dict[str, Dict] = {}  # nct_id -> {enrollment, total_sites}

        for trial in recruiting_trials:
            nct_id = trial.nct_id
            if nct_id not in trial_site_distribution:
                trial_site_distribution[nct_id] = defaultdict(int)
                trial_metadata[nct_id] = {
                    "enrollment": trial.enrollment,
                    "total_sites": len(trial.sites) if trial.sites else 1,
                }

            for site in trial.sites:
                country = site.get("country", "")
                if not country:
                    continue
                country_lower = country.lower()
                trial_site_distribution[nct_id][country_lower] += 1

                if country_lower in countries_map:
                    countries_map[country_lower]["recruiting_nct_ids"].add(trial.nct_id)

        # Now add competing trial details to each country
        for nct_id, country_sites in trial_site_distribution.items():
            metadata = trial_metadata.get(nct_id, {})
            total_sites = max(metadata.get("total_sites", 1), 1)
            enrollment = metadata.get("enrollment")

            for country_lower, sites_in_country in country_sites.items():
                if country_lower in countries_map:
                    # Check if this trial is already in competing_trial_details
                    existing_ncts = {d["nct_id"] for d in countries_map[country_lower]["competing_trial_details"]}
                    if nct_id not in existing_ncts:
                        countries_map[country_lower]["competing_trial_details"].append({
                            "nct_id": nct_id,
                            "enrollment": enrollment,
                            "sites_in_country": sites_in_country,
                            "sites_total": total_sites,
                        })

        # Convert to CountryRecord objects
        country_records = []

        for country_lower, data in countries_map.items():
            if not data["country_name"]:
                continue

            avg_enrollment = None
            if data["enrollments"]:
                avg_enrollment = sum(data["enrollments"]) / len(data["enrollments"])

            # Calculate average enrollment for competing trials
            competing_details = data["competing_trial_details"]
            avg_competing_enrollment = None
            if competing_details:
                enrollments = [d["enrollment"] for d in competing_details if d.get("enrollment")]
                if enrollments:
                    avg_competing_enrollment = sum(enrollments) / len(enrollments)

            # Calculate weighted experience from trial weights
            trial_weights = data["trial_weights"]
            weighted_experience = sum(trial_weights.values()) if trial_weights else 0.0
            experience_weights_used = bool(trial_weights)
            experience_trial_count = len(data["indication_trials"])

            country_records.append(CountryRecord(
                country_name=data["country_name"],
                country_code=get_country_code(data["country_name"]),
                site_count=len(data["sites"]),
                investigator_count=len(data["investigators"]),
                total_trials=len(data["trials"]),
                indication_trials=len(data["indication_trials"]),
                phase_match_trials=len(data["phase_match_trials"]),
                actively_recruiting=len(data["recruiting_nct_ids"]),
                completed_trials=len(data["completed_trials"]),
                terminated_trials=len(data["terminated_trials"]),
                avg_enrollment_per_site=avg_enrollment,
                competing_trial_details=competing_details,
                avg_competing_enrollment=avg_competing_enrollment,
                weighted_experience=weighted_experience,
                experience_weights_used=experience_weights_used,
                experience_trial_count=experience_trial_count,
                source=self.source_name,
            ))

        # Deduplicate by country_code - merge records with same code
        deduplicated = {}
        for record in country_records:
            code = record.country_code.upper() if record.country_code else "UNKNOWN"
            if code in deduplicated:
                # Merge with existing record
                existing = deduplicated[code]
                existing.site_count += record.site_count
                existing.investigator_count += record.investigator_count
                existing.total_trials += record.total_trials
                existing.indication_trials += record.indication_trials
                existing.phase_match_trials += record.phase_match_trials
                existing.actively_recruiting += record.actively_recruiting
                existing.completed_trials += record.completed_trials
                existing.terminated_trials += record.terminated_trials
                # Merge weighted experience
                existing.weighted_experience += record.weighted_experience
                existing.experience_trial_count += record.experience_trial_count
                existing.experience_weights_used = existing.experience_weights_used or record.experience_weights_used
                # Merge competing_trial_details (avoid duplicates by nct_id)
                existing_ncts = {d["nct_id"] for d in existing.competing_trial_details}
                for detail in record.competing_trial_details:
                    if detail["nct_id"] not in existing_ncts:
                        existing.competing_trial_details.append(detail)
                        existing_ncts.add(detail["nct_id"])
                # Recalculate avg_competing_enrollment after merge
                if existing.competing_trial_details:
                    enrollments = [d["enrollment"] for d in existing.competing_trial_details if d.get("enrollment")]
                    if enrollments:
                        existing.avg_competing_enrollment = sum(enrollments) / len(enrollments)
                # Keep the longer/more complete country name
                if len(record.country_name) > len(existing.country_name):
                    existing.country_name = record.country_name
            else:
                deduplicated[code] = record

        # Log indication trial counts for top countries
        final_records = list(deduplicated.values())
        if indication_variants and final_records:
            top_5 = sorted(final_records, key=lambda c: c.indication_trials, reverse=True)[:5]
            logger.info(
                f"Indication trial counts (top 5): "
                f"{[(c.country_name, c.indication_trials, c.total_trials) for c in top_5]}"
            )

        return final_records
