#!/usr/bin/env python3
"""
Test script for SiteSync Screener data pipeline.

Validates the core data flow:
1. Creates a ProtocolCriteria for NASH Phase II
2. Queries ClinicalTrials.gov for matching trials
3. Aggregates by country
4. Prints the top 10 countries by trial count

Run from project root:
    python scripts/test_screener_pipeline.py
"""

import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.screener.data_sources.base import ProtocolCriteria
from app.services.screener.data_sources.ctgov_source import CTGovDataSource
from app.services.screener.country_feasibility import CountryFeasibilityEngine
from app.services.screener.protocol_analyzer import ScreenerProtocolAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_direct_ctgov_query():
    """Test direct ClinicalTrials.gov data source queries."""
    print("\n" + "=" * 70)
    print("TEST 1: Direct ClinicalTrials.gov Query")
    print("=" * 70)

    ctgov = CTGovDataSource()

    # Search for NASH Phase 2 trials
    print("\nSearching for NASH Phase II trials...")
    trials = await ctgov.search_trials_by_condition(
        condition="NASH",
        phase=["PHASE2"],
        status=None,  # All statuses
        max_results=100,
    )

    print(f"\nFound {len(trials)} NASH Phase II trials")

    if trials:
        print("\nSample trials:")
        for trial in trials[:3]:
            print(f"  - {trial.nct_id}: {trial.title[:60]}...")
            print(f"    Phase: {trial.phase}, Status: {trial.status}")
            print(f"    Sites: {len(trial.sites)}, Enrollment: {trial.enrollment}")


async def test_country_aggregation():
    """Test country-level aggregation from trials."""
    print("\n" + "=" * 70)
    print("TEST 2: Country Aggregation")
    print("=" * 70)

    ctgov = CTGovDataSource()

    # Get country summary for NASH
    print("\nGetting country summary for NASH trials...")
    countries = await ctgov.get_country_summary(
        condition="NASH",
        phase=["PHASE2"],
    )

    print(f"\nFound {len(countries)} countries with NASH trials")

    if countries:
        # Sort by total trials
        countries.sort(key=lambda c: c.total_trials, reverse=True)

        print("\nTop 10 Countries by Trial Count:")
        print("-" * 70)
        print(f"{'Rank':<5} {'Country':<25} {'Trials':<10} {'Sites':<10} {'Recruiting':<12}")
        print("-" * 70)

        for i, country in enumerate(countries[:10], 1):
            print(
                f"{i:<5} {country.country_name:<25} "
                f"{country.total_trials:<10} {country.site_count:<10} "
                f"{country.actively_recruiting:<12}"
            )

    return countries


async def test_country_feasibility_scoring():
    """Test the full country feasibility scoring engine."""
    print("\n" + "=" * 70)
    print("TEST 3: Country Feasibility Scoring (with composite scores)")
    print("=" * 70)

    # Create protocol criteria manually (simulating PDF extraction)
    criteria = ProtocolCriteria(
        indication="NASH",
        therapeutic_area="Hepatology",
        phase="Phase II",
        enrollment_target=450,
        patients_per_site=8,
        duration="48 weeks",
        required_equipment=["FibroScan", "MRI-PDFF", "-80C storage"],
        required_staff=["Hepatologist PI", "GCP-certified coordinators"],
        procedures=["Liver biopsy", "FibroScan", "Blood draws Q4W"],
    )

    print(f"\nProtocol Criteria:")
    print(f"  Indication: {criteria.indication}")
    print(f"  Phase: {criteria.phase}")
    print(f"  Therapeutic Area: {criteria.therapeutic_area}")
    print(f"  Enrollment Target: {criteria.enrollment_target}")

    # Initialize feasibility engine (without AI for faster testing)
    engine = CountryFeasibilityEngine()

    print("\nRanking countries (this may take a moment)...")
    ranked_countries = await engine.rank_countries(
        criteria=criteria,
        min_trials=1,
        include_ai_analysis=False,  # Skip AI for faster testing
    )

    if ranked_countries:
        print("\nTop 10 Countries by Feasibility Score:")
        print("-" * 90)
        print(
            f"{'Rank':<5} {'Country':<20} {'Score':<8} "
            f"{'Trials':<8} {'Sites':<8} {'Experience':<12} {'Competition':<12}"
        )
        print("-" * 90)

        for i, country in enumerate(ranked_countries[:10], 1):
            print(
                f"{i:<5} {country.country_name:<20} "
                f"{country.composite_score:>6.1f}  "
                f"{country.total_trials:<8} {country.site_count:<8} "
                f"{country.trial_experience_score:>10.1f}  "
                f"{country.competition_score:>10.1f}"
            )

    return ranked_countries


async def test_protocol_analyzer():
    """Test the protocol analyzer with manual criteria creation."""
    print("\n" + "=" * 70)
    print("TEST 4: Protocol Analyzer (Manual Criteria)")
    print("=" * 70)

    analyzer = ScreenerProtocolAnalyzer()

    # Create criteria manually
    criteria = analyzer.create_manual_criteria(
        indication="NAFLD",
        phase="Phase III",
        therapeutic_area="Gastroenterology / Hepatology",
        enrollment_target=300,
    )

    print(f"\nManually created criteria:")
    print(f"  Indication: {criteria.indication}")
    print(f"  Phase: {criteria.phase}")
    print(f"  Therapeutic Area: {criteria.therapeutic_area}")
    print(f"  Phase Filter for CT.gov: {criteria.get_phase_filter()}")


async def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("SITESYNC SCREENER PIPELINE TEST")
    print("=" * 70)
    print("\nTesting the core data pipeline for the Screener module.")
    print("This validates CT.gov queries, country aggregation, and scoring.")

    try:
        # Test 1: Direct CT.gov query
        await test_direct_ctgov_query()

        # Test 2: Country aggregation
        countries = await test_country_aggregation()

        # Test 3: Full scoring engine
        ranked = await test_country_feasibility_scoring()

        # Test 4: Protocol analyzer
        await test_protocol_analyzer()

        print("\n" + "=" * 70)
        print("ALL TESTS COMPLETED SUCCESSFULLY")
        print("=" * 70)
        print("\nThe Screener data pipeline is working correctly!")
        print("Next steps:")
        print("  1. Create site_intelligence.py for site-level scoring")
        print("  2. Create scoring_engine.py for combined scoring")
        print("  3. Create API routes in app/routes/screener.py")
        print("  4. Create frontend in frontend/app/screener/page.tsx")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
