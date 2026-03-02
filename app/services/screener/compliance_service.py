"""
Compliance Data Ingestion Service for SiteSync Screener.

Provides identity resolution via NPI, OIG exclusion checks, and FDA inspection lookups.

Data Sources:
- NPPES Registry: https://npiregistry.cms.hhs.gov/api/
- OIG LEIE: https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv
- openFDA: https://api.fda.gov/
"""

import asyncio
import re
import csv
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

# API URLs
NPPES_API_URL = "https://npiregistry.cms.hhs.gov/api/"
OIG_LEIE_CSV_URL = "https://oig.hhs.gov/exclusions/downloadables/UPDATED.csv"
FDA_INSPECTIONS_API_URL = "https://api.fda.gov/other/inspectionresults.json"

# Rate limiting
NPPES_RATE_LIMIT_DELAY = 0.5  # 500ms between NPPES calls
FDA_RATE_LIMIT_DELAY = 0.25   # 250ms between FDA calls (240/min allowed)

# OIG LEIE cache (module-level)
_oig_leie_cache: Optional[List[Dict[str, Any]]] = None
_oig_leie_cache_time: Optional[datetime] = None
OIG_CACHE_TTL_HOURS = 24


# =============================================================================
# NPI Utilities
# =============================================================================

def clean_npi(npi_string: Optional[str]) -> Optional[str]:
    """
    Clean and validate an NPI string.

    - Strips whitespace
    - Removes trailing ".0" (common from Excel/CSV imports)
    - Validates exactly 10 digits

    Args:
        npi_string: Raw NPI string (e.g., "1023088630.0")

    Returns:
        Cleaned 10-digit NPI string, or None if invalid
    """
    if not npi_string:
        return None

    # Convert to string and strip whitespace
    npi = str(npi_string).strip()

    # Remove trailing .0 (from float conversion)
    if npi.endswith('.0'):
        npi = npi[:-2]

    # Remove any remaining decimal points
    npi = npi.split('.')[0]

    # Validate: must be exactly 10 digits
    if not re.match(r'^\d{10}$', npi):
        logger.debug(f"Invalid NPI format: {npi_string}")
        return None

    return npi


def parse_pi_name(full_name: str) -> Tuple[str, str]:
    """
    Parse a PI name into first and last name components.

    Handles formats:
    - "First Last" -> ("First", "Last")
    - "First M. Last" -> ("First", "Last")
    - "Last, First" -> ("First", "Last")
    - "Dr. First Last" -> ("First", "Last")
    - "First Last, MD" -> ("First", "Last")

    Args:
        full_name: Full name string

    Returns:
        Tuple of (first_name, last_name)
    """
    if not full_name:
        return ("", "")

    # Remove common titles and suffixes
    name = re.sub(r'\b(Dr\.?|MD|PhD|DO|Prof\.?|Professor)\b', '', full_name, flags=re.IGNORECASE)
    name = re.sub(r'\b(Jr\.?|Sr\.?|III|IV|II)\b', '', name, flags=re.IGNORECASE)
    name = name.strip()

    # Handle "Last, First" format
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        last_name = parts[0]
        first_parts = parts[1].split() if len(parts) > 1 else []
        first_name = first_parts[0] if first_parts else ""
    else:
        # Handle "First [Middle] Last" format
        parts = name.split()
        if len(parts) >= 2:
            first_name = parts[0]
            last_name = parts[-1]
        elif len(parts) == 1:
            first_name = ""
            last_name = parts[0]
        else:
            first_name = ""
            last_name = ""

    return (first_name.strip(), last_name.strip())


# =============================================================================
# NPPES Lookup
# =============================================================================

async def lookup_npi(
    first_name: str,
    last_name: str,
    state: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Look up NPI from NPPES registry by name.

    Args:
        first_name: Provider's first name
        last_name: Provider's last name
        state: Optional 2-letter state code to narrow results

    Returns:
        Dict with NPI info if found:
        {
            "npi": "1234567890",
            "first_name": "John",
            "last_name": "Smith",
            "credential": "MD",
            "state": "CA",
            "taxonomy": "Internal Medicine"
        }
        Returns None if no match found
    """
    if not first_name or not last_name:
        return None

    try:
        params = {
            "version": "2.1",
            "first_name": first_name,
            "last_name": last_name,
            "enumeration_type": "NPI-1",  # Individual providers only
            "limit": 10,
        }

        if state:
            params["state"] = state

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(NPPES_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

        result_count = data.get("result_count", 0)
        if result_count == 0:
            logger.debug(f"No NPPES results for {first_name} {last_name}")
            return None

        results = data.get("results", [])

        # If state provided, prefer exact match
        if state:
            for result in results:
                addresses = result.get("addresses", [])
                for addr in addresses:
                    if addr.get("state") == state:
                        return _format_nppes_result(result)

        # Return first result
        if results:
            return _format_nppes_result(results[0])

        return None

    except httpx.TimeoutException:
        logger.warning(f"NPPES timeout for {first_name} {last_name}")
        return None
    except Exception as e:
        logger.error(f"NPPES lookup error for {first_name} {last_name}: {e}")
        return None


def _format_nppes_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Format NPPES API result into standardized dict."""
    basic = result.get("basic", {})
    addresses = result.get("addresses", [])
    taxonomies = result.get("taxonomies", [])

    # Get primary state from location address
    state = None
    for addr in addresses:
        if addr.get("address_purpose") == "LOCATION":
            state = addr.get("state")
            break
    if not state and addresses:
        state = addresses[0].get("state")

    # Get primary taxonomy description
    taxonomy = None
    for tax in taxonomies:
        if tax.get("primary"):
            taxonomy = tax.get("desc")
            break
    if not taxonomy and taxonomies:
        taxonomy = taxonomies[0].get("desc")

    return {
        "npi": result.get("number"),
        "first_name": basic.get("first_name", ""),
        "last_name": basic.get("last_name", ""),
        "credential": basic.get("credential", ""),
        "state": state,
        "taxonomy": taxonomy,
    }


async def batch_npi_resolution(
    sites: List[Dict[str, Any]],
    project_id: int
) -> Dict[str, Any]:
    """
    Resolve NPIs for multiple sites.

    For each site:
    1. If NPI exists in citeline_data, clean it
    2. If no NPI, attempt NPPES lookup using PI name

    Args:
        sites: List of site dicts with data_sources
        project_id: Project ID for logging

    Returns:
        {
            "total_sites": N,
            "npi_from_citeline": N,
            "npi_from_nppes": N,
            "npi_not_found": N,
            "results": [{ "site_id": ..., "npi": ..., "source": ... }, ...]
        }
    """
    summary = {
        "total_sites": len(sites),
        "npi_from_citeline": 0,
        "npi_from_nppes": 0,
        "npi_not_found": 0,
        "results": [],
    }

    for site in sites:
        site_id = site.get("site_id")
        data_sources = site.get("data_sources", {}) or {}
        citeline_data = data_sources.get("citeline_data", {}) or {}
        citeline_enrichment = data_sources.get("citeline_enrichment", {}) or {}
        citeline_pi_discovery = data_sources.get("citeline_pi_discovery", {}) or {}

        result = {
            "site_id": site_id,
            "npi": None,
            "source": None,
        }

        # Check for existing NPI in Citeline data (multiple locations)
        raw_npi = (
            citeline_data.get("npi") or
            citeline_enrichment.get("npi") or
            citeline_pi_discovery.get("npi")
        )
        if raw_npi:
            cleaned_npi = clean_npi(raw_npi)
            if cleaned_npi:
                result["npi"] = cleaned_npi
                result["source"] = "citeline"
                summary["npi_from_citeline"] += 1
                summary["results"].append(result)
                continue

        # Try to get PI name for NPPES lookup (check multiple sources)
        pi_name = (
            citeline_data.get("pi_name") or
            citeline_enrichment.get("pi_name") or
            citeline_pi_discovery.get("pi_name")
        )
        if not pi_name:
            # Check investigators array
            investigators = site.get("investigators", [])
            if investigators and investigators[0].get("name"):
                pi_name = investigators[0]["name"]

        if pi_name:
            first_name, last_name = parse_pi_name(pi_name)
            if first_name and last_name:
                # Get state from site
                state = site.get("state")

                # Rate limit
                await asyncio.sleep(NPPES_RATE_LIMIT_DELAY)

                # NPPES lookup
                nppes_result = await lookup_npi(first_name, last_name, state)

                if nppes_result and nppes_result.get("npi"):
                    result["npi"] = nppes_result["npi"]
                    result["source"] = "nppes_lookup"
                    result["nppes_data"] = nppes_result
                    summary["npi_from_nppes"] += 1
                    summary["results"].append(result)
                    continue

        # No NPI found
        summary["npi_not_found"] += 1
        summary["results"].append(result)

    logger.info(
        f"NPI resolution for project {project_id}: "
        f"{summary['npi_from_citeline']} from Citeline, "
        f"{summary['npi_from_nppes']} from NPPES, "
        f"{summary['npi_not_found']} not found"
    )

    return summary


# =============================================================================
# OIG LEIE Exclusion Check
# =============================================================================

async def download_oig_leie() -> List[Dict[str, Any]]:
    """
    Download and parse OIG LEIE (List of Excluded Individuals/Entities).

    Uses module-level cache with 24-hour TTL.

    Returns:
        List of exclusion records with fields:
        - lastname, firstname, midname, state
        - excltype, excldate, reindate, waiverdate, wvrstate
    """
    global _oig_leie_cache, _oig_leie_cache_time

    # Check cache
    if _oig_leie_cache is not None and _oig_leie_cache_time is not None:
        cache_age = datetime.now() - _oig_leie_cache_time
        if cache_age < timedelta(hours=OIG_CACHE_TTL_HOURS):
            logger.debug(f"Using cached OIG LEIE data ({len(_oig_leie_cache)} records)")
            return _oig_leie_cache

    try:
        logger.info("Downloading OIG LEIE exclusion list...")

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(OIG_LEIE_CSV_URL)
            response.raise_for_status()

            # Parse CSV
            csv_content = response.text
            reader = csv.DictReader(io.StringIO(csv_content))

            records = []
            for row in reader:
                records.append({
                    "lastname": row.get("LASTNAME", "").strip().upper(),
                    "firstname": row.get("FIRSTNAME", "").strip().upper(),
                    "midname": row.get("MIDNAME", "").strip().upper(),
                    "state": row.get("STATE", "").strip().upper(),
                    "excltype": row.get("EXCLTYPE", "").strip(),
                    "excldate": row.get("EXCLDATE", "").strip(),
                    "reindate": row.get("REINDATE", "").strip(),
                    "waiverdate": row.get("WAIVERDATE", "").strip(),
                    "wvrstate": row.get("WVRSTATE", "").strip(),
                })

            # Update cache
            _oig_leie_cache = records
            _oig_leie_cache_time = datetime.now()

            logger.info(f"Downloaded OIG LEIE: {len(records)} exclusion records")
            return records

    except Exception as e:
        logger.error(f"Error downloading OIG LEIE: {e}")
        # Return cached data if available, even if stale
        if _oig_leie_cache is not None:
            logger.warning("Using stale OIG LEIE cache due to download error")
            return _oig_leie_cache
        return []


def check_oig_exclusion(
    first_name: str,
    last_name: str,
    leie_data: List[Dict[str, Any]],
    npi: Optional[str] = None,
    state: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Check if a person is on the OIG LEIE exclusion list.

    Args:
        first_name: First name to check
        last_name: Last name to check
        leie_data: Downloaded LEIE data
        npi: Optional NPI (not in LEIE, but kept for API consistency)
        state: Optional state for higher confidence matching

    Returns:
        Exclusion record if found:
        {
            "excluded": True,
            "exclusion_type": "...",
            "exclusion_date": "...",
            "reinstatement_date": "..." or None,
            "reinstated": True/False,
            "match_confidence": "high"|"medium",
            "matched_name": "LASTNAME, FIRSTNAME"
        }
        Returns None if no match
    """
    if not first_name or not last_name or not leie_data:
        return None

    first_upper = first_name.strip().upper()
    last_upper = last_name.strip().upper()
    state_upper = state.strip().upper() if state else None

    best_match = None
    best_confidence = None

    for record in leie_data:
        # Must match last name exactly
        if record["lastname"] != last_upper:
            continue

        rec_first = record["firstname"]
        rec_state = record["state"]

        # High confidence: exact first name + same state
        if rec_first == first_upper and rec_state == state_upper:
            best_match = record
            best_confidence = "high"
            break  # Can't do better than this

        # High confidence: exact first name, no state restriction
        if rec_first == first_upper:
            if best_confidence != "high":
                best_match = record
                best_confidence = "high" if not state_upper else "medium"

        # Medium confidence: first 3 chars match + same state
        if len(first_upper) >= 3 and len(rec_first) >= 3:
            if rec_first[:3] == first_upper[:3]:
                if rec_state == state_upper:
                    if best_confidence not in ("high",):
                        best_match = record
                        best_confidence = "medium"
                elif best_confidence not in ("high", "medium"):
                    best_match = record
                    best_confidence = "low"

    if best_match and best_confidence in ("high", "medium"):
        # Parse dates
        reindate = best_match["reindate"]
        is_reinstated = False
        if reindate:
            try:
                rein_dt = datetime.strptime(reindate, "%Y%m%d")
                if rein_dt < datetime.now():
                    is_reinstated = True
            except ValueError:
                pass

        return {
            "excluded": True,
            "exclusion_type": best_match["excltype"],
            "exclusion_date": best_match["excldate"],
            "reinstatement_date": reindate if reindate else None,
            "reinstated": is_reinstated,
            "match_confidence": best_confidence,
            "matched_name": f"{best_match['lastname']}, {best_match['firstname']}",
            "matched_state": best_match["state"],
        }

    return None


async def batch_oig_check(
    sites: List[Dict[str, Any]],
    project_id: int
) -> Dict[str, Any]:
    """
    Check OIG LEIE exclusions for multiple sites.

    Args:
        sites: List of site dicts with PI information
        project_id: Project ID for logging

    Returns:
        {
            "total_checked": N,
            "exclusions_found": N,
            "reinstated": N,
            "clean": N,
            "results": [{ "site_id": ..., "excluded": bool, ... }, ...],
            "excluded_sites": [{ "site_id": ..., "site_name": ..., "pi_name": ..., "exclusion_type": ..., "exclusion_date": ... }, ...]
        }
    """
    summary = {
        "total_checked": 0,
        "exclusions_found": 0,
        "reinstated": 0,
        "clean": 0,
        "results": [],
        "excluded_sites": [],  # List of excluded sites with details
    }

    # Download LEIE data once
    leie_data = await download_oig_leie()
    if not leie_data:
        logger.error("Could not download OIG LEIE data")
        return summary

    for site in sites:
        site_id = site.get("site_id")
        data_sources = site.get("data_sources", {}) or {}
        citeline_data = data_sources.get("citeline_data", {}) or {}
        compliance_data = data_sources.get("compliance_data", {}) or {}

        # Get PI name
        pi_name = citeline_data.get("pi_name")
        if not pi_name:
            investigators = site.get("investigators", [])
            if investigators and investigators[0].get("name"):
                pi_name = investigators[0]["name"]

        result = {
            "site_id": site_id,
            "pi_name": pi_name,
            "checked": True,
            "checked_at": datetime.utcnow().isoformat(),
        }

        if not pi_name:
            result["checked"] = False
            result["error"] = "No PI name available"
            summary["results"].append(result)
            continue

        summary["total_checked"] += 1

        first_name, last_name = parse_pi_name(pi_name)
        state = site.get("state")
        npi = compliance_data.get("npi")

        exclusion = check_oig_exclusion(
            first_name=first_name,
            last_name=last_name,
            leie_data=leie_data,
            npi=npi,
            state=state
        )

        if exclusion:
            result["excluded"] = True
            result["exclusion_type"] = exclusion["exclusion_type"]
            result["exclusion_date"] = exclusion["exclusion_date"]
            result["reinstatement_date"] = exclusion["reinstatement_date"]
            result["reinstated"] = exclusion["reinstated"]
            result["match_confidence"] = exclusion["match_confidence"]

            if exclusion["reinstated"]:
                summary["reinstated"] += 1
            else:
                summary["exclusions_found"] += 1
                # Add to excluded_sites list for easy frontend display
                summary["excluded_sites"].append({
                    "site_id": site_id,
                    "site_name": site.get("site_name", "Unknown Site"),
                    "pi_name": pi_name,
                    "exclusion_type": exclusion["exclusion_type"],
                    "exclusion_date": exclusion["exclusion_date"],
                    "match_confidence": exclusion["match_confidence"],
                })
        else:
            result["excluded"] = False
            summary["clean"] += 1

        summary["results"].append(result)

    logger.info(
        f"OIG check for project {project_id}: "
        f"{summary['exclusions_found']} excluded, "
        f"{summary['reinstated']} reinstated, "
        f"{summary['clean']} clean"
    )

    return summary


# =============================================================================
# FDA Inspection Lookup
# =============================================================================

async def lookup_fda_inspections(
    organization_name: str,
    state: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Look up FDA inspection history from openFDA.

    Args:
        organization_name: Organization/site name to search
        state: Optional state to narrow results

    Returns:
        List of inspection records:
        [
            {
                "legal_name": "...",
                "city": "...",
                "state": "...",
                "inspection_end_date": "...",
                "classification": "NAI"|"VAI"|"OAI",
                "project_area": "...",
                "posted_citations": int
            }
        ]
    """
    try:
        # Build search query
        search_query = f'legal_name:"{organization_name}"'
        if state:
            search_query += f' AND state:"{state}"'

        params = {
            "search": search_query,
            "limit": 20,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(FDA_INSPECTIONS_API_URL, params=params)

            if response.status_code == 404:
                # No results
                return []

            response.raise_for_status()
            data = response.json()

        results = data.get("results", [])

        inspections = []
        for r in results:
            inspections.append({
                "legal_name": r.get("legal_name", ""),
                "city": r.get("city", ""),
                "state": r.get("state", ""),
                "inspection_end_date": r.get("inspection_end_date", ""),
                "classification": r.get("classification", ""),
                "project_area": r.get("project_area", ""),
                "posted_citations": r.get("posted_citations", 0),
            })

        # Sort by date descending
        inspections.sort(key=lambda x: x["inspection_end_date"], reverse=True)

        return inspections

    except httpx.TimeoutException:
        logger.warning(f"FDA API timeout for {organization_name}")
        return []
    except Exception as e:
        logger.error(f"FDA lookup error for {organization_name}: {e}")
        return []


async def batch_fda_inspections(
    sites: List[Dict[str, Any]],
    project_id: int
) -> Dict[str, Any]:
    """
    Look up FDA inspections for multiple sites.

    Args:
        sites: List of site dicts
        project_id: Project ID for logging

    Returns:
        {
            "total_sites_checked": N,
            "sites_with_inspections": N,
            "total_inspections": N,
            "oai_found": N,  # Official Action Indicated (serious)
            "results": [{ "site_id": ..., "inspections": [...], ... }, ...]
        }
    """
    summary = {
        "total_sites_checked": 0,
        "sites_with_inspections": 0,
        "total_inspections": 0,
        "oai_found": 0,
        "results": [],
    }

    for site in sites:
        site_id = site.get("site_id")
        site_name = site.get("site_name", "")
        state = site.get("state")

        result = {
            "site_id": site_id,
            "site_name": site_name,
            "checked": True,
            "checked_at": datetime.utcnow().isoformat(),
        }

        if not site_name:
            result["checked"] = False
            result["error"] = "No site name"
            summary["results"].append(result)
            continue

        summary["total_sites_checked"] += 1

        # Rate limit
        await asyncio.sleep(FDA_RATE_LIMIT_DELAY)

        inspections = await lookup_fda_inspections(site_name, state)

        if inspections:
            summary["sites_with_inspections"] += 1
            summary["total_inspections"] += len(inspections)

            # Count by classification
            nai_count = sum(1 for i in inspections if i["classification"] == "NAI")
            vai_count = sum(1 for i in inspections if i["classification"] == "VAI")
            oai_count = sum(1 for i in inspections if i["classification"] == "OAI")

            if oai_count > 0:
                summary["oai_found"] += 1

            result["inspections"] = inspections
            result["total_inspections"] = len(inspections)
            result["nai_count"] = nai_count
            result["vai_count"] = vai_count
            result["oai_count"] = oai_count
            result["most_recent_date"] = inspections[0]["inspection_end_date"] if inspections else None
        else:
            result["inspections"] = []
            result["total_inspections"] = 0
            result["nai_count"] = 0
            result["vai_count"] = 0
            result["oai_count"] = 0

        summary["results"].append(result)

    logger.info(
        f"FDA inspections for project {project_id}: "
        f"{summary['sites_with_inspections']}/{summary['total_sites_checked']} sites with inspections, "
        f"{summary['oai_found']} with OAI"
    )

    return summary


# =============================================================================
# Combined Compliance Check
# =============================================================================

async def run_all_compliance_checks(
    sites: List[Dict[str, Any]],
    project_id: int
) -> Dict[str, Any]:
    """
    Run all compliance checks in sequence: NPI resolution, OIG check, FDA inspections.

    Args:
        sites: List of site dicts
        project_id: Project ID

    Returns:
        Combined summary from all checks
    """
    results = {
        "project_id": project_id,
        "started_at": datetime.utcnow().isoformat(),
        "npi_resolution": None,
        "oig_check": None,
        "fda_inspections": None,
        "errors": [],
    }

    # Step 1: NPI Resolution
    try:
        npi_result = await batch_npi_resolution(sites, project_id)
        results["npi_resolution"] = {
            "status": "success",
            "total_sites": npi_result["total_sites"],
            "npi_from_citeline": npi_result["npi_from_citeline"],
            "npi_from_nppes": npi_result["npi_from_nppes"],
            "npi_not_found": npi_result["npi_not_found"],
        }
    except Exception as e:
        logger.error(f"NPI resolution failed: {e}")
        results["npi_resolution"] = {"status": "error", "error": str(e)}
        results["errors"].append(f"NPI resolution: {e}")

    # Step 2: OIG Check
    try:
        oig_result = await batch_oig_check(sites, project_id)
        results["oig_check"] = {
            "status": "success",
            "total_checked": oig_result["total_checked"],
            "exclusions_found": oig_result["exclusions_found"],
            "reinstated": oig_result["reinstated"],
            "clean": oig_result["clean"],
            "excluded_sites": oig_result.get("excluded_sites", []),  # Include excluded site details
        }
    except Exception as e:
        logger.error(f"OIG check failed: {e}")
        results["oig_check"] = {"status": "error", "error": str(e)}
        results["errors"].append(f"OIG check: {e}")

    # Step 3: FDA Inspections
    try:
        fda_result = await batch_fda_inspections(sites, project_id)
        results["fda_inspections"] = {
            "status": "success",
            "total_sites_checked": fda_result["total_sites_checked"],
            "sites_with_inspections": fda_result["sites_with_inspections"],
            "total_inspections": fda_result["total_inspections"],
            "oai_found": fda_result["oai_found"],
        }
    except Exception as e:
        logger.error(f"FDA inspections failed: {e}")
        results["fda_inspections"] = {"status": "error", "error": str(e)}
        results["errors"].append(f"FDA inspections: {e}")

    results["completed_at"] = datetime.utcnow().isoformat()

    return results
