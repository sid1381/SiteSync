"""
Country Feasibility Engine for SiteSync Screener.

Takes ProtocolCriteria and returns ranked list of CountryRecords with
composite feasibility scores.

Scoring Components:
- trial_experience_score (30%): Normalized trial count in indication
- site_density_score (25%): Number of qualified sites
- competition_score (20%): INVERSE - more competing = lower score
- regulatory_score (15%): Data-driven from World Bank indicators
- prevalence_score (10%): AI-assessed disease prevalence

Data Sources:
- ClinicalTrials.gov: Trial counts, site density, competition
- World Bank API: Regulatory Quality Index, Logistics Performance, Health Expenditure
- GPT-4o: Prevalence estimates, explanation of data-driven scores
"""

import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from app.services.screener.data_sources.base import (
    ProtocolCriteria,
    CountryRecord,
)
from app.services.screener.data_sources.ctgov_source import CTGovDataSource
from app.services.screener.data_sources.worldbank_source import (
    WorldBankDataSource,
    CountryIndicators,
    get_worldbank_source,
)
from app.services.screener.data_sources.prevalence_source import (
    PrevalenceSource,
    PrevalenceData,
    get_prevalence_source,
)
from app.services.screener.data_sources.regulatory_maturity import (
    get_regulatory_maturity_bonus,
)

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Configurable weights for country scoring."""
    trial_experience: float = 0.30
    site_density: float = 0.25
    competition: float = 0.20
    regulatory: float = 0.15
    prevalence: float = 0.10

    def validate(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.trial_experience +
            self.site_density +
            self.competition +
            self.regulatory +
            self.prevalence
        )
        return abs(total - 1.0) < 0.01

    def normalized(self) -> "ScoringWeights":
        """Return normalized weights that sum to 1.0."""
        total = (
            self.trial_experience +
            self.site_density +
            self.competition +
            self.regulatory +
            self.prevalence
        )
        if total == 0:
            total = 1.0  # Avoid division by zero
        return ScoringWeights(
            trial_experience=self.trial_experience / total,
            site_density=self.site_density / total,
            competition=self.competition / total,
            regulatory=self.regulatory / total,
            prevalence=self.prevalence / total,
        )


class CountryFeasibilityEngine:
    """
    Ranks countries by feasibility for a given protocol.

    Uses ClinicalTrials.gov data to score countries on:
    - Historical trial experience in the indication
    - Site density and capacity
    - Current competition (recruiting trials)
    - Regulatory environment (AI-assessed)
    - Disease prevalence (AI-assessed)
    """

    def __init__(
        self,
        weights: Optional[ScoringWeights] = None,
        openai_client: Optional[Any] = None
    ):
        """
        Initialize the country feasibility engine.

        Args:
            weights: Custom scoring weights (default: standard weights)
            openai_client: OpenAI client for AI-enhanced scoring
        """
        self.weights = weights or ScoringWeights()
        self.ctgov = CTGovDataSource()

        # Initialize World Bank data source for data-driven regulatory scoring
        try:
            self.worldbank = get_worldbank_source()
        except Exception as e:
            logger.warning(f"World Bank data source not available: {e}")
            self.worldbank = None

        # Initialize prevalence source for epidemiology data
        try:
            self.prevalence_source = get_prevalence_source()
        except Exception as e:
            logger.warning(f"Prevalence data source not available: {e}")
            self.prevalence_source = None

        # Try to initialize OpenAI for AI-enhanced scoring
        self.openai = openai_client
        if self.openai is None:
            try:
                from app.services.openai_client import get_openai_client
                self.openai = get_openai_client()
            except Exception as e:
                logger.warning(f"OpenAI not available for regulatory/prevalence scoring: {e}")
                self.openai = None

    async def rank_countries(
        self,
        criteria: ProtocolCriteria,
        min_trials: int = 1,
        include_ai_analysis: bool = True
    ) -> List[CountryRecord]:
        """
        Rank countries by feasibility for the given protocol criteria.

        Args:
            criteria: Protocol requirements extracted from PDF
            min_trials: Minimum trials required to include a country
            include_ai_analysis: Whether to include AI regulatory/prevalence analysis

        Returns:
            List of CountryRecord objects sorted by composite score
        """
        logger.info(
            f"Ranking countries for indication='{criteria.indication}', "
            f"phase='{criteria.phase}'"
        )

        # Get phase filter for API
        phase_filter = criteria.get_phase_filter()

        # Step 1: Get country summaries from ClinicalTrials.gov
        countries = await self.ctgov.get_country_summary(
            condition=criteria.indication,
            phase=phase_filter,
        )

        if not countries:
            logger.warning(f"No countries found for indication='{criteria.indication}'")
            return []

        logger.info(f"Retrieved {len(countries)} countries from CT.gov")

        # Filter by minimum trials
        countries = [c for c in countries if c.total_trials >= min_trials]
        logger.info(f"{len(countries)} countries have >= {min_trials} trials")

        if not countries:
            return []

        # Step 2: Calculate base scores for each country
        scored_countries = self._calculate_scores(countries)

        # Step 3: Fetch World Bank indicators for data-driven regulatory scoring
        worldbank_data: Dict[str, CountryIndicators] = {}
        if self.worldbank:
            try:
                country_codes = [c.country_code for c in scored_countries if c.country_code]
                worldbank_data = await self.worldbank.get_country_indicators(country_codes)
                logger.info(f"World Bank data fetched for {len(worldbank_data)} countries")
            except Exception as e:
                logger.warning(f"Failed to fetch World Bank data: {e}")

        # Step 4: Apply World Bank data to regulatory scores and get populations
        countries_with_wb_data = 0
        countries_without_wb_data = []
        populations: Dict[str, int] = {}

        for country in scored_countries:
            wb_data = worldbank_data.get(country.country_code.upper())
            if wb_data:
                composite_reg = wb_data.get_composite_regulatory_score()
                if composite_reg is not None:
                    # Store base World Bank score
                    country.regulatory_base_score = composite_reg
                    country.regulatory_score = composite_reg
                    country.regulatory_missing = False

                    # Store raw indicators for display
                    country.regulatory_quality_raw = wb_data.regulatory_quality_raw
                    country.physician_density = wb_data.physician_density_raw
                    country.logistics_index = wb_data.logistics_index_raw
                    country.health_expenditure_pct = wb_data.health_expenditure_raw
                    countries_with_wb_data += 1
                    logger.debug(
                        f"Country {country.country_code}: World Bank regulatory score = "
                        f"{composite_reg:.0f} (RQ={wb_data.regulatory_quality_raw:.2f})"
                    )
                else:
                    countries_without_wb_data.append(country.country_code)
                    country.regulatory_missing = True

                # Store population for addressable pool calculation
                if wb_data.population:
                    populations[country.country_code.upper()] = wb_data.population
                    country.population = wb_data.population
            else:
                countries_without_wb_data.append(country.country_code)
                country.regulatory_missing = True

        # Step 4b: Apply WHO GBT / SRA regulatory maturity bonus
        countries_with_gbt_bonus = 0
        for country in scored_countries:
            gbt_bonus, gbt_tier, gbt_authority = get_regulatory_maturity_bonus(country.country_code)
            country.regulatory_gbt_bonus = gbt_bonus
            country.regulatory_gbt_tier = gbt_tier
            country.regulatory_gbt_authority = gbt_authority

            if gbt_bonus > 0:
                # Apply bonus, capped at 100
                if country.regulatory_base_score is not None:
                    country.regulatory_score = min(100.0, country.regulatory_base_score + gbt_bonus)
                elif country.regulatory_score is not None and not country.regulatory_missing:
                    country.regulatory_score = min(100.0, country.regulatory_score + gbt_bonus)
                countries_with_gbt_bonus += 1
                logger.debug(
                    f"Country {country.country_code}: +{gbt_bonus} {gbt_tier} bonus "
                    f"({gbt_authority}) → {country.regulatory_score:.0f}"
                )

        if countries_with_gbt_bonus > 0:
            logger.info(
                f"Applied WHO GBT/SRA bonus to {countries_with_gbt_bonus} countries"
            )

        if countries_with_wb_data > 0:
            logger.info(
                f"Applied World Bank data to {countries_with_wb_data} countries, "
                f"{len(countries_without_wb_data)} will use AI fallback"
            )

        # Step 5: Fetch prevalence data and calculate addressable patient pools
        prevalence_data: Dict[str, PrevalenceData] = {}
        if self.prevalence_source and criteria.indication:
            try:
                country_codes = [c.country_code for c in scored_countries if c.country_code]
                prevalence_data = await self.prevalence_source.get_prevalence(
                    indication=criteria.indication,
                    indication_detail=criteria.indication_detail or "",
                    countries=country_codes,
                )
                logger.info(f"Prevalence data fetched for {len(prevalence_data)} countries")

                # Calculate exclusion criteria count
                num_exclusion = len(criteria.exclusion_criteria) if criteria.exclusion_criteria else 0

                # Calculate addressable pools
                prevalence_data = self.prevalence_source.calculate_addressable_pool(
                    prevalence_data=prevalence_data,
                    populations=populations,
                    num_exclusion_criteria=num_exclusion,
                )

                # Apply prevalence data to countries
                self._apply_prevalence_data(scored_countries, prevalence_data)

                # Calculate competition metrics using demand/supply model
                self._apply_competition_metrics(scored_countries, prevalence_data)

            except Exception as e:
                logger.warning(f"Failed to fetch prevalence data: {e}")

        # Step 6: Add AI analysis for countries (explain WB data, fallback for missing)
        if include_ai_analysis and self.openai:
            # Only analyze top 20 to save API calls
            top_countries = scored_countries[:20]
            top_countries = await self._add_ai_analysis(
                top_countries,
                criteria,
                worldbank_data,  # Pass WB data for context
            )
            # Recalculate composite scores with AI scores
            top_countries = self._recalculate_composite(top_countries)
            # Merge back
            scored_countries = top_countries + scored_countries[20:]

        # Step 7: Build dimension breakdown for transparent scoring
        self._build_dimension_breakdown(scored_countries, worldbank_data)

        # Step 8: Sort by composite score
        scored_countries.sort(key=lambda c: c.composite_score, reverse=True)

        logger.info(
            f"Country ranking complete. Top 5: "
            f"{[f'{c.country_name}({c.composite_score:.0f})' for c in scored_countries[:5]]}"
        )

        return scored_countries

    def _calculate_scores(
        self,
        countries: List[CountryRecord]
    ) -> List[CountryRecord]:
        """
        Calculate component scores and composite score for each country.

        Uses PERCENTILE RANKING for trial_experience and site_density scores.
        This is more stable than max-normalization (one outlier doesn't skew all scores)
        and more meaningful ("Italy is in the 96th percentile for site density").

        All scores are normalized to 0-100 scale.
        """
        if not countries:
            return countries

        n = len(countries)

        # Sort and rank by weighted_experience for trial experience (percentile ranking)
        # Weighted experience accounts for recency, phase match, and completion status
        # Use indication_trials as tiebreaker, then total_trials
        sorted_by_trials = sorted(
            enumerate(countries),
            key=lambda x: (x[1].weighted_experience, x[1].indication_trials, x[1].total_trials)
        )
        trial_ranks = {idx: rank for rank, (idx, _) in enumerate(sorted_by_trials)}

        # Sort and rank by site_count for site density (percentile ranking)
        sorted_by_sites = sorted(
            enumerate(countries),
            key=lambda x: x[1].site_count
        )
        site_ranks = {idx: rank for rank, (idx, _) in enumerate(sorted_by_sites)}

        # Store ranking data for dimension breakdown (used later)
        self._ranking_data = {
            'trial_ranks': {},  # country_code -> (rank, percentile, rank_position)
            'site_ranks': {},
            'total_countries': n,
        }

        # Calculate scores using percentile ranking
        for idx, country in enumerate(countries):
            # Trial Experience Score (30%) - percentile ranking
            # Score = (rank / (total-1)) * 100, where rank 0 = lowest
            trial_percentile = (trial_ranks[idx] / max(n - 1, 1)) * 100
            country.trial_experience_score = trial_percentile

            # Store for breakdown (including weighted experience details)
            trial_rank_pos = n - trial_ranks[idx]  # 1st = highest
            avg_weight = (
                country.weighted_experience / country.experience_trial_count
                if country.experience_trial_count > 0
                else 0.0
            )
            self._ranking_data['trial_ranks'][country.country_code] = {
                'rank': trial_ranks[idx],
                'percentile': trial_percentile,
                'rank_position': f"{self._ordinal(trial_rank_pos)} of {n}",
                'weighted_experience': country.weighted_experience,
                'experience_trial_count': country.experience_trial_count,
                'avg_weight_per_trial': round(avg_weight, 3),
                'experience_weights_used': country.experience_weights_used,
            }

            # Site Density Score (25%) - percentile ranking
            site_percentile = (site_ranks[idx] / max(n - 1, 1)) * 100
            country.site_density_score = site_percentile

            # Store for breakdown
            site_rank_pos = n - site_ranks[idx]
            self._ranking_data['site_ranks'][country.country_code] = {
                'rank': site_ranks[idx],
                'percentile': site_percentile,
                'rank_position': f"{self._ordinal(site_rank_pos)} of {n}",
            }

            # Competition Score (20%)
            # INVERSE - more competing trials = lower score
            # Note: This may be updated later by _apply_competition_metrics with demand/supply model
            max_recruiting = max(c.actively_recruiting for c in countries) or 1
            if max_recruiting > 0:
                competition_ratio = country.actively_recruiting / max_recruiting
                country.competition_score = (1 - competition_ratio) * 100
            else:
                country.competition_score = 100  # No competition is good

            # Regulatory Score (15%) - will be set by World Bank data or AI fallback
            # Flag as missing for re-weighting; World Bank/AI will update later
            country.regulatory_score = None
            country.regulatory_missing = True

            # Prevalence Score (10%) - will be set by prevalence data or AI fallback
            # Flag as missing for re-weighting; prevalence source will update later
            country.prevalence_score = None
            country.prevalence_missing = True

            # Calculate composite score
            country.composite_score = self._compute_composite(country)

        return countries

    def _ordinal(self, n: int) -> str:
        """Return ordinal string for a number (1st, 2nd, 3rd, etc.)."""
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        else:
            suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
        return f"{n}{suffix}"

    def _compute_composite(self, country: CountryRecord) -> float:
        """
        Compute weighted composite score for a country, re-weighting if dimensions are missing.

        If regulatory_score or prevalence_score is None (missing data), the composite
        is calculated using only available dimensions and their weights are normalized
        to sum to 1.0. This prevents unfair penalties for countries with missing data.
        """
        # Build list of (score, weight) for available dimensions
        dimensions = [
            (country.trial_experience_score, self.weights.trial_experience),
            (country.site_density_score, self.weights.site_density),
            (country.competition_score, self.weights.competition),
            (country.regulatory_score, self.weights.regulatory),
            (country.prevalence_score, self.weights.prevalence),
        ]

        available_score = 0.0
        available_weight = 0.0

        for score, weight in dimensions:
            if score is not None:
                available_score += score * weight
                available_weight += weight

        if available_weight == 0:
            return 0.0

        # Re-weight: normalize to 0-100 scale by dividing by available weight
        return available_score / available_weight

    def _recalculate_composite(
        self,
        countries: List[CountryRecord]
    ) -> List[CountryRecord]:
        """Recalculate composite scores after AI analysis."""
        for country in countries:
            country.composite_score = self._compute_composite(country)
        return countries

    def _build_dimension_breakdown(
        self,
        countries: List[CountryRecord],
        worldbank_data: Dict[str, CountryIndicators],
    ) -> None:
        """
        Build dimension_breakdown for each country with transparent scoring details.

        Populates country.dimension_breakdown with detailed score breakdown
        that the frontend can render directly without recalculation.
        """
        norm_weights = self.weights.normalized()

        for country in countries:
            code = country.country_code.upper()

            # Get ranking data (stored during _calculate_scores)
            trial_rank_data = getattr(self, '_ranking_data', {}).get('trial_ranks', {}).get(code, {})
            site_rank_data = getattr(self, '_ranking_data', {}).get('site_ranks', {}).get(code, {})
            prevalence_rank_data = getattr(self, '_ranking_data', {}).get('prevalence_ranks', {}).get(code, {})
            total_countries = getattr(self, '_ranking_data', {}).get('total_countries', len(countries))

            # Get World Bank data for regulatory breakdown
            wb = worldbank_data.get(code)

            # Build trial experience breakdown (with weighted experience details)
            weighted_exp = trial_rank_data.get('weighted_experience', country.weighted_experience)
            trial_count = trial_rank_data.get('experience_trial_count', country.experience_trial_count)
            avg_weight = trial_rank_data.get('avg_weight_per_trial', 0)
            weights_used = trial_rank_data.get('experience_weights_used', country.experience_weights_used)

            trial_breakdown = {
                "score": round(country.trial_experience_score, 1),
                "weight": norm_weights.trial_experience,
                "weighted_contribution": round(country.trial_experience_score * norm_weights.trial_experience, 1),
                "data": {
                    "indication_trials": country.indication_trials,
                    "total_trials": country.total_trials,
                    "weighted_experience": round(weighted_exp, 2) if weighted_exp else 0,
                    "avg_weight_per_trial": round(avg_weight, 2) if avg_weight else None,
                    "weights_applied": weights_used,
                    "percentile_rank": round(trial_rank_data.get('percentile', 0), 0),
                    "rank_position": trial_rank_data.get('rank_position', f"? of {total_countries}"),
                },
                "explanation": self._build_trial_experience_explanation(
                    country, trial_rank_data, total_countries
                ),
            }

            # Build site density breakdown
            sites_per_10m = None
            if country.population and country.population > 0:
                sites_per_10m = round((country.site_count / country.population) * 10_000_000, 1)

            site_breakdown = {
                "score": round(country.site_density_score, 1),
                "weight": norm_weights.site_density,
                "weighted_contribution": round(country.site_density_score * norm_weights.site_density, 1),
                "data": {
                    "site_count": country.site_count,
                    "sites_per_10m_pop": sites_per_10m,
                    "percentile_rank": round(site_rank_data.get('percentile', 0), 0),
                    "rank_position": site_rank_data.get('rank_position', f"? of {total_countries}"),
                },
                "explanation": (
                    f"{country.site_count} research sites"
                    + (f" ({sites_per_10m} per 10M pop)" if sites_per_10m else "")
                    + f", {site_rank_data.get('rank_position', '')}"
                ),
            }

            # Build competition breakdown
            comp_score = country.competition_score if country.competition_score is not None else 0
            has_real_enrollment_data = bool(country.competing_trial_details and any(
                d.get("enrollment") for d in country.competing_trial_details
            ))
            competition_breakdown = {
                "score": round(comp_score, 1) if country.competition_score is not None else None,
                "weight": norm_weights.competition,
                "weighted_contribution": round(comp_score * norm_weights.competition, 1) if country.competition_score is not None else None,
                "data": {
                    "competing_trials": country.actively_recruiting,
                    "competition_demand": country.competition_demand,
                    "addressable_pool": country.addressable_pool,
                    "competition_ratio": round(country.competition_ratio, 4) if country.competition_ratio else None,
                    "pressure_level": country.competition_pressure,
                    "demand_source": "CT.gov enrollment" if has_real_enrollment_data else "estimated",
                    "avg_competing_enrollment": round(country.avg_competing_enrollment, 0) if country.avg_competing_enrollment else None,
                    "trials_with_enrollment_data": sum(1 for d in country.competing_trial_details if d.get("enrollment")) if country.competing_trial_details else 0,
                },
                "explanation": self._build_competition_explanation(country),
            }

            # Build regulatory breakdown
            reg_score = country.regulatory_score if country.regulatory_score is not None else 0
            regulatory_breakdown = {
                "score": round(reg_score, 1) if country.regulatory_score is not None else None,
                "weight": norm_weights.regulatory,
                "weighted_contribution": round(reg_score * norm_weights.regulatory, 1) if country.regulatory_score is not None else None,
                "data": {},
                "explanation": "",
                "missing": country.regulatory_missing,
            }

            # Add GBT bonus info to data
            if country.regulatory_gbt_bonus is not None and country.regulatory_gbt_bonus > 0:
                regulatory_breakdown["data"]["gbt_bonus"] = {
                    "bonus": country.regulatory_gbt_bonus,
                    "tier": country.regulatory_gbt_tier,
                    "authority": country.regulatory_gbt_authority,
                }

            if wb and wb.regulatory_quality_raw is not None:
                # World Bank data available - show component breakdown
                rq_normalized = wb.regulatory_quality or 0
                lpi_normalized = ((wb.logistics_index_raw or 3) - 1) / 4 * 100 if wb.logistics_index_raw else None
                he_normalized = min(100, ((wb.health_expenditure_raw or 0) / 20) * 100)
                base_score = country.regulatory_base_score or reg_score

                regulatory_breakdown["data"]["regulatory_quality"] = {
                    "raw": wb.regulatory_quality_raw,
                    "normalized": round(rq_normalized, 0),
                    "weight": 0.5,
                }
                regulatory_breakdown["data"]["logistics_index"] = {
                    "raw": wb.logistics_index_raw,
                    "normalized": round(lpi_normalized, 0) if lpi_normalized else None,
                    "weight": 0.3,
                }
                regulatory_breakdown["data"]["health_expenditure"] = {
                    "raw": wb.health_expenditure_raw,
                    "normalized": round(he_normalized, 0),
                    "weight": 0.2,
                }

                # Build explanation with GBT bonus if applicable
                if country.regulatory_gbt_bonus and country.regulatory_gbt_bonus > 0:
                    if lpi_normalized:
                        regulatory_breakdown["explanation"] = (
                            f"World Bank composite: RQ {rq_normalized:.0f}×0.5 + "
                            f"LPI {lpi_normalized:.0f}×0.3 + HE {he_normalized:.0f}×0.2 = {base_score:.0f}, "
                            f"+ {country.regulatory_gbt_tier} bonus +{country.regulatory_gbt_bonus:.0f} "
                            f"({country.regulatory_gbt_authority}) → {reg_score:.0f}"
                        )
                    else:
                        regulatory_breakdown["explanation"] = (
                            f"Regulatory Quality Index: {wb.regulatory_quality_raw:.2f} = {base_score:.0f}, "
                            f"+ {country.regulatory_gbt_tier} bonus +{country.regulatory_gbt_bonus:.0f} → {reg_score:.0f}"
                        )
                else:
                    regulatory_breakdown["explanation"] = (
                        f"World Bank composite: RQ {rq_normalized:.0f}×0.5 + "
                        f"LPI {lpi_normalized:.0f}×0.3 + HE {he_normalized:.0f}×0.2 = "
                        f"{reg_score:.0f} (No WHO GBT/SRA classification)"
                    ) if lpi_normalized else f"Regulatory Quality Index: {wb.regulatory_quality_raw:.2f}"
            elif country.regulatory_score is not None:
                # AI-estimated or GBT bonus only
                if country.regulatory_gbt_bonus and country.regulatory_gbt_bonus > 0:
                    regulatory_breakdown["data"]["source"] = "AI estimate + GBT bonus"
                    regulatory_breakdown["explanation"] = (
                        f"AI-estimated with {country.regulatory_gbt_tier} bonus "
                        f"+{country.regulatory_gbt_bonus:.0f} ({country.regulatory_gbt_authority})"
                    )
                else:
                    regulatory_breakdown["data"]["source"] = "AI estimate"
                    regulatory_breakdown["explanation"] = "AI-estimated (no World Bank data available)"
            else:
                # Missing data - will be excluded from composite
                regulatory_breakdown["data"]["source"] = "Missing"
                regulatory_breakdown["explanation"] = "No regulatory data available (excluded from composite)"

            # Build prevalence breakdown
            prev_score = country.prevalence_score if country.prevalence_score is not None else 0
            prevalence_breakdown = {
                "score": round(prev_score, 1) if country.prevalence_score is not None else None,
                "weight": norm_weights.prevalence,
                "weighted_contribution": round(prev_score * norm_weights.prevalence, 1) if country.prevalence_score is not None else None,
                "data": {
                    "prevalence_per_100k": country.prevalence_per_100k,
                    "source": country.prevalence_source,
                    "data_year": country.prevalence_data_year,
                    "confidence": country.prevalence_confidence,
                    "estimated_patients": country.estimated_patients,
                    "addressable_pool": country.addressable_pool,
                    "percentile_rank": round(prevalence_rank_data.get('percentile', 50), 0),
                    "rank_position": prevalence_rank_data.get('rank_position', ''),
                },
                "explanation": self._build_prevalence_explanation(country, prevalence_rank_data),
                "missing": country.prevalence_missing,
            }

            # Build overall breakdown - handle None scores
            formula_parts = []
            if country.trial_experience_score is not None:
                formula_parts.append(f"{country.trial_experience_score:.0f}×{norm_weights.trial_experience}")
            if country.site_density_score is not None:
                formula_parts.append(f"{country.site_density_score:.0f}×{norm_weights.site_density}")
            if country.competition_score is not None:
                formula_parts.append(f"{country.competition_score:.0f}×{norm_weights.competition}")
            if country.regulatory_score is not None:
                formula_parts.append(f"{country.regulatory_score:.0f}×{norm_weights.regulatory}")
            if country.prevalence_score is not None:
                formula_parts.append(f"{country.prevalence_score:.0f}×{norm_weights.prevalence}")

            overall_breakdown = {
                "score": round(country.composite_score, 1),
                "formula": " + ".join(formula_parts),
                "result": round(country.composite_score, 1),
            }

            # Assemble full breakdown
            country.dimension_breakdown = {
                "trial_experience": trial_breakdown,
                "site_density": site_breakdown,
                "competition": competition_breakdown,
                "regulatory": regulatory_breakdown,
                "prevalence": prevalence_breakdown,
                "overall": overall_breakdown,
            }

    def _build_competition_explanation(self, country: CountryRecord) -> str:
        """Build human-readable competition explanation."""
        # Determine data source for demand calculation
        has_real_data = bool(country.competing_trial_details and any(
            d.get("enrollment") for d in country.competing_trial_details
        ))
        demand_source = "CT.gov enrollment" if has_real_data else "estimated"

        if country.competition_ratio is not None and country.addressable_pool:
            ratio_pct = country.competition_ratio * 100
            return (
                f"{country.actively_recruiting} competing trial(s) "
                f"(~{country.competition_demand:,} patient demand, {demand_source}) vs "
                f"~{country.addressable_pool:,} addressable patients — "
                f"{country.competition_pressure} pressure ({ratio_pct:.2f}%)"
            )
        else:
            return f"{country.actively_recruiting} competing trial(s) recruiting"

    def _build_prevalence_explanation(self, country: CountryRecord, rank_data: dict) -> str:
        """Build human-readable prevalence explanation."""
        parts = []
        if country.prevalence_per_100k:
            parts.append(f"{country.prevalence_per_100k:.0f} per 100k")
            if country.prevalence_source:
                year = f", {country.prevalence_data_year}" if country.prevalence_data_year else ""
                parts.append(f"({country.prevalence_source}{year})")
        if country.estimated_patients:
            parts.append(f"— ~{country.estimated_patients:,} estimated patients")
        if rank_data.get('rank_position'):
            parts.append(f"[{rank_data['rank_position']}]")
        return " ".join(parts) if parts else "Prevalence data unavailable"

    def _build_trial_experience_explanation(
        self,
        country: CountryRecord,
        rank_data: dict,
        total_countries: int,
    ) -> str:
        """
        Build human-readable trial experience explanation with weighted experience details.

        Shows both raw trial counts and weighted experience (accounting for recency,
        phase match, and completion status).
        """
        parts = []

        # Raw trial count
        parts.append(f"{country.indication_trials} indication-specific trials")

        # Weighted experience info if available
        weighted_exp = rank_data.get('weighted_experience', country.weighted_experience)
        trial_count = rank_data.get('experience_trial_count', country.experience_trial_count)
        avg_weight = rank_data.get('avg_weight_per_trial', 0)

        if weighted_exp and trial_count > 0:
            # Show weighted score with interpretation
            if avg_weight >= 0.7:
                quality = "strong"  # Recent, phase-matched, completed
            elif avg_weight >= 0.4:
                quality = "moderate"
            else:
                quality = "mixed"  # Older, phase-mismatched, or terminated

            parts.append(
                f"(weighted score: {weighted_exp:.1f}, "
                f"avg quality: {avg_weight:.2f} — {quality} recency/phase/completion)"
            )

        # Ranking position
        rank_position = rank_data.get('rank_position')
        if rank_position:
            parts.append(f"[{rank_position}]")

        return " ".join(parts)

    def _apply_prevalence_data(
        self,
        countries: List[CountryRecord],
        prevalence_data: Dict[str, PrevalenceData],
    ) -> None:
        """
        Apply prevalence data to countries and calculate prevalence scores using percentile ranking.

        Updates country records in-place with:
        - prevalence_per_100k, incidence_per_100k
        - prevalence_source (citation)
        - prevalence_confidence
        - estimated_patients, eligibility_fraction, addressable_pool
        - prevalence_score (0-100, percentile ranking across countries)
        """
        if not prevalence_data:
            return

        # First pass: apply data to countries
        countries_with_data = []
        for country in countries:
            code = country.country_code.upper()
            data = prevalence_data.get(code)
            if data:
                # Store raw data
                country.prevalence_per_100k = data.prevalence_per_100k
                country.incidence_per_100k = data.incidence_per_100k
                country.prevalence_source = data.data_source
                country.prevalence_confidence = data.confidence
                country.prevalence_data_year = data.data_year

                # Store calculated pool data
                country.estimated_patients = data.estimated_patients
                country.eligibility_fraction = data.eligibility_fraction
                country.addressable_pool = data.addressable_pool

                if data.prevalence_per_100k and data.prevalence_per_100k > 0:
                    countries_with_data.append(country)

        # Second pass: calculate percentile ranking for prevalence scores
        if countries_with_data:
            # Sort by prevalence (lowest to highest)
            sorted_by_prevalence = sorted(
                countries_with_data,
                key=lambda c: c.prevalence_per_100k or 0
            )

            # Assign percentile ranks
            # Higher prevalence = higher score = better for recruitment
            # rank_pos 1 = lowest prevalence, rank_pos n = highest prevalence
            n = len(sorted_by_prevalence)
            prevalence_ranks = {}
            for rank, country in enumerate(sorted_by_prevalence):
                percentile = (rank / max(n - 1, 1)) * 100
                country.prevalence_score = percentile
                country.prevalence_missing = False  # Has valid data
                rank_pos = rank + 1  # 1st = lowest prevalence, nth = highest
                prevalence_ranks[country.country_code] = {
                    'rank': rank,
                    'percentile': percentile,
                    'rank_position': f"{self._ordinal(rank_pos)} of {n}",
                }

            # Store for dimension breakdown
            if hasattr(self, '_ranking_data'):
                self._ranking_data['prevalence_ranks'] = prevalence_ranks

            # Countries without prevalence data remain with prevalence_missing = True
            # (set in _calculate_scores) so they will be re-weighted in _compute_composite

            max_prevalence = max(c.prevalence_per_100k for c in countries_with_data)
            logger.info(
                f"Prevalence scores (percentile): {n} countries with data, "
                f"max={max_prevalence:.1f}/100k"
            )
        else:
            logger.warning("No countries have valid prevalence data")

    def _apply_competition_metrics(
        self,
        countries: List[CountryRecord],
        prevalence_data: Dict[str, PrevalenceData],
        default_patients_per_trial: int = 50,
    ) -> None:
        """
        Apply demand/supply competition model to countries.

        UPGRADED: Uses actual enrollment data from ClinicalTrials.gov instead of
        hardcoded estimates. For each competing trial, allocates enrollment
        proportionally to the country based on its share of the trial's sites.

        Updates country records in-place with:
        - competition_demand (estimated patient demand from recruiting trials)
        - competition_ratio (demand / addressable_pool)
        - competition_pressure ('low', 'moderate', 'high', 'extreme')
        - competition_score (0-100, based on ratio)
        """
        if not prevalence_data:
            return

        countries_with_real_data = 0
        countries_with_fallback = 0

        for country in countries:
            code = country.country_code.upper()
            data = prevalence_data.get(code)

            # Calculate demand from competing trials using REAL enrollment data
            demand = 0.0
            used_real_data = False

            if country.competing_trial_details:
                # Best case: per-trial country-allocated demand
                for trial in country.competing_trial_details:
                    enrollment = trial.get("enrollment")
                    if enrollment is None:
                        # Fallback for trials without enrollment data
                        enrollment = default_patients_per_trial
                    else:
                        used_real_data = True

                    sites_in_country = trial.get("sites_in_country", 1)
                    sites_total = max(trial.get("sites_total", 1), 1)

                    # Allocate this trial's enrollment proportionally to this country
                    country_share = enrollment * (sites_in_country / sites_total)
                    demand += country_share

                demand = int(demand)
                if used_real_data:
                    countries_with_real_data += 1
                else:
                    countries_with_fallback += 1

            elif country.avg_competing_enrollment:
                # Fallback: use average enrollment × count
                demand = int(country.actively_recruiting * country.avg_competing_enrollment)
                countries_with_real_data += 1
            else:
                # Last resort: original hardcoded fallback
                demand = country.actively_recruiting * default_patients_per_trial
                countries_with_fallback += 1

            country.competition_demand = demand

            # Calculate ratio if we have addressable pool
            if data and data.addressable_pool and data.addressable_pool > 0:
                ratio = demand / data.addressable_pool
                country.competition_ratio = ratio

                # Convert to score (0-100, where 100 = no competition)
                country.competition_score = max(0, 100 * (1 - ratio))

                # Determine pressure level
                if ratio < 0.01:
                    country.competition_pressure = "low"
                elif ratio < 0.1:
                    country.competition_pressure = "moderate"
                elif ratio < 0.5:
                    country.competition_pressure = "high"
                else:
                    country.competition_pressure = "extreme"
            else:
                # Fallback to inverse trial count if no pool data
                country.competition_pressure = "unknown"

        # Log summary
        with_ratio = [c for c in countries if c.competition_ratio is not None]
        if with_ratio:
            avg_ratio = sum(c.competition_ratio for c in with_ratio) / len(with_ratio)
            logger.info(
                f"Competition metrics applied: {len(with_ratio)} countries, "
                f"avg ratio={avg_ratio:.4f} ({avg_ratio*100:.2f}%), "
                f"{countries_with_real_data} with real CT.gov enrollment data, "
                f"{countries_with_fallback} using fallback"
            )

    async def _add_ai_analysis(
        self,
        countries: List[CountryRecord],
        criteria: ProtocolCriteria,
        worldbank_data: Optional[Dict[str, CountryIndicators]] = None,
    ) -> List[CountryRecord]:
        """
        Add AI-generated prevalence analysis and explanations of data-driven scores.

        Uses GPT-4o to:
        - Assess disease prevalence for this protocol
        - EXPLAIN the World Bank data-driven regulatory scores (not generate them)
        - Provide context on infrastructure readiness
        - Fall back to AI-generated regulatory scores only if no WB data available

        Batches countries (5 per batch) to stay within token limits.
        """
        if not self.openai or not countries:
            return countries

        worldbank_data = worldbank_data or {}

        # Limit to top 20 countries for analysis
        countries_to_analyze = countries[:20]

        # Batch countries (5 per batch for detailed analysis)
        BATCH_SIZE = 5
        batches = [countries_to_analyze[i:i + BATCH_SIZE]
                   for i in range(0, len(countries_to_analyze), BATCH_SIZE)]

        logger.info(f"AI analysis: {len(countries_to_analyze)} countries in {len(batches)} batches")

        # Collect all AI results
        all_ai_results: Dict[str, dict] = {}

        for batch_idx, batch in enumerate(batches):
            batch_results = await self._analyze_country_batch(
                batch=batch,
                criteria=criteria,
                worldbank_data=worldbank_data,
                batch_num=batch_idx + 1,
                total_batches=len(batches),
            )
            all_ai_results.update(batch_results)

        # Apply AI results to countries
        for country in countries:
            ai_info = all_ai_results.get(country.country_name.lower())
            if ai_info:
                # Update prevalence score and text if AI provided one
                ai_prev_score = ai_info.get("prevalence_score")
                if ai_prev_score is not None and country.prevalence_score is None:
                    country.prevalence_score = ai_prev_score
                    country.prevalence_missing = False  # AI provided a score
                country.prevalence_estimate = ai_info.get("prevalence_estimate")
                country.regulatory_summary = ai_info.get("regulatory_summary")

                # Only use AI regulatory_score if no World Bank data
                wb = worldbank_data.get(country.country_code.upper())
                if not wb or wb.get_composite_regulatory_score() is None:
                    ai_reg_score = ai_info.get("regulatory_score")
                    if ai_reg_score is not None:
                        # Store AI base score and apply GBT bonus if applicable
                        country.regulatory_base_score = ai_reg_score
                        gbt_bonus = country.regulatory_gbt_bonus or 0
                        country.regulatory_score = min(100.0, ai_reg_score + gbt_bonus)
                        country.regulatory_missing = False  # AI provided a score
                        logger.info(
                            f"Country {country.country_code}: AI regulatory score {ai_reg_score}"
                            + (f" + {country.regulatory_gbt_tier} bonus +{gbt_bonus}" if gbt_bonus > 0 else "")
                        )

        logger.info(f"AI analysis added for {len(all_ai_results)} countries")
        return countries

    async def _analyze_country_batch(
        self,
        batch: List[CountryRecord],
        criteria: ProtocolCriteria,
        worldbank_data: Dict[str, CountryIndicators],
        batch_num: int,
        total_batches: int,
    ) -> Dict[str, dict]:
        """Analyze a batch of countries with GPT-4o."""

        # Build country info with World Bank data for context
        country_info_lines = []
        for c in batch:
            wb = worldbank_data.get(c.country_code.upper())
            if wb and wb.regulatory_quality_raw is not None:
                # Has World Bank data - include in context
                line = (
                    f"- {c.country_name}: Regulatory Quality Index={wb.regulatory_quality_raw:.2f} "
                    f"(normalized: {wb.regulatory_quality:.0f}/100), "
                    f"Physicians/1k={wb.physician_density_raw or 'N/A'}, "
                    f"Logistics Index={wb.logistics_index_raw or 'N/A'}, "
                    f"Health Exp={wb.health_expenditure_raw or 'N/A'}% GDP"
                )
            else:
                # No World Bank data
                line = f"- {c.country_name}: No World Bank regulatory data available"
            country_info_lines.append(line)

        country_context = "\n".join(country_info_lines)

        # Build protocol context from criteria (safe access patterns)
        indication = criteria.indication or "Unknown indication"
        therapeutic_area = criteria.therapeutic_area or "Unknown therapeutic area"
        indication_detail = criteria.indication_detail or indication
        phase = criteria.phase or "Not specified"
        enrollment_target = criteria.enrollment_target
        patients_per_site = criteria.patients_per_site

        # Build capability requirements section
        capability_flags = []
        if criteria.requires_infusion:
            capability_flags.append("IV infusion capability")
        if criteria.requires_endoscopy:
            capability_flags.append("Endoscopy")
        if criteria.requires_biopsy:
            capability_flags.append("Biopsy procedures")
        if criteria.ecg_required:
            capability_flags.append("ECG")
        if criteria.requires_imaging:
            capability_flags.extend(criteria.requires_imaging[:3])

        # Truncate lists for prompt efficiency
        procedures = criteria.procedures[:10] if criteria.procedures else []
        equipment = criteria.required_equipment[:5] if criteria.required_equipment else []
        storage = criteria.storage_requirements[:3] if criteria.storage_requirements else []
        inclusion = criteria.inclusion_criteria[:5] if criteria.inclusion_criteria else []
        num_exclusion_criteria = len(criteria.exclusion_criteria) if criteria.exclusion_criteria else 0

        # Drug administration context
        dose_route = criteria.dose_and_route or "Not specified"
        dosing_freq = criteria.dosing_frequency or "Not specified"
        treatment_duration = criteria.treatment_duration or criteria.total_duration or "Not specified"

        # Build the protocol requirements section
        protocol_context = f"""
=== PROTOCOL REQUIREMENTS ===
This is a {phase} study in {indication_detail} ({therapeutic_area}).

Study Design:
- Phase: {phase}
- Enrollment Target: {enrollment_target or 'Not specified'} patients total
- Patients per Site: {patients_per_site or 'Not specified'}
- Treatment Duration: {treatment_duration}

Drug Administration:
- Dose/Route: {dose_route}
- Frequency: {dosing_freq}

Required Capabilities: {', '.join(capability_flags) if capability_flags else 'Standard clinical trial capabilities'}
Required Equipment: {', '.join(equipment) if equipment else 'Not specified'}
Required Procedures: {', '.join(procedures) if procedures else 'Standard assessments'}
Storage Requirements: {', '.join(storage) if storage else 'Standard storage'}

Eligibility Criteria Complexity:
- {len(inclusion)} inclusion criteria
- {num_exclusion_criteria} exclusion criteria ({"narrow patient pool" if num_exclusion_criteria > 15 else "moderate" if num_exclusion_criteria > 8 else "broad patient pool"})
"""

        prompt = f"""Analyze country feasibility for THIS SPECIFIC clinical trial.

{protocol_context}

=== WORLD BANK REGULATORY/INFRASTRUCTURE DATA ===
{country_context}

=== YOUR TASKS ===

For EACH of the {len(batch)} countries above:

1. **regulatory_summary** (2-3 sentences): EXPLAIN the regulatory readiness based on:
   - The World Bank data shown (reference the specific numbers!)
   - How the regulatory environment applies to {phase} {therapeutic_area} trials
   - Infrastructure implications for {', '.join(capability_flags) if capability_flags else 'standard procedures'}
   Example: "With a Regulatory Quality Index of 1.82 (92/100 normalized) and 4.1 physicians per 1,000,
   the US has strong infrastructure for IBD trials requiring endoscopy..."

2. **prevalence_score** (0-100): Estimate recruitment feasibility for {indication}
   - 90-100: Large patient pool, easy enrollment
   - 70-89: Good patient access
   - 50-69: Limited patient pool
   - Below 50: Difficult recruitment

3. **prevalence_estimate** (2-3 sentences): Explain the prevalence/recruitment situation
   - Reference disease epidemiology for {indication}
   - Consider the {num_exclusion_criteria} exclusion criteria impact

4. **regulatory_score** (0-100): ONLY provide if no World Bank data shown for that country.
   For countries WITH World Bank data, omit this field (the score is already calculated from real data).

Return a JSON object with a "countries" array containing EXACTLY {len(batch)} entries:
{{"countries": [
  {{"country": "Country Name", "prevalence_score": 75, "regulatory_summary": "With a Regulatory Quality Index of X.XX...", "prevalence_estimate": "The {indication} prevalence..."}}
]}}

CRITICAL: Return analysis for ALL {len(batch)} countries. Do not truncate."""

        logger.info(f"Batch {batch_num}/{total_batches}: Analyzing {len(batch)} countries")

        try:
            response = self.openai.create_json_completion(
                prompt=prompt,
                system_message=(
                    "You are a clinical trial feasibility expert with knowledge of "
                    "global regulatory environments and disease epidemiology. "
                    "When World Bank data is provided, reference those specific numbers in your explanations. "
                    "Provide data-driven assessments, not vague opinions. "
                    "IMPORTANT: You MUST analyze ALL countries requested."
                ),
                temperature=0.2,
                max_tokens=3000,  # Increased for complete analysis
            )

            # Handle both array and object responses
            if isinstance(response, dict) and "countries" in response:
                ai_data = response["countries"]
            elif isinstance(response, list):
                ai_data = response
            else:
                ai_data = [response] if response else []

            # Map AI results by country name (lowercase for matching)
            ai_map = {item.get("country", "").lower(): item for item in ai_data if isinstance(item, dict)}

            logger.info(f"Batch {batch_num}/{total_batches}: Received {len(ai_map)}/{len(batch)} countries")

            if len(ai_map) < len(batch):
                missing = [c.country_name for c in batch if c.country_name.lower() not in ai_map]
                logger.warning(f"Batch {batch_num}: Missing countries: {missing}")

            return ai_map

        except Exception as e:
            logger.error(f"Batch {batch_num}: AI analysis failed: {e}")
            return {}

    async def get_country_details(
        self,
        country_code: str,
        criteria: ProtocolCriteria
    ) -> Optional[CountryRecord]:
        """
        Get detailed information for a specific country.

        Args:
            country_code: ISO country code
            criteria: Protocol criteria for context

        Returns:
            CountryRecord with full details
        """
        # Get country summary
        countries = await self.ctgov.get_country_summary(
            condition=criteria.indication,
            phase=criteria.get_phase_filter(),
        )

        # Find matching country
        for country in countries:
            if country.country_code.upper() == country_code.upper():
                # Calculate scores
                scored = self._calculate_scores([country])
                if scored:
                    # Add AI analysis
                    if self.openai:
                        scored = await self._add_ai_analysis(
                            scored,
                            criteria.indication,
                            criteria.therapeutic_area,
                        )
                        scored = self._recalculate_composite(scored)
                    return scored[0]

        return None

    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """
        Update scoring weights.

        Args:
            new_weights: Dict with weight updates
        """
        if "trial_experience" in new_weights:
            self.weights.trial_experience = new_weights["trial_experience"]
        if "site_density" in new_weights:
            self.weights.site_density = new_weights["site_density"]
        if "competition" in new_weights:
            self.weights.competition = new_weights["competition"]
        if "regulatory" in new_weights:
            self.weights.regulatory = new_weights["regulatory"]
        if "prevalence" in new_weights:
            self.weights.prevalence = new_weights["prevalence"]

        if not self.weights.validate():
            logger.warning("Weights do not sum to 1.0, scores may be skewed")
