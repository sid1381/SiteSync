"""
PubMed Publication Lookup Service for PI Research.

Uses NCBI E-utilities API to search for investigator publications.
API Documentation: https://www.ncbi.nlm.nih.gov/books/NBK25500/
"""

import asyncio
import re
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import httpx

logger = logging.getLogger(__name__)

# NCBI E-utilities base URLs
ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Rate limiting: NCBI allows 3 requests/second without API key, 10/second with key
RATE_LIMIT_DELAY = 0.35  # 350ms between requests for safety


def normalize_pi_name_for_pubmed(pi_name: str) -> str:
    """
    Convert PI name to PubMed author search format.

    PubMed author search works best with "LastName FirstInitial" format.

    Examples:
        "John Smith" -> "Smith J"
        "Jane M. Doe" -> "Doe JM"
        "Smith, John" -> "Smith J"
        "Dr. Jane Doe" -> "Doe J"
        "John A. Smith III" -> "Smith JA"
    """
    if not pi_name:
        return ""

    # Remove common titles and suffixes
    name = re.sub(r'\b(Dr\.?|MD|PhD|Prof\.?|Professor)\b', '', pi_name, flags=re.IGNORECASE)
    name = re.sub(r'\b(Jr\.?|Sr\.?|III|IV|II)\b', '', name, flags=re.IGNORECASE)
    name = name.strip()

    # Handle "Last, First" format
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        last_name = parts[0]
        first_parts = parts[1].split() if len(parts) > 1 else []
    else:
        # Handle "First Last" format
        parts = name.split()
        if len(parts) >= 2:
            last_name = parts[-1]
            first_parts = parts[:-1]
        elif len(parts) == 1:
            last_name = parts[0]
            first_parts = []
        else:
            return ""

    # Build initials from first/middle names
    initials = ''.join(p[0].upper() for p in first_parts if p)

    if initials:
        return f"{last_name} {initials}"
    return last_name


def build_pubmed_query(pi_name: str, specialty: Optional[str] = None, clinical_trials_only: bool = False) -> str:
    """
    Build a PubMed search query for a PI.

    Args:
        pi_name: PI name in any format
        specialty: Optional specialty to narrow search (e.g., "hepatology", "oncology")
        clinical_trials_only: If True, filter to clinical trial publications only

    Returns:
        PubMed query string
    """
    # Normalize name for author search
    author_name = normalize_pi_name_for_pubmed(pi_name)
    if not author_name:
        return ""

    # Build query parts
    query_parts = [f"{author_name}[Author]"]

    # Add specialty filter if provided
    if specialty:
        # Clean specialty for search
        specialty_clean = specialty.lower().strip()
        query_parts.append(f"({specialty_clean}[MeSH Terms] OR {specialty_clean}[Title/Abstract])")

    # Add clinical trials filter
    if clinical_trials_only:
        query_parts.append("(Clinical Trial[Publication Type] OR Randomized Controlled Trial[Publication Type])")

    return " AND ".join(query_parts)


async def search_pi_publications(
    pi_name: str,
    specialty: Optional[str] = None,
    max_results: int = 10,
    include_clinical_only: bool = False
) -> Dict[str, Any]:
    """
    Search PubMed for a PI's publications using NCBI E-utilities.

    Args:
        pi_name: PI's full name (any format)
        specialty: Optional specialty to filter results (e.g., "hepatology")
        max_results: Maximum number of recent papers to return details for
        include_clinical_only: If True, also search for clinical trial pubs specifically

    Returns:
        {
            "pi_name": str,
            "search_query": str,
            "total_publications": int,
            "clinical_trial_publications": int,
            "recent_papers": [
                {
                    "pmid": str,
                    "title": str,
                    "authors": str,
                    "journal": str,
                    "pub_date": str,
                    "pub_year": int,
                    "is_clinical_trial": bool
                }
            ],
            "search_success": bool,
            "error": str or None
        }
    """
    result = {
        "pi_name": pi_name,
        "search_query": "",
        "total_publications": 0,
        "total_publications_5y": 0,
        "clinical_trial_publications": 0,
        "clinical_trial_publications_5y": 0,
        "recent_papers": [],
        "search_success": False,
        "error": None
    }

    # Calculate 5-year date range for NCBI queries
    today = datetime.now()
    five_years_ago = today - timedelta(days=5*365)
    date_min = five_years_ago.strftime("%Y/%m/%d")
    date_max = today.strftime("%Y/%m/%d")

    if not pi_name or not pi_name.strip():
        result["error"] = "No PI name provided"
        return result

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Search for all publications
            all_pubs_query = build_pubmed_query(pi_name, specialty, clinical_trials_only=False)
            if not all_pubs_query:
                result["error"] = "Could not parse PI name"
                return result

            result["search_query"] = all_pubs_query

            # E-search for total count
            search_params = {
                "db": "pubmed",
                "term": all_pubs_query,
                "retmode": "json",
                "retmax": max_results,
                "sort": "pub_date"  # Most recent first
            }

            logger.info(f"PubMed search for PI '{pi_name}': {all_pubs_query}")

            response = await client.get(ESEARCH_URL, params=search_params)
            response.raise_for_status()
            search_data = response.json()

            esearch_result = search_data.get("esearchresult", {})
            total_count = int(esearch_result.get("count", 0))
            pmids = esearch_result.get("idlist", [])

            result["total_publications"] = total_count

            # Step 2: Search for all publications in last 5 years
            await asyncio.sleep(RATE_LIMIT_DELAY)

            search_params_5y = {
                "db": "pubmed",
                "term": all_pubs_query,
                "retmode": "json",
                "retmax": 0,  # Just need count
                "mindate": date_min,
                "maxdate": date_max,
                "datetype": "pdat"
            }

            response_5y = await client.get(ESEARCH_URL, params=search_params_5y)
            response_5y.raise_for_status()
            data_5y = response_5y.json()

            total_count_5y = int(data_5y.get("esearchresult", {}).get("count", 0))
            result["total_publications_5y"] = total_count_5y

            # Step 3: Search for clinical trial publications specifically (all-time)
            if include_clinical_only or True:  # Always get clinical trial count
                await asyncio.sleep(RATE_LIMIT_DELAY)

                clinical_query = build_pubmed_query(pi_name, specialty, clinical_trials_only=True)
                clinical_params = {
                    "db": "pubmed",
                    "term": clinical_query,
                    "retmode": "json",
                    "retmax": 0  # Just need count
                }

                clinical_response = await client.get(ESEARCH_URL, params=clinical_params)
                clinical_response.raise_for_status()
                clinical_data = clinical_response.json()

                clinical_count = int(clinical_data.get("esearchresult", {}).get("count", 0))
                result["clinical_trial_publications"] = clinical_count

            # Step 4: Search for clinical trial publications in last 5 years
            await asyncio.sleep(RATE_LIMIT_DELAY)

            clinical_params_5y = {
                "db": "pubmed",
                "term": clinical_query,
                "retmode": "json",
                "retmax": 0,
                "mindate": date_min,
                "maxdate": date_max,
                "datetype": "pdat"
            }

            clinical_response_5y = await client.get(ESEARCH_URL, params=clinical_params_5y)
            clinical_response_5y.raise_for_status()
            clinical_data_5y = clinical_response_5y.json()

            clinical_count_5y = int(clinical_data_5y.get("esearchresult", {}).get("count", 0))
            result["clinical_trial_publications_5y"] = clinical_count_5y

            # Step 5: Fetch summaries for recent papers
            if pmids:
                await asyncio.sleep(RATE_LIMIT_DELAY)

                summary_params = {
                    "db": "pubmed",
                    "id": ",".join(pmids),
                    "retmode": "json"
                }

                summary_response = await client.get(ESUMMARY_URL, params=summary_params)
                summary_response.raise_for_status()
                summary_data = summary_response.json()

                articles = summary_data.get("result", {})

                for pmid in pmids:
                    if pmid in articles and pmid != "uids":
                        article = articles[pmid]

                        # Parse publication date
                        pub_date = article.get("pubdate", "")
                        pub_year = None
                        if pub_date:
                            year_match = re.match(r"(\d{4})", pub_date)
                            if year_match:
                                pub_year = int(year_match.group(1))

                        # Check if clinical trial (from publication types)
                        pub_types = article.get("pubtype", [])
                        is_clinical = any(
                            "Clinical Trial" in pt or "Randomized" in pt
                            for pt in pub_types
                        )

                        # Format authors
                        authors = article.get("authors", [])
                        if authors:
                            author_names = [a.get("name", "") for a in authors[:3]]
                            authors_str = ", ".join(author_names)
                            if len(authors) > 3:
                                authors_str += f" et al. ({len(authors)} authors)"
                        else:
                            authors_str = "Authors not listed"

                        result["recent_papers"].append({
                            "pmid": pmid,
                            "title": article.get("title", ""),
                            "authors": authors_str,
                            "journal": article.get("source", ""),
                            "pub_date": pub_date,
                            "pub_year": pub_year,
                            "is_clinical_trial": is_clinical
                        })

            result["search_success"] = True
            logger.info(f"PubMed found {total_count} total ({total_count_5y} in 5y), {result['clinical_trial_publications']} clinical ({clinical_count_5y} in 5y) for {pi_name}")

    except httpx.TimeoutException:
        result["error"] = "PubMed request timed out"
        logger.warning(f"PubMed timeout for PI: {pi_name}")
    except httpx.HTTPStatusError as e:
        result["error"] = f"PubMed API error: {e.response.status_code}"
        logger.error(f"PubMed HTTP error for {pi_name}: {e}")
    except Exception as e:
        result["error"] = f"Search failed: {str(e)}"
        logger.error(f"PubMed search error for {pi_name}: {e}")

    return result


async def batch_search_publications(
    pi_list: List[Dict[str, str]],
    specialty: Optional[str] = None,
    max_results_per_pi: int = 10
) -> Dict[str, Any]:
    """
    Search PubMed for multiple PIs with rate limiting.

    Args:
        pi_list: List of PI dicts with at least 'name' key
            [{"name": "John Smith", "site_id": "123"}, ...]
        specialty: Optional specialty to filter all searches
        max_results_per_pi: Max recent papers per PI

    Returns:
        {
            "total_pis_searched": int,
            "successful_searches": int,
            "failed_searches": int,
            "results": {
                "pi_name": { ...search result... }
            },
            "summary": {
                "total_publications": int,
                "total_clinical_publications": int,
                "avg_publications_per_pi": float
            }
        }
    """
    results = {
        "total_pis_searched": len(pi_list),
        "successful_searches": 0,
        "failed_searches": 0,
        "results": {},
        "summary": {
            "total_publications": 0,
            "total_clinical_publications": 0,
            "avg_publications_per_pi": 0.0
        }
    }

    if not pi_list:
        return results

    # Process PIs sequentially with rate limiting
    for pi_info in pi_list:
        pi_name = pi_info.get("name", "")
        if not pi_name:
            continue

        # Rate limit between requests
        await asyncio.sleep(RATE_LIMIT_DELAY)

        # Search for this PI
        search_result = await search_pi_publications(
            pi_name=pi_name,
            specialty=specialty,
            max_results=max_results_per_pi
        )

        # Store result keyed by name
        results["results"][pi_name] = search_result

        if search_result["search_success"]:
            results["successful_searches"] += 1
            results["summary"]["total_publications"] += search_result["total_publications"]
            results["summary"]["total_clinical_publications"] += search_result["clinical_trial_publications"]
        else:
            results["failed_searches"] += 1

    # Calculate average
    if results["successful_searches"] > 0:
        results["summary"]["avg_publications_per_pi"] = (
            results["summary"]["total_publications"] / results["successful_searches"]
        )

    return results


async def enrich_site_with_pubmed(
    site_data: Dict[str, Any],
    specialty: Optional[str] = None
) -> Dict[str, Any]:
    """
    Enrich a site's investigator data with PubMed publication counts.

    Args:
        site_data: Site data dict containing investigators
        specialty: Optional specialty filter

    Returns:
        Updated site_data with pubmed_data added to each investigator
    """
    investigators = site_data.get("investigators", [])

    if not investigators:
        # Check for citeline_pi_discovery
        pi_discovery = site_data.get("citeline_pi_discovery")
        if pi_discovery and pi_discovery.get("name"):
            investigators = [{"name": pi_discovery["name"]}]

    if not investigators:
        return site_data

    # Build PI list
    pi_list = [{"name": inv.get("name", "")} for inv in investigators if inv.get("name")]

    # Batch search
    batch_results = await batch_search_publications(
        pi_list=pi_list,
        specialty=specialty,
        max_results_per_pi=10
    )

    # Enrich investigators with results
    for inv in site_data.get("investigators", []):
        pi_name = inv.get("name", "")
        if pi_name in batch_results["results"]:
            inv["pubmed_data"] = batch_results["results"][pi_name]

    # Add summary to site
    site_data["pubmed_summary"] = batch_results["summary"]
    site_data["pubmed_enriched"] = True

    return site_data
