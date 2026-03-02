"""
Site Intelligence Engine for SiteSync Screener.

Takes ProtocolCriteria + country_code and returns ranked list of SiteRecords
with detailed scoring for each site within the selected country.

Scoring Components:
- experience_score (35%): Trial count, indication match, phase match, recency
- pi_strength_score (20%): Publications, trial experience, specialization
- capacity_score (20%): Historical enrollment sizes, current workload
- compliance_score (15%): FDA record clean, no debarments
- protocol_match_score (10%): AI gap analysis vs protocol requirements
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from app.services.screener.data_sources.base import (
    ProtocolCriteria,
    SiteRecord,
    InvestigatorRecord,
)
from app.services.screener.data_sources.ctgov_source import CTGovDataSource

logger = logging.getLogger(__name__)


@dataclass
class SiteScoringWeights:
    """Configurable weights for site scoring."""
    experience: float = 0.35
    pi_strength: float = 0.20
    capacity: float = 0.20
    compliance: float = 0.15
    protocol_match: float = 0.10

    def validate(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.experience +
            self.pi_strength +
            self.capacity +
            self.compliance +
            self.protocol_match
        )
        return abs(total - 1.0) < 0.01

    def normalized(self) -> "SiteScoringWeights":
        """Return normalized weights that sum to 1.0."""
        total = (
            self.experience +
            self.pi_strength +
            self.capacity +
            self.compliance +
            self.protocol_match
        )
        if total == 0:
            total = 1.0  # Avoid division by zero
        return SiteScoringWeights(
            experience=self.experience / total,
            pi_strength=self.pi_strength / total,
            capacity=self.capacity / total,
            compliance=self.compliance / total,
            protocol_match=self.protocol_match / total,
        )


@dataclass
class ScoredSite:
    """Site with all scoring components calculated."""
    site: SiteRecord

    # Individual scores (0-100)
    experience_score: float = 0.0
    pi_strength_score: float = 0.0
    capacity_score: float = 0.0
    compliance_score: float = 0.0
    protocol_match_score: float = 0.0

    # Composite
    site_composite_score: float = 0.0

    # Additional analytics
    completion_rate: float = 0.0
    competing_trial_count: int = 0

    # Flags and analysis
    red_flags: List[str] = field(default_factory=list)
    yellow_flags: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    gap_analysis: Optional[str] = None

    # Enrichment status
    fda_enriched: bool = False
    pubmed_enriched: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "site": self.site.to_dict(),
            "experience_score": self.experience_score,
            "pi_strength_score": self.pi_strength_score,
            "capacity_score": self.capacity_score,
            "compliance_score": self.compliance_score,
            "protocol_match_score": self.protocol_match_score,
            "site_composite_score": self.site_composite_score,
            "completion_rate": self.completion_rate,
            "competing_trial_count": self.competing_trial_count,
            "red_flags": self.red_flags,
            "yellow_flags": self.yellow_flags,
            "strengths": self.strengths,
            "gap_analysis": self.gap_analysis,
            "fda_enriched": self.fda_enriched,
            "pubmed_enriched": self.pubmed_enriched,
        }


class SiteIntelligenceEngine:
    """
    Ranks sites within a country by feasibility for a given protocol.

    Uses ClinicalTrials.gov data to score sites on:
    - Historical trial experience in the indication
    - PI quality and experience
    - Site capacity and current workload
    - Compliance record (FDA - placeholder for now)
    - Protocol-specific requirements match
    """

    def __init__(
        self,
        weights: Optional[SiteScoringWeights] = None,
        openai_client: Optional[Any] = None
    ):
        """
        Initialize the site intelligence engine.

        Args:
            weights: Custom scoring weights
            openai_client: OpenAI client for AI-enhanced analysis
        """
        self.weights = weights or SiteScoringWeights()
        self.ctgov = CTGovDataSource()

        # Try to initialize OpenAI for gap analysis
        self.openai = openai_client
        if self.openai is None:
            try:
                from app.services.openai_client import get_openai_client
                self.openai = get_openai_client()
            except Exception as e:
                logger.warning(f"OpenAI not available for gap analysis: {e}")
                self.openai = None

    async def rank_sites(
        self,
        criteria: ProtocolCriteria,
        country_code: str,
        country_name: Optional[str] = None,
        min_trials: int = 1,
        include_gap_analysis: bool = False
    ) -> List[ScoredSite]:
        """
        Rank sites within a country by feasibility for the given protocol.

        Args:
            criteria: Protocol requirements
            country_code: ISO country code to filter sites
            country_name: Full country name (for CT.gov query)
            min_trials: Minimum trials required to include a site
            include_gap_analysis: Whether to include AI gap analysis

        Returns:
            List of ScoredSite objects sorted by composite score
        """
        logger.info(
            f"Ranking sites in {country_code} for indication='{criteria.indication}'"
        )

        # Get phase filter for API
        phase_filter = criteria.get_phase_filter()

        # Step 1: Get sites from ClinicalTrials.gov
        sites = await self.ctgov.get_sites_for_condition(
            condition=criteria.indication,
            phase=phase_filter,
            country=country_name,
            max_results=500,
        )

        if not sites:
            logger.warning(f"No sites found in {country_code} for {criteria.indication}")
            return []

        # Filter by country code if provided (in case country_name query is broad)
        if country_code:
            sites = [
                s for s in sites
                if s.country_code and s.country_code.upper() == country_code.upper()
            ]

        logger.info(f"Retrieved {len(sites)} sites from CT.gov")

        # Filter by minimum trials
        sites = [s for s in sites if s.trial_count >= min_trials]
        logger.info(f"{len(sites)} sites have >= {min_trials} trials")

        if not sites:
            return []

        # Step 2: Get competing trials for workload analysis
        competing_trials = await self.ctgov.get_competing_trials(
            condition=criteria.indication,
            country=country_name,
        )

        # Build map of site -> competing trial count
        competing_map = self._build_competing_map(competing_trials)

        # Step 3: Calculate scores for each site
        scored_sites = self._calculate_scores(
            sites=sites,
            criteria=criteria,
            competing_map=competing_map,
        )

        # Step 4: Add gap analysis for top sites (if enabled)
        if include_gap_analysis and self.openai:
            top_sites = scored_sites[:15]
            top_sites = await self._add_gap_analysis(top_sites, criteria)
            scored_sites = top_sites + scored_sites[15:]

        # Step 5: Sort by composite score
        scored_sites.sort(key=lambda s: s.site_composite_score, reverse=True)

        logger.info(
            f"Site ranking complete. Top 3: "
            f"{[f'{s.site.site_name[:30]}({s.site_composite_score:.0f})' for s in scored_sites[:3]]}"
        )

        return scored_sites

    def _build_competing_map(self, competing_trials: List) -> Dict[str, int]:
        """Build a map of site_key -> number of competing trials."""
        competing_map: Dict[str, int] = {}

        for trial in competing_trials:
            for site in trial.sites:
                facility = site.get("facility", "")
                city = site.get("city", "")
                site_key = f"{facility}|{city}".lower()

                if site_key not in competing_map:
                    competing_map[site_key] = 0
                competing_map[site_key] += 1

        return competing_map

    def _calculate_scores(
        self,
        sites: List[SiteRecord],
        criteria: ProtocolCriteria,
        competing_map: Dict[str, int],
    ) -> List[ScoredSite]:
        """Calculate scoring components for each site."""
        if not sites:
            return []

        # Find max values for normalization
        max_trials = max(s.trial_count for s in sites) or 1
        max_indication_trials = max(s.indication_trial_count for s in sites) or 1
        max_investigators = max(len(s.investigators) for s in sites) or 1
        max_enrollment = max(s.avg_enrollment or 0 for s in sites) or 1
        max_competing = max(competing_map.values()) if competing_map else 1

        scored_sites = []

        for site in sites:
            scored = ScoredSite(site=site)

            # Calculate completion rate
            total_finished = site.completed_trials + site.terminated_trials
            if total_finished > 0:
                scored.completion_rate = site.completed_trials / total_finished
            else:
                scored.completion_rate = 0.5  # Unknown, assume moderate

            # Get competing trial count
            site_key = f"{site.site_name}|{site.city}".lower()
            scored.competing_trial_count = competing_map.get(site_key, 0)

            # Experience Score (35%)
            # Based on: trial count, indication match, phase match, completion rate
            trial_factor = (site.trial_count / max_trials) * 30
            indication_factor = (site.indication_trial_count / max_indication_trials) * 40
            completion_factor = scored.completion_rate * 30
            scored.experience_score = min(100, trial_factor + indication_factor + completion_factor)

            # PI Strength Score (20%)
            # Based on: number of investigators, trial count per investigator
            # (Full scoring would use PubMed publications - placeholder for now)
            investigator_factor = (len(site.investigators) / max_investigators) * 50
            if site.investigators:
                avg_pi_trials = sum(i.trial_count for i in site.investigators) / len(site.investigators)
                pi_experience_factor = min(50, avg_pi_trials * 5)
            else:
                pi_experience_factor = 25  # Unknown
            scored.pi_strength_score = min(100, investigator_factor + pi_experience_factor)

            # Capacity Score (20%)
            # Based on: historical enrollment, current workload (inverse of competing)
            enrollment_factor = ((site.avg_enrollment or 0) / max_enrollment) * 50
            if max_competing > 0:
                workload_factor = (1 - (scored.competing_trial_count / max_competing)) * 50
            else:
                workload_factor = 50
            scored.capacity_score = min(100, enrollment_factor + workload_factor)

            # Compliance Score (15%)
            # Placeholder: assume clean unless FDA data says otherwise
            # Will be updated by enrich_with_fda()
            scored.compliance_score = 85  # Default good

            # Protocol Match Score (10%)
            # Placeholder: basic therapeutic area match
            # Full scoring would use AI gap analysis
            if criteria.therapeutic_area:
                area_match = any(
                    criteria.therapeutic_area.lower() in ta.lower()
                    for ta in site.therapeutic_areas
                )
                scored.protocol_match_score = 80 if area_match else 60
            else:
                scored.protocol_match_score = 70  # Unknown

            # Calculate composite score
            scored.site_composite_score = self._compute_composite(scored)

            # Identify flags and strengths
            self._identify_flags(scored, criteria)

            scored_sites.append(scored)

        return scored_sites

    def _compute_composite(self, scored: ScoredSite) -> float:
        """Compute weighted composite score for a site."""
        return (
            scored.experience_score * self.weights.experience +
            scored.pi_strength_score * self.weights.pi_strength +
            scored.capacity_score * self.weights.capacity +
            scored.compliance_score * self.weights.compliance +
            scored.protocol_match_score * self.weights.protocol_match
        )

    def _identify_flags(self, scored: ScoredSite, criteria: ProtocolCriteria) -> None:
        """Identify red flags, yellow flags, and strengths for a site."""
        site = scored.site

        # Red Flags
        if scored.completion_rate < 0.5:
            scored.red_flags.append(
                f"Low completion rate: {scored.completion_rate:.0%}"
            )

        if site.terminated_trials > site.completed_trials:
            scored.red_flags.append(
                f"More terminated ({site.terminated_trials}) than completed ({site.completed_trials}) trials"
            )

        # Yellow Flags
        if scored.competing_trial_count >= 3:
            scored.yellow_flags.append(
                f"High competing workload: {scored.competing_trial_count} recruiting trials"
            )

        if site.indication_trial_count == 0:
            scored.yellow_flags.append(
                f"No trials in exact indication ({criteria.indication})"
            )

        if len(site.investigators) == 0:
            scored.yellow_flags.append("No investigators identified in public records")

        # Strengths
        if site.indication_trial_count >= 5:
            scored.strengths.append(
                f"Strong indication experience: {site.indication_trial_count} trials"
            )

        if scored.completion_rate >= 0.9:
            scored.strengths.append(
                f"Excellent completion rate: {scored.completion_rate:.0%}"
            )

        if site.trial_count >= 20:
            scored.strengths.append(
                f"Highly experienced site: {site.trial_count} total trials"
            )

        if len(site.investigators) >= 3:
            scored.strengths.append(
                f"Strong investigator team: {len(site.investigators)} identified"
            )

    async def _add_gap_analysis(
        self,
        scored_sites: List[ScoredSite],
        criteria: ProtocolCriteria
    ) -> List[ScoredSite]:
        """
        Add AI-generated gap analysis for top sites.

        Analyzes how well each site matches THIS SPECIFIC protocol's requirements,
        including procedures, equipment, eligibility criteria complexity, and
        specialized capabilities (infusion, endoscopy, biopsy, storage).
        """
        if not self.openai or not scored_sites:
            return scored_sites

        # Build site summaries for batch analysis
        site_summaries = []
        for scored in scored_sites[:10]:
            site = scored.site
            summary = {
                "name": site.site_name,
                "city": site.city,
                "trials": site.trial_count,
                "indication_trials": site.indication_trial_count,
                "completion_rate": f"{scored.completion_rate:.0%}",
                "competing": scored.competing_trial_count,
                "therapeutic_areas": site.therapeutic_areas[:5],
                "pi": site.investigators[0].get("name", "Unknown") if site.investigators else "Unknown",
            }
            site_summaries.append(summary)

        # Build comprehensive protocol context (safe access patterns)
        indication = criteria.indication or "Unknown indication"
        indication_detail = criteria.indication_detail or indication
        phase = criteria.phase or "Not specified"
        enrollment_target = criteria.enrollment_target
        patients_per_site = criteria.patients_per_site

        # Capability requirements
        capability_flags = []
        if criteria.requires_infusion:
            capability_flags.append("IV infusion capability (REQUIRED)")
        if criteria.requires_endoscopy:
            capability_flags.append("Endoscopy (REQUIRED)")
        if criteria.requires_biopsy:
            capability_flags.append("Biopsy procedures (REQUIRED)")
        if criteria.ecg_required:
            capability_flags.append("ECG (REQUIRED)")
        if criteria.requires_imaging:
            for img in criteria.requires_imaging[:3]:
                capability_flags.append(f"{img} imaging (REQUIRED)")

        # Truncate lists for prompt efficiency
        procedures = criteria.procedures[:15] if criteria.procedures else []
        equipment = criteria.required_equipment[:8] if criteria.required_equipment else []
        staff = criteria.required_staff[:5] if criteria.required_staff else []
        storage = criteria.storage_requirements[:3] if criteria.storage_requirements else []
        sample_proc = criteria.sample_processing[:3] if criteria.sample_processing else []
        lab_reqs = criteria.lab_requirements[:5] if criteria.lab_requirements else []

        # Eligibility complexity
        inclusion = criteria.inclusion_criteria[:8] if criteria.inclusion_criteria else []
        exclusion = criteria.exclusion_criteria[:8] if criteria.exclusion_criteria else []
        num_exclusion = len(criteria.exclusion_criteria) if criteria.exclusion_criteria else 0
        eligibility_complexity = "very narrow" if num_exclusion > 20 else "narrow" if num_exclusion > 12 else "moderate" if num_exclusion > 6 else "broad"

        # Drug administration
        dose_route = criteria.dose_and_route or "Not specified"
        dosing_freq = criteria.dosing_frequency or "Not specified"
        treatment_duration = criteria.treatment_duration or criteria.total_duration or "Not specified"
        total_visits = criteria.total_visits or criteria.visit_count

        # Endpoints
        primary_endpoint = criteria.primary_endpoint or "Not specified"
        primary_assessment = criteria.primary_assessment or "Standard assessments"

        prompt = f"""Analyze these clinical trial sites for THIS SPECIFIC protocol:

=== PROTOCOL REQUIREMENTS ===
Study: {phase} study in {indication_detail}

Enrollment:
- Target: {enrollment_target or 'Not specified'} patients total
- Per Site: {patients_per_site or 'Not specified'} patients
- Treatment Duration: {treatment_duration}
- Total Visits: {total_visits or 'Not specified'}

Drug Administration:
- Dose/Route: {dose_route}
- Frequency: {dosing_freq}

REQUIRED Capabilities (sites MUST have):
{chr(10).join(f'  • {cap}' for cap in capability_flags) if capability_flags else '  • Standard clinical trial capabilities'}

Required Equipment: {', '.join(equipment) if equipment else 'Standard'}
Required Staff: {', '.join(staff) if staff else 'PI + coordinators'}
Required Procedures: {', '.join(procedures[:10]) if procedures else 'Standard assessments'}

Storage/Lab Requirements:
- Storage: {', '.join(storage) if storage else 'Standard'}
- Sample Processing: {', '.join(sample_proc) if sample_proc else 'Standard'}
- Lab Tests: {', '.join(lab_reqs) if lab_reqs else 'Standard panels'}

Eligibility Complexity: {eligibility_complexity} ({len(inclusion)} inclusion, {num_exclusion} exclusion criteria)
Key Exclusions: {'; '.join(exclusion[:4]) if exclusion else 'Standard exclusions'}

Primary Endpoint: {primary_endpoint}
Assessment Method: {primary_assessment}

=== SITES TO ANALYZE ===
{site_summaries}

=== INSTRUCTIONS ===
For EACH site, provide a 2-3 sentence gap analysis that:
1. Assesses whether their trial history suggests they can perform the REQUIRED procedures
2. Flags any capability gaps based on the protocol requirements above
3. Notes capacity concerns (competing trials vs. enrollment target)
4. Gives an overall fit rating: "Strong fit", "Good fit with gaps", "Concerns", or "Poor fit"

Be SPECIFIC about gaps. Examples:
- "No evidence of endoscopy experience - protocol requires colonoscopy at weeks 0, 12, 24"
- "Only 2 {indication} trials - may struggle with {eligibility_complexity} eligibility criteria"
- "4 competing trials may limit capacity for {patients_per_site or 'target'} patient enrollment"

Return JSON array:
[
  {{"site_name": "Site Name", "gap_analysis": "2-3 sentence analysis with specific gaps and fit rating..."}}
]

Return ONLY valid JSON array."""

        logger.info(f"Site gap analysis prompt length: {len(prompt)} chars")

        try:
            response = self.openai.create_json_completion(
                prompt=prompt,
                system_message=(
                    "You are a clinical trial site selection expert specializing in "
                    "protocol-site matching. Identify specific capability gaps and "
                    "provide actionable assessments based on the protocol requirements."
                ),
                temperature=0.2,
                max_tokens=2500,
            )

            # Handle response format
            if isinstance(response, list):
                ai_data = response
            elif isinstance(response, dict) and "sites" in response:
                ai_data = response["sites"]
            else:
                ai_data = []

            # Map results back
            ai_map = {
                item.get("site_name", "").lower(): item.get("gap_analysis", "")
                for item in ai_data
            }

            for scored in scored_sites:
                analysis = ai_map.get(scored.site.site_name.lower())
                if analysis:
                    scored.gap_analysis = analysis

            logger.info(f"Gap analysis added for {len(ai_map)} sites")

        except Exception as e:
            logger.error(f"Gap analysis failed: {e}")

        return scored_sites

    async def get_site_details(
        self,
        site_id: str,
        criteria: ProtocolCriteria,
        country_name: Optional[str] = None
    ) -> Optional[ScoredSite]:
        """
        Get detailed information for a specific site.

        Args:
            site_id: Site identifier
            criteria: Protocol criteria for context
            country_name: Country name for search

        Returns:
            ScoredSite with full details
        """
        # Get all sites and find the matching one
        sites = await self.ctgov.get_sites_for_condition(
            condition=criteria.indication,
            phase=criteria.get_phase_filter(),
            country=country_name,
            max_results=500,
        )

        for site in sites:
            if site.site_id == site_id:
                # Score this single site
                scored_list = self._calculate_scores(
                    sites=[site],
                    criteria=criteria,
                    competing_map={},
                )
                if scored_list:
                    # Add gap analysis
                    if self.openai:
                        scored_list = await self._add_gap_analysis(scored_list, criteria)
                    return scored_list[0]

        return None

    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """Update scoring weights."""
        if "experience" in new_weights:
            self.weights.experience = new_weights["experience"]
        if "pi_strength" in new_weights:
            self.weights.pi_strength = new_weights["pi_strength"]
        if "capacity" in new_weights:
            self.weights.capacity = new_weights["capacity"]
        if "compliance" in new_weights:
            self.weights.compliance = new_weights["compliance"]
        if "protocol_match" in new_weights:
            self.weights.protocol_match = new_weights["protocol_match"]

        if not self.weights.validate():
            logger.warning("Weights do not sum to 1.0, scores may be skewed")

    # =========================================================================
    # Placeholder enrichment methods - to be implemented with real data sources
    # =========================================================================

    async def enrich_with_fda(self, scored_site: ScoredSite) -> ScoredSite:
        """
        Enrich site with FDA inspection data.

        PLACEHOLDER: Returns site unchanged.
        Future implementation will query openFDA API for:
        - Clinical investigator inspections
        - 483 observations
        - Warning letters
        - Debarment status

        Args:
            scored_site: Site to enrich

        Returns:
            ScoredSite with FDA data (unchanged for now)
        """
        # TODO: Implement openFDA integration
        # API: https://api.fda.gov/other/inspections.json
        # Search by investigator name
        # Check debarment list

        logger.debug(f"FDA enrichment placeholder for {scored_site.site.site_name}")
        scored_site.fda_enriched = False  # Mark as not enriched
        return scored_site

    async def enrich_with_pubmed(self, scored_site: ScoredSite) -> ScoredSite:
        """
        Enrich site with PI publication data from PubMed.

        PLACEHOLDER: Returns site unchanged.
        Future implementation will query NCBI E-utilities for:
        - Publication count in therapeutic area
        - Recent publications
        - Co-author network

        Args:
            scored_site: Site to enrich

        Returns:
            ScoredSite with publication data (unchanged for now)
        """
        # TODO: Implement PubMed integration
        # API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
        # Search: "{pi_name}[Author] AND {therapeutic_area}[Title/Abstract]"
        # Get publication count and recent papers

        logger.debug(f"PubMed enrichment placeholder for {scored_site.site.site_name}")
        scored_site.pubmed_enriched = False  # Mark as not enriched
        return scored_site

    async def enrich_all(self, scored_sites: List[ScoredSite]) -> List[ScoredSite]:
        """
        Enrich multiple sites with FDA and PubMed data.

        PLACEHOLDER: Returns sites unchanged.

        Args:
            scored_sites: Sites to enrich

        Returns:
            List of enriched ScoredSite objects
        """
        # In future, batch these calls efficiently
        enriched = []
        for site in scored_sites:
            site = await self.enrich_with_fda(site)
            site = await self.enrich_with_pubmed(site)
            enriched.append(site)
        return enriched
