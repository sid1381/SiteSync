"""
Scoring Engine for SiteSync Screener.

Combines country-level and site-level scores into final ranked output.

Final Score = (Site Score × site_country_ratio) + (Country Score × (1 - site_country_ratio))
Default site_country_ratio = 0.7 (sites weighted more than country)
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

from app.services.screener.data_sources.base import (
    ProtocolCriteria,
    CountryRecord,
)
from app.services.screener.country_feasibility import (
    CountryFeasibilityEngine,
    ScoringWeights as CountryScoringWeights,
)
from app.services.screener.site_intelligence import (
    SiteIntelligenceEngine,
    ScoredSite,
    SiteScoringWeights,
)

logger = logging.getLogger(__name__)


@dataclass
class FinalScoredSite:
    """Site with final combined score (site + country)."""
    # Site data
    site_id: str
    site_name: str
    city: str
    state: Optional[str]
    country: str
    country_code: str

    # Component scores
    site_composite_score: float
    country_composite_score: float
    final_score: float

    # Detailed site scores
    experience_score: float
    pi_strength_score: float
    capacity_score: float
    compliance_score: float
    protocol_match_score: float

    # Site analytics
    trial_count: int
    indication_trial_count: int
    completion_rate: float
    competing_trial_count: int

    # Investigators
    investigators: List[Dict] = field(default_factory=list)

    # Flags and analysis
    red_flags: List[str] = field(default_factory=list)
    yellow_flags: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    gap_analysis: Optional[str] = None

    # Shortlist status
    is_shortlisted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScoringConfiguration:
    """Complete scoring configuration for the engine."""
    # Country scoring weights
    country_weights: CountryScoringWeights = field(
        default_factory=CountryScoringWeights
    )

    # Site scoring weights
    site_weights: SiteScoringWeights = field(
        default_factory=SiteScoringWeights
    )

    # How much to weight site vs country in final score
    site_country_ratio: float = 0.7  # 70% site, 30% country

    def to_dict(self) -> Dict[str, Any]:
        return {
            "country_weights": {
                "trial_experience": self.country_weights.trial_experience,
                "site_density": self.country_weights.site_density,
                "competition": self.country_weights.competition,
                "regulatory": self.country_weights.regulatory,
                "prevalence": self.country_weights.prevalence,
            },
            "site_weights": {
                "experience": self.site_weights.experience,
                "pi_strength": self.site_weights.pi_strength,
                "capacity": self.site_weights.capacity,
                "compliance": self.site_weights.compliance,
                "protocol_match": self.site_weights.protocol_match,
            },
            "site_country_ratio": self.site_country_ratio,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScoringConfiguration":
        """Create configuration from dictionary."""
        config = cls()

        if "country_weights" in data:
            cw = data["country_weights"]
            config.country_weights = CountryScoringWeights(
                trial_experience=cw.get("trial_experience", 0.30),
                site_density=cw.get("site_density", 0.25),
                competition=cw.get("competition", 0.20),
                regulatory=cw.get("regulatory", 0.15),
                prevalence=cw.get("prevalence", 0.10),
            )

        if "site_weights" in data:
            sw = data["site_weights"]
            config.site_weights = SiteScoringWeights(
                experience=sw.get("experience", 0.35),
                pi_strength=sw.get("pi_strength", 0.20),
                capacity=sw.get("capacity", 0.20),
                compliance=sw.get("compliance", 0.15),
                protocol_match=sw.get("protocol_match", 0.10),
            )

        if "site_country_ratio" in data:
            config.site_country_ratio = data["site_country_ratio"]

        return config


class ScoringEngine:
    """
    Main scoring engine that orchestrates country and site scoring.

    Provides unified interface for:
    - Running country rankings
    - Running site rankings within countries
    - Computing final combined scores
    - Adjusting weights and recalculating
    """

    def __init__(self, config: Optional[ScoringConfiguration] = None):
        """
        Initialize the scoring engine.

        Args:
            config: Scoring configuration with all weights
        """
        self.config = config or ScoringConfiguration()

        # Initialize sub-engines
        self.country_engine = CountryFeasibilityEngine(
            weights=self.config.country_weights
        )
        self.site_engine = SiteIntelligenceEngine(
            weights=self.config.site_weights
        )

    async def rank_countries(
        self,
        criteria: ProtocolCriteria,
        min_trials: int = 1,
        include_ai_analysis: bool = True
    ) -> List[CountryRecord]:
        """
        Rank countries by feasibility.

        Args:
            criteria: Protocol requirements
            min_trials: Minimum trials to include country
            include_ai_analysis: Whether to include AI regulatory analysis

        Returns:
            List of CountryRecord sorted by composite score
        """
        return await self.country_engine.rank_countries(
            criteria=criteria,
            min_trials=min_trials,
            include_ai_analysis=include_ai_analysis,
        )

    async def rank_sites_in_country(
        self,
        criteria: ProtocolCriteria,
        country_code: str,
        country_name: Optional[str] = None,
        country_score: Optional[float] = None,
        min_trials: int = 1,
        include_gap_analysis: bool = False
    ) -> List[FinalScoredSite]:
        """
        Rank sites within a country with final combined scores.

        Args:
            criteria: Protocol requirements
            country_code: ISO country code
            country_name: Full country name for CT.gov query
            country_score: Pre-computed country score (optional)
            min_trials: Minimum trials to include site
            include_gap_analysis: Whether to include AI gap analysis

        Returns:
            List of FinalScoredSite sorted by final score
        """
        # Get site rankings
        scored_sites = await self.site_engine.rank_sites(
            criteria=criteria,
            country_code=country_code,
            country_name=country_name,
            min_trials=min_trials,
            include_gap_analysis=include_gap_analysis,
        )

        if not scored_sites:
            return []

        # Get country score if not provided
        if country_score is None:
            country_score = await self._get_country_score(
                criteria=criteria,
                country_code=country_code,
            )

        # Convert to FinalScoredSite with combined scores
        final_sites = self._compute_final_scores(
            scored_sites=scored_sites,
            country_score=country_score,
            country_code=country_code,
        )

        # Sort by final score
        final_sites.sort(key=lambda s: s.final_score, reverse=True)

        return final_sites

    async def _get_country_score(
        self,
        criteria: ProtocolCriteria,
        country_code: str
    ) -> float:
        """Get the composite score for a country."""
        countries = await self.country_engine.rank_countries(
            criteria=criteria,
            min_trials=0,
            include_ai_analysis=False,
        )

        for country in countries:
            if country.country_code.upper() == country_code.upper():
                return country.composite_score

        return 50.0  # Default moderate score if not found

    def _compute_final_scores(
        self,
        scored_sites: List[ScoredSite],
        country_score: float,
        country_code: str,
    ) -> List[FinalScoredSite]:
        """Compute final combined scores for all sites."""
        final_sites = []

        site_ratio = self.config.site_country_ratio
        country_ratio = 1 - site_ratio

        for scored in scored_sites:
            site = scored.site

            # Calculate final combined score
            final_score = (
                scored.site_composite_score * site_ratio +
                country_score * country_ratio
            )

            # Convert investigators to dicts
            investigators = [
                inv.to_dict() if hasattr(inv, 'to_dict') else inv
                for inv in site.investigators[:5]
            ]

            final_site = FinalScoredSite(
                site_id=site.site_id or "",
                site_name=site.site_name,
                city=site.city,
                state=site.state,
                country=site.country,
                country_code=country_code,
                site_composite_score=scored.site_composite_score,
                country_composite_score=country_score,
                final_score=final_score,
                experience_score=scored.experience_score,
                pi_strength_score=scored.pi_strength_score,
                capacity_score=scored.capacity_score,
                compliance_score=scored.compliance_score,
                protocol_match_score=scored.protocol_match_score,
                trial_count=site.trial_count,
                indication_trial_count=site.indication_trial_count,
                completion_rate=scored.completion_rate,
                competing_trial_count=scored.competing_trial_count,
                investigators=investigators,
                red_flags=scored.red_flags,
                yellow_flags=scored.yellow_flags,
                strengths=scored.strengths,
                gap_analysis=scored.gap_analysis,
            )

            final_sites.append(final_site)

        return final_sites

    def recalculate_sites(
        self,
        sites: List[FinalScoredSite],
        country_scores: Dict[str, float],
    ) -> List[FinalScoredSite]:
        """
        Recalculate final scores with current weights.

        Use this after updating weights to refresh scores without re-fetching data.

        Args:
            sites: List of sites to recalculate
            country_scores: Map of country_code -> country_score

        Returns:
            List of sites with recalculated final scores
        """
        site_ratio = self.config.site_country_ratio
        country_ratio = 1 - site_ratio

        # Normalize weights so they sum to 1.0
        norm_weights = self.config.site_weights.normalized()

        for site in sites:
            # Recalculate site composite from components using normalized weights
            site.site_composite_score = (
                site.experience_score * norm_weights.experience +
                site.pi_strength_score * norm_weights.pi_strength +
                site.capacity_score * norm_weights.capacity +
                site.compliance_score * norm_weights.compliance +
                site.protocol_match_score * norm_weights.protocol_match
            )

            # Get country score
            country_score = country_scores.get(
                site.country_code.upper(),
                site.country_composite_score
            )
            site.country_composite_score = country_score

            # Recalculate final score
            site.final_score = (
                site.site_composite_score * site_ratio +
                country_score * country_ratio
            )

        # Re-sort
        sites.sort(key=lambda s: s.final_score, reverse=True)

        return sites

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        Update scoring configuration.

        Args:
            new_config: Dictionary with updated configuration values
        """
        if "country_weights" in new_config:
            cw = new_config["country_weights"]
            self.config.country_weights.trial_experience = cw.get(
                "trial_experience", self.config.country_weights.trial_experience
            )
            self.config.country_weights.site_density = cw.get(
                "site_density", self.config.country_weights.site_density
            )
            self.config.country_weights.competition = cw.get(
                "competition", self.config.country_weights.competition
            )
            self.config.country_weights.regulatory = cw.get(
                "regulatory", self.config.country_weights.regulatory
            )
            self.config.country_weights.prevalence = cw.get(
                "prevalence", self.config.country_weights.prevalence
            )

            # Update country engine weights
            self.country_engine.weights = self.config.country_weights

        if "site_weights" in new_config:
            sw = new_config["site_weights"]
            self.config.site_weights.experience = sw.get(
                "experience", self.config.site_weights.experience
            )
            self.config.site_weights.pi_strength = sw.get(
                "pi_strength", self.config.site_weights.pi_strength
            )
            self.config.site_weights.capacity = sw.get(
                "capacity", self.config.site_weights.capacity
            )
            self.config.site_weights.compliance = sw.get(
                "compliance", self.config.site_weights.compliance
            )
            self.config.site_weights.protocol_match = sw.get(
                "protocol_match", self.config.site_weights.protocol_match
            )

            # Update site engine weights
            self.site_engine.weights = self.config.site_weights

        if "site_country_ratio" in new_config:
            self.config.site_country_ratio = new_config["site_country_ratio"]

        logger.info(f"Scoring config updated: {self.config.to_dict()}")

    def get_config(self) -> Dict[str, Any]:
        """Get current scoring configuration."""
        return self.config.to_dict()
