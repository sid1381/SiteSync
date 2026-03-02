"""
Citeline Export Parser for SiteSync Screener

Handles two Citeline export formats:
1. SiteTrove — PI-centric (each row = one investigator)
   Key columns for MATCHING:
     - "Investigator First Name", "Investigator Last Name" (or "Investigator Name")
     - "City", "Organization Name"
     - "NPI Number" (US only, high-precision match)
   Key columns for ENRICHMENT:
     - "Investigator Tier" (Gold/Silver/Bronze)
     - "Total Trials" or "Matching Trials"
     - "Organization Type" (Academic, Community, etc.)
     - "Regulatory Actions" (count or list)
     - "Disease Areas" (semicolon-delimited)
     - "Specialties"

2. TrialTrove — Trial-centric (each row = one trial)
   Key columns for MATCHING:
     - "Protocol/Trial ID" — contains NCT IDs (e.g., "NCT03456789")
   Key columns for ENRICHMENT:
     - "Pts/Site/Mo" (patients per site per month — 61% coverage)
     - "Actual Accrual" (75% coverage)
     - "Trial Status", "Phase", "Sponsor"
     - "No. of Sites"

Auto-detection: SiteTrove exports have "Investigator" columns.
TrialTrove exports have "Protocol/Trial ID" and "Pts/Site/Mo" columns.
"""

import pandas as pd
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Optional rapidfuzz - fall back to difflib if not installed
try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False
    from difflib import SequenceMatcher
    logger.warning("rapidfuzz not installed, using difflib for fuzzy matching (slower)")


@dataclass
class CitelinePI:
    """Parsed PI record from SiteTrove export"""
    first_name: str
    last_name: str
    full_name: str
    city: str
    organization: str
    npi: Optional[str] = None
    tier: Optional[str] = None  # Gold/Silver/Bronze
    total_trials: int = 0
    matching_trials: int = 0
    org_type: Optional[str] = None
    regulatory_actions: int = 0
    disease_areas: List[str] = field(default_factory=list)
    specialties: List[str] = field(default_factory=list)
    raw_row: Optional[Dict] = None


@dataclass
class CitelineTrial:
    """Parsed trial record from TrialTrove export"""
    trial_id: str
    nct_ids: List[str]  # Extracted from Protocol/Trial ID
    phase: Optional[str] = None
    status: Optional[str] = None
    sponsor: Optional[str] = None
    pts_per_site_month: Optional[float] = None
    actual_accrual: Optional[int] = None
    num_sites: Optional[int] = None
    raw_row: Optional[Dict] = None


@dataclass
class CitelineMatchResult:
    """Result of matching Citeline data to CT.gov sites"""
    total_citeline_records: int
    matched_count: int
    unmatched_count: int
    new_pis_count: int  # PIs not in CT.gov at all
    match_details: List[Dict]  # Per-match info with confidence
    enrichment_summary: Dict  # What fields got enriched


def _fuzzy_ratio(s1: str, s2: str) -> float:
    """Fuzzy string similarity ratio using rapidfuzz or difflib fallback"""
    if RAPIDFUZZ_AVAILABLE:
        return fuzz.ratio(s1, s2)
    else:
        return SequenceMatcher(None, s1, s2).ratio() * 100


def _fuzzy_token_sort_ratio(s1: str, s2: str) -> float:
    """Token-sorted fuzzy similarity (handles name inversions)"""
    if RAPIDFUZZ_AVAILABLE:
        return fuzz.token_sort_ratio(s1, s2)
    else:
        # Simple token sort fallback
        tokens1 = sorted(s1.lower().split())
        tokens2 = sorted(s2.lower().split())
        return SequenceMatcher(None, ' '.join(tokens1), ' '.join(tokens2)).ratio() * 100


def normalize_pi_name(name: str) -> str:
    """
    Convert PI name from "Last, First MI" format to "First MI Last" format.

    Examples:
        "Williams, David K" → "David K Williams"
        "Smith, Jane Marie" → "Jane Marie Smith"
        "Jones, Robert" → "Robert Jones"
        "David Williams" → "David Williams" (unchanged, no comma)
    """
    if not name or ',' not in name:
        return name.strip() if name else ''

    parts = name.split(',', 1)  # Split on first comma only
    if len(parts) != 2:
        return name.strip()

    last = parts[0].strip()
    first = parts[1].strip()

    if not first or not last:
        return name.strip()

    return f"{first} {last}"


def detect_export_type(df: pd.DataFrame) -> str:
    """
    Auto-detect whether this is SiteTrove or TrialTrove.

    SiteTrove indicators (investigator-centric):
    - "Investigator Full Name" or similar investigator columns
    - "NPI Number" or NPI-related columns
    - PI-specific fields like "PI City", "PI Tier"

    TrialTrove indicators (trial-centric, WITHOUT investigator columns):
    - "Trial Phase", "Trial Status", "Enrollment"
    - Protocol/trial IDs without investigator columns
    """
    cols_lower = [c.lower() for c in df.columns]
    cols_set = set(cols_lower)

    # Strong SiteTrove indicators - investigator-specific columns
    sitetrove_strong = any(
        k in cols_set for k in [
            'investigator full name',
            'npi number',
            'pi full name',
            'investigator first name',
            'investigator last name',
        ]
    )

    # Additional SiteTrove signals
    sitetrove_signals = sum(1 for c in cols_lower
                           if any(k in c for k in ['investigator', 'npi', 'pi ', 'pi_', 'tier']))

    # Strong TrialTrove indicators - trial-specific columns
    trialtrove_strong = any(
        k in cols_set for k in [
            'trial phase',
            'trial status',
            'enrollment',
            'trial id',
        ]
    )

    # Additional TrialTrove signals
    trialtrove_signals = sum(1 for c in cols_lower
                            if any(k in c for k in ['protocol', 'pts/site', 'accrual', 'trial id', 'trial status', 'enrollment']))

    # Decision logic: SiteTrove if it has investigator columns
    # TrialTrove only if it has trial columns WITHOUT investigator columns
    if sitetrove_strong:
        return 'sitetrove'
    elif trialtrove_strong and sitetrove_signals == 0:
        return 'trialtrove'
    elif sitetrove_signals > trialtrove_signals:
        return 'sitetrove'
    elif trialtrove_signals > sitetrove_signals:
        return 'trialtrove'
    else:
        raise ValueError(
            f"Cannot determine export type. Found {sitetrove_signals} SiteTrove "
            f"and {trialtrove_signals} TrialTrove column indicators. "
            f"Columns: {list(df.columns[:20])}"
        )


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Flexibly find a column by trying multiple possible names"""
    cols_lower = {c.lower().strip(): c for c in df.columns}
    for candidate in candidates:
        if candidate.lower() in cols_lower:
            return cols_lower[candidate.lower()]
        # Partial match
        for col_lower, col_original in cols_lower.items():
            if candidate.lower() in col_lower:
                return col_original
    return None


def parse_sitetrove(df: pd.DataFrame) -> List[CitelinePI]:
    """Parse a SiteTrove export into structured PI records"""
    pis = []

    # Flexible column detection
    name_col = _find_column(df, ['Investigator Name', 'Name', 'PI Name', 'Investigator'])
    first_col = _find_column(df, ['Investigator First Name', 'First Name'])
    last_col = _find_column(df, ['Investigator Last Name', 'Last Name'])
    city_col = _find_column(df, ['City', 'Investigator City', 'Organization City'])
    org_col = _find_column(df, ['Organization Name', 'Organization', 'Site Name', 'Institution'])
    npi_col = _find_column(df, ['NPI Number', 'NPI', 'National Provider Identifier'])
    tier_col = _find_column(df, ['Investigator Tier', 'Tier', 'PI Tier'])
    trials_col = _find_column(df, ['Total Trials', 'Total Matching Trials', 'Trial Count', 'Matching Trials'])
    org_type_col = _find_column(df, ['Organization Type', 'Org Type', 'Site Type', 'Institution Type'])
    reg_col = _find_column(df, ['Regulatory Actions', 'FDA Actions', 'Compliance Issues'])
    disease_col = _find_column(df, ['Disease Areas', 'Therapeutic Areas', 'Indications'])
    spec_col = _find_column(df, ['Specialties', 'Specialty', 'Medical Specialty'])

    if not (name_col or (first_col and last_col)):
        raise ValueError(f"Cannot find investigator name columns. Available: {list(df.columns)}")
    if not city_col:
        raise ValueError(f"Cannot find city column. Available: {list(df.columns)}")

    for _, row in df.iterrows():
        try:
            # Build name
            if first_col and last_col:
                first = str(row.get(first_col, '')).strip()
                last = str(row.get(last_col, '')).strip()
                full = f"{first} {last}"
            else:
                raw_full = str(row.get(name_col, '')).strip()
                full = normalize_pi_name(raw_full)  # Convert "Last, First MI" → "First MI Last"
                parts = full.split()
                first = parts[0] if parts else ''
                last = parts[-1] if len(parts) > 1 else ''

            if not full or full == 'nan':
                continue

            city = str(row.get(city_col, '')).strip()
            org = str(row.get(org_col, '')).strip() if org_col else ''

            # Parse disease areas (semicolon or comma delimited)
            diseases = []
            if disease_col and pd.notna(row.get(disease_col)):
                raw = str(row[disease_col])
                diseases = [d.strip() for d in re.split(r'[;,]', raw) if d.strip()]

            specialties = []
            if spec_col and pd.notna(row.get(spec_col)):
                raw = str(row[spec_col])
                specialties = [s.strip() for s in re.split(r'[;,]', raw) if s.strip()]

            # Parse regulatory actions count
            reg_count = 0
            if reg_col and pd.notna(row.get(reg_col)):
                val = str(row[reg_col]).strip()
                if val.isdigit():
                    reg_count = int(val)
                elif val.lower() not in ('none', 'n/a', '', 'nan'):
                    reg_count = len(re.split(r'[;,]', val))

            pi = CitelinePI(
                first_name=first,
                last_name=last,
                full_name=full,
                city=city if city != 'nan' else '',
                organization=org if org != 'nan' else '',
                npi=str(row[npi_col]).strip() if npi_col and pd.notna(row.get(npi_col)) else None,
                tier=str(row[tier_col]).strip() if tier_col and pd.notna(row.get(tier_col)) else None,
                total_trials=int(row[trials_col]) if trials_col and pd.notna(row.get(trials_col)) else 0,
                org_type=str(row[org_type_col]).strip() if org_type_col and pd.notna(row.get(org_type_col)) else None,
                regulatory_actions=reg_count,
                disease_areas=diseases,
                specialties=specialties,
                raw_row=row.to_dict()
            )
            pis.append(pi)
        except Exception as e:
            logger.warning(f"Skipping row: {e}")
            continue

    logger.info(f"Parsed {len(pis)} PIs from SiteTrove export ({len(df)} rows)")
    return pis


def parse_trialtrove(df: pd.DataFrame) -> List[CitelineTrial]:
    """Parse a TrialTrove export into structured trial records"""
    trials = []

    id_col = _find_column(df, ['Protocol/Trial ID', 'Trial ID', 'Protocol ID', 'Study ID'])
    phase_col = _find_column(df, ['Phase', 'Trial Phase', 'Study Phase'])
    status_col = _find_column(df, ['Status', 'Trial Status', 'Study Status'])
    sponsor_col = _find_column(df, ['Sponsor', 'Sponsor/Collaborator', 'Lead Sponsor'])
    pts_col = _find_column(df, ['Pts/Site/Mo', 'Patients/Site/Month', 'Pts Per Site Per Month'])
    accrual_col = _find_column(df, ['Actual Accrual', 'Total Accrual', 'Enrollment'])
    sites_col = _find_column(df, ['No. of Sites', 'Number of Sites', 'Sites', 'Site Count'])

    if not id_col:
        raise ValueError(f"Cannot find trial ID column. Available: {list(df.columns)}")

    for _, row in df.iterrows():
        try:
            trial_id_raw = str(row.get(id_col, '')).strip()
            if not trial_id_raw or trial_id_raw == 'nan':
                continue

            # Extract NCT IDs from the Protocol/Trial ID field
            # Common formats: "NCT03456789", "NCT03456789; NCT03456790",
            # or embedded like "CTJ301UC201 (NCT03456789)"
            nct_ids = re.findall(r'NCT\d{7,8}', trial_id_raw, re.IGNORECASE)

            # Parse pts/site/month (might be float or string)
            pts_sm = None
            if pts_col and pd.notna(row.get(pts_col)):
                try:
                    pts_sm = float(str(row[pts_col]).replace(',', ''))
                except ValueError:
                    pass

            accrual = None
            if accrual_col and pd.notna(row.get(accrual_col)):
                try:
                    accrual = int(float(str(row[accrual_col]).replace(',', '')))
                except ValueError:
                    pass

            num_sites = None
            if sites_col and pd.notna(row.get(sites_col)):
                try:
                    num_sites = int(float(str(row[sites_col]).replace(',', '')))
                except ValueError:
                    pass

            trial = CitelineTrial(
                trial_id=trial_id_raw,
                nct_ids=nct_ids,
                phase=str(row[phase_col]).strip() if phase_col and pd.notna(row.get(phase_col)) else None,
                status=str(row[status_col]).strip() if status_col and pd.notna(row.get(status_col)) else None,
                sponsor=str(row[sponsor_col]).strip() if sponsor_col and pd.notna(row.get(sponsor_col)) else None,
                pts_per_site_month=pts_sm,
                actual_accrual=accrual,
                num_sites=num_sites,
                raw_row=row.to_dict()
            )
            trials.append(trial)
        except Exception as e:
            logger.warning(f"Skipping trial row: {e}")
            continue

    logger.info(f"Parsed {len(trials)} trials from TrialTrove ({len(df)} rows), "
                f"{sum(1 for t in trials if t.nct_ids)} with NCT IDs")
    return trials


def extract_nct_ids_from_trialtrove(trials: List[CitelineTrial]) -> Dict[str, CitelineTrial]:
    """Build NCT ID → trial lookup for fast matching"""
    nct_map = {}
    for trial in trials:
        for nct_id in trial.nct_ids:
            nct_map[nct_id.upper()] = trial
    return nct_map


# =============================================================================
# MATCHING ENGINE
# =============================================================================

def normalize_name(name: str) -> str:
    """Normalize investigator name for fuzzy matching"""
    name = name.lower().strip()
    # Remove titles
    for title in ['dr.', 'dr ', 'md', 'phd', 'do', 'prof.', 'prof ']:
        name = name.replace(title, '')
    # Remove punctuation
    name = re.sub(r'[.,\-\'"]', ' ', name)
    # Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


def normalize_city(city: str) -> str:
    """Normalize city name for matching"""
    city = city.lower().strip()
    city = re.sub(r'[.,\-]', ' ', city)
    city = re.sub(r'\s+', ' ', city).strip()
    return city


def match_sitetrove_to_sites(
    citeline_pis: List[CitelinePI],
    ctgov_sites: List[Dict],  # From our /countries/{code}/sites API
    name_threshold: int = 75,  # Fuzzy match score threshold
    city_threshold: int = 85
) -> CitelineMatchResult:
    """
    Match Citeline PIs to CT.gov sites using multi-signal matching:

    PASS 1 - PI-to-PI matching (confirms existing PIs):
    1. NPI exact match (highest confidence) — US only
    2. Name + City fuzzy match (primary method)
    3. Name + Organization fuzzy match (fallback)

    PASS 2 - Org-to-Site matching (discovers new PIs):
    For unmatched records, match SiteTrove org to CT.gov site_name
    Assigns the highest-trial-count PI from that org to sites with no PI
    """
    matches = []
    matched_site_ids = set()

    # Build lookup structures from CT.gov sites
    site_investigators = []
    for site in ctgov_sites:
        for inv in site.get('investigators', []):
            site_investigators.append({
                'site_id': site['site_id'],
                'site_name': site['site_name'],
                'site_city': site.get('city', ''),
                'inv_name': inv.get('name', ''),
                'inv_name_normalized': normalize_name(inv.get('name', '')),
                'site': site
            })

    # =========================================================================
    # PASS 1: PI-to-PI Matching (confirms existing PIs)
    # =========================================================================
    unmatched_pis = []  # Track PIs that didn't match for Pass 2

    for pi in citeline_pis:
        best_match = None
        best_confidence = 0
        match_method = 'none'

        pi_name_norm = normalize_name(pi.full_name)
        pi_city_norm = normalize_city(pi.city)

        # Method 1: NPI exact match (US sites only, highest precision)
        if pi.npi:
            for si in site_investigators:
                if si.get('npi') == pi.npi:
                    best_match = si
                    best_confidence = 99
                    match_method = 'npi_exact'
                    break

        # Method 2: Name + City fuzzy match
        if best_confidence < 90:
            for si in site_investigators:
                name_score = _fuzzy_token_sort_ratio(pi_name_norm, si['inv_name_normalized'])

                if name_score >= name_threshold:
                    city_score = _fuzzy_ratio(pi_city_norm, normalize_city(si['site_city']))

                    if city_score >= city_threshold:
                        combined = (name_score * 0.6) + (city_score * 0.4)
                        if combined > best_confidence:
                            best_confidence = combined
                            best_match = si
                            match_method = 'name_city_fuzzy'

        # Method 3: Name + Organization fuzzy match (fallback)
        if best_confidence < 70:
            for site in ctgov_sites:
                org_score = _fuzzy_token_sort_ratio(
                    normalize_name(pi.organization),
                    normalize_name(site.get('site_name', ''))
                )
                if org_score >= 70:
                    # Check if any investigator name partially matches
                    for inv in site.get('investigators', []):
                        name_score = _fuzzy_token_sort_ratio(
                            pi_name_norm, normalize_name(inv.get('name', ''))
                        )
                        if name_score >= 65:
                            combined = (name_score * 0.4) + (org_score * 0.4) + 20
                            if combined > best_confidence:
                                best_confidence = combined
                                best_match = {
                                    'site_id': site['site_id'],
                                    'site_name': site['site_name'],
                                    'inv_name': inv.get('name', ''),
                                    'site': site
                                }
                                match_method = 'name_org_fuzzy'

        is_matched = best_match is not None and best_confidence >= 65

        match_detail = {
            'citeline_pi': pi.full_name,
            'citeline_city': pi.city,
            'citeline_org': pi.organization,
            'citeline_tier': pi.tier,
            'matched': is_matched,
            'confidence': round(best_confidence, 1),
            'match_method': match_method,
            'matched_site_id': best_match['site_id'] if is_matched else None,
            'matched_site_name': best_match['site_name'] if is_matched else None,
            'matched_inv_name': best_match.get('inv_name') if is_matched else None,
            'is_pi_discovery': False,  # Pass 1 matches are confirmed PIs
            'enrichment': {
                'tier': pi.tier,
                'total_trials': pi.total_trials,
                'org_type': pi.org_type,
                'regulatory_actions': pi.regulatory_actions,
                'disease_areas': pi.disease_areas,
                'specialties': pi.specialties,
                'npi': pi.npi,
            }
        }
        matches.append(match_detail)

        if is_matched:
            matched_site_ids.add(best_match['site_id'])
        else:
            # Track for Pass 2
            unmatched_pis.append((pi, len(matches) - 1))  # (PI object, index in matches list)

    # =========================================================================
    # PASS 2: Org-to-Site Matching (discovers new PIs for sites without PIs)
    # =========================================================================
    # Group unmatched PIs by normalized org name
    org_to_pis: Dict[str, List[Tuple[CitelinePI, int]]] = {}
    for pi, match_idx in unmatched_pis:
        org_norm = normalize_name(pi.organization)
        if org_norm not in org_to_pis:
            org_to_pis[org_norm] = []
        org_to_pis[org_norm].append((pi, match_idx))

    # For each org group, pick the best PI (highest trial count)
    org_best_pi: Dict[str, Tuple[CitelinePI, int]] = {}
    for org_norm, pi_list in org_to_pis.items():
        # Sort by total_trials desc, pick the one with most experience
        pi_list_sorted = sorted(pi_list, key=lambda x: x[0].total_trials, reverse=True)
        org_best_pi[org_norm] = pi_list_sorted[0]

    # Build site lookup by normalized name
    site_by_name_norm: Dict[str, Dict] = {}
    for site in ctgov_sites:
        site_name_norm = normalize_name(site.get('site_name', ''))
        site_by_name_norm[site_name_norm] = site

    # Sites that already have PIs (from CT.gov or Pass 1 matches)
    sites_with_pis = set()
    for site in ctgov_sites:
        if site.get('investigators'):
            sites_with_pis.add(site['site_id'])
    # Also add sites that got matched in Pass 1
    sites_with_pis.update(matched_site_ids)

    pi_discoveries = 0

    # For each unique org, try to match against sites without PIs
    for org_norm, (best_pi, match_idx) in org_best_pi.items():
        pi_city_norm = normalize_city(best_pi.city)

        best_site_match = None
        best_combined_score = 0

        for site in ctgov_sites:
            site_name_norm = normalize_name(site.get('site_name', ''))
            site_city_norm = normalize_city(site.get('city', ''))

            # Score org-to-site name match
            org_score = _fuzzy_token_sort_ratio(org_norm, site_name_norm)

            # Score city match
            city_score = _fuzzy_ratio(pi_city_norm, site_city_norm)

            # Combined score: (org * 0.6) + (city * 0.4)
            combined = (org_score * 0.6) + (city_score * 0.4)

            if combined >= 70 and combined > best_combined_score:
                # Prefer sites without existing PIs (new PI discovery)
                # But still allow matching to sites with PIs (enrichment)
                best_combined_score = combined
                best_site_match = site

        if best_site_match and best_combined_score >= 70:
            # Update the match record for this PI
            is_discovery = best_site_match['site_id'] not in sites_with_pis

            matches[match_idx].update({
                'matched': True,
                'confidence': round(best_combined_score, 1),
                'match_method': 'org_city_fuzzy',
                'matched_site_id': best_site_match['site_id'],
                'matched_site_name': best_site_match['site_name'],
                'matched_inv_name': None,  # No existing PI - this IS the discovered PI
                'is_pi_discovery': is_discovery,
            })

            matched_site_ids.add(best_site_match['site_id'])

            if is_discovery:
                pi_discoveries += 1
                logger.info(
                    f"PI Discovery: {best_pi.full_name} ({best_pi.total_trials} trials) "
                    f"→ {best_site_match['site_name']} (confidence: {best_combined_score:.1f}%)"
                )

    matched = [m for m in matches if m['matched']]
    unmatched = [m for m in matches if not m['matched']]

    return CitelineMatchResult(
        total_citeline_records=len(citeline_pis),
        matched_count=len(matched),
        unmatched_count=len(unmatched),
        new_pis_count=pi_discoveries,
        match_details=matches,
        enrichment_summary={
            'sites_enriched': len(matched_site_ids),
            'pi_discoveries': pi_discoveries,
            'with_tier': sum(1 for m in matched if m['enrichment']['tier']),
            'with_org_type': sum(1 for m in matched if m['enrichment']['org_type']),
            'with_regulatory': sum(1 for m in matched if m['enrichment']['regulatory_actions'] > 0),
            'avg_confidence': round(sum(m['confidence'] for m in matched) / max(len(matched), 1), 1)
        }
    )


def match_trialtrove_to_trials(
    citeline_trials: List[CitelineTrial],
    ctgov_trial_ncts: List[str]  # NCT IDs from our CT.gov data
) -> Dict[str, CitelineTrial]:
    """
    Match TrialTrove records to CT.gov trials by NCT ID.
    Returns: Dict of NCT_ID → CitelineTrial for matched trials.
    High precision — NCT IDs are unique identifiers.
    """
    nct_map = extract_nct_ids_from_trialtrove(citeline_trials)
    ctgov_set = {nct.upper() for nct in ctgov_trial_ncts}

    matched = {nct: trial for nct, trial in nct_map.items() if nct in ctgov_set}

    logger.info(
        f"TrialTrove matching: {len(matched)}/{len(nct_map)} NCT IDs matched "
        f"({len(ctgov_set)} CT.gov trials available)"
    )
    return matched


# =============================================================================
# COMPREHENSIVE TRIALTROVE PARSING WITH ANALYTICS
# =============================================================================

@dataclass
class TrialTroveAnalytics:
    """Comprehensive analytics from TrialTrove export"""
    competition_summary: Dict
    enrollment_benchmarks: Dict
    sponsor_landscape: Dict
    drug_landscape: Dict
    endpoint_landscape: Dict
    timeline_trends: Dict


def parse_trialtrove_full(file_content: bytes, filename: str) -> Dict:
    """
    Parse a TrialTrove export into structured trial records with comprehensive analytics.

    Args:
        file_content: Raw bytes of the Excel file
        filename: Original filename

    Returns:
        Dict containing:
        - export_type: "trialtrove"
        - total_records: count of trials
        - query_context: search context from Query sheet
        - trials: list of parsed trial dicts
        - analytics: comprehensive analytics object
        - nct_ids: list of all NCT IDs for dedup
    """
    import io
    from statistics import median
    from collections import Counter, defaultdict

    # Read Excel file
    xlsx = pd.ExcelFile(io.BytesIO(file_content))

    # Try to get query context from Query sheet
    query_context = ""
    if 'Query' in xlsx.sheet_names:
        try:
            query_df = pd.read_excel(xlsx, sheet_name='Query')
            # Extract search terms from the Query sheet
            query_context = str(query_df.to_dict())[:500]  # Truncate for storage
        except Exception:
            pass

    # Read the Results sheet (main data)
    sheet_name = 'Results' if 'Results' in xlsx.sheet_names else xlsx.sheet_names[0]
    df = pd.read_excel(xlsx, sheet_name=sheet_name)

    # Column detection with flexible matching
    def find_col(candidates: List[str]) -> Optional[str]:
        return _find_column(df, candidates)

    # Map columns
    trial_id_col = find_col(['Trial ID', 'TrialTrove ID'])
    protocol_col = find_col(['Protocol/Trial ID', 'Protocol ID', 'NCT ID'])
    title_col = find_col(['Trial Title', 'Title', 'Study Title'])
    phase_col = find_col(['Trial Phase', 'Phase'])
    status_col = find_col(['Trial Status', 'Status'])
    disease_col = find_col(['Disease', 'Condition', 'Indication'])
    ta_col = find_col(['Therapeutic Area', 'Therapy Area'])
    sponsor_col = find_col(['Sponsor/Collaborator', 'Sponsor', 'Lead Sponsor'])
    sponsor_type_col = find_col(['Sponsor/Collaborator Type', 'Sponsor Type'])
    drug_col = find_col(['Primary Tested Drug', 'Drug', 'Intervention'])
    mechanism_col = find_col(['Primary Tested Drug: Mechanism Of Action', 'Mechanism', 'MOA'])
    endpoint_col = find_col(['Primary Endpoint', 'Endpoint', 'Primary Outcome'])
    start_date_col = find_col(['Start Date', 'Study Start', 'First Patient In'])
    enrollment_dur_col = find_col(['Enrollment Duration (Mos.)', 'Enrollment Duration', 'Duration'])
    pts_site_mo_col = find_col(['Pts/Site/Mo', 'Patients/Site/Month', 'Enrollment Rate'])
    target_accrual_col = find_col(['Target Accrual', 'Target Enrollment', 'Planned Enrollment'])
    actual_accrual_col = find_col(['Actual Accrual (No. of patients)', 'Actual Accrual', 'Actual Enrollment'])
    sites_col = find_col(['Reported Sites', 'No. of Sites', 'Sites', 'Site Count'])
    countries_col = find_col(['Countries', 'Country'])
    cro_col = find_col(['Associated CRO', 'CRO', 'Contract Research Organization'])
    dct_col = find_col(['Decentralized (DCT) Attributes', 'DCT', 'Decentralized'])
    design_col = find_col(['Study Design', 'Design', 'Trial Design'])

    # Parse each trial row
    trials = []
    all_nct_ids = []

    for _, row in df.iterrows():
        try:
            # Extract trial ID
            trial_id = str(row.get(trial_id_col, '')) if trial_id_col else ''
            if trial_id in ('', 'nan', 'None'):
                trial_id = str(_)  # Use row index as fallback

            # Extract NCT IDs from protocol field
            protocol_raw = str(row.get(protocol_col, '')) if protocol_col else ''
            nct_ids = re.findall(r'NCT\d{7,8}', protocol_raw, re.IGNORECASE)
            nct_ids = [n.upper() for n in nct_ids]
            all_nct_ids.extend(nct_ids)

            # Helper to get first value from multiline/delimited field
            def get_first(col, delimiter='\n'):
                if col and pd.notna(row.get(col)):
                    val = str(row[col]).strip()
                    if delimiter in val:
                        return val.split(delimiter)[0].strip()
                    return val
                return None

            # Helper to parse numeric
            def parse_float(col):
                if col and pd.notna(row.get(col)):
                    try:
                        return float(str(row[col]).replace(',', '').strip())
                    except ValueError:
                        return None
                return None

            def parse_int(col):
                if col and pd.notna(row.get(col)):
                    try:
                        return int(float(str(row[col]).replace(',', '').strip()))
                    except ValueError:
                        return None
                return None

            # Parse date to ISO string
            def parse_date(col):
                if col and pd.notna(row.get(col)):
                    val = row[col]
                    if isinstance(val, pd.Timestamp):
                        return val.isoformat()[:10]
                    try:
                        return pd.to_datetime(val).isoformat()[:10]
                    except Exception:
                        return str(val)[:10]
                return None

            # Parse countries (semicolon delimited)
            countries = []
            if countries_col and pd.notna(row.get(countries_col)):
                raw = str(row[countries_col])
                countries = [c.strip() for c in raw.split(';') if c.strip() and c.strip() != 'nan']

            trial = {
                'trial_id': trial_id,
                'protocol_ids': protocol_raw,
                'nct_ids': nct_ids,
                'title': (str(row[title_col])[:200] if title_col and pd.notna(row.get(title_col)) else None),
                'phase': get_first(phase_col),
                'status': get_first(status_col),
                'disease': get_first(disease_col),
                'therapeutic_area': get_first(ta_col),
                'sponsor': get_first(sponsor_col),
                'sponsor_type': get_first(sponsor_type_col),
                'drug': get_first(drug_col, ','),
                'mechanism': get_first(mechanism_col),
                'primary_endpoint': get_first(endpoint_col),
                'start_date': parse_date(start_date_col),
                'enrollment_duration_months': parse_float(enrollment_dur_col),
                'pts_site_month': parse_float(pts_site_mo_col),
                'target_accrual': parse_int(target_accrual_col),
                'actual_accrual': parse_int(actual_accrual_col),
                'reported_sites': parse_int(sites_col),
                'countries': countries,
                'cro': get_first(cro_col),
                'dct_attributes': get_first(dct_col),
                'study_design': (str(row[design_col])[:300] if design_col and pd.notna(row.get(design_col)) else None),
            }
            trials.append(trial)

        except Exception as e:
            logger.warning(f"Skipping TrialTrove row: {e}")
            continue

    # =========================================================================
    # COMPUTE ANALYTICS
    # =========================================================================

    # Competition summary
    phase_counts = Counter()
    status_counts = Counter()
    active_statuses = {'Open', 'Planned', 'Temporarily Closed', 'Recruiting', 'Active', 'Enrolling'}

    for t in trials:
        # Normalize phase
        phase = (t.get('phase') or '').strip()
        if 'I' in phase and 'II' not in phase and 'III' not in phase and 'IV' not in phase:
            phase_counts['I'] += 1
        elif 'II' in phase and 'III' not in phase:
            phase_counts['II'] += 1
        elif 'III' in phase and 'IV' not in phase:
            phase_counts['III'] += 1
        elif 'IV' in phase:
            phase_counts['IV'] += 1
        else:
            phase_counts['other'] += 1

        # Status
        status = (t.get('status') or 'Unknown').strip()
        status_counts[status] += 1

    active_trials = sum(1 for t in trials if t.get('status') in active_statuses)

    competition_summary = {
        'total_trials': len(trials),
        'by_phase': dict(phase_counts),
        'by_status': dict(status_counts),
        'active_trials': active_trials,
    }

    # Enrollment benchmarks
    enrollment_durations = [t['enrollment_duration_months'] for t in trials if t.get('enrollment_duration_months')]
    pts_site_months = [t['pts_site_month'] for t in trials if t.get('pts_site_month')]
    target_accruals = [t['target_accrual'] for t in trials if t.get('target_accrual')]

    def safe_median(lst):
        return round(median(lst), 2) if lst else None

    # By phase breakdowns
    def phase_median(field: str, phase_key: str):
        values = []
        for t in trials:
            phase = (t.get('phase') or '').strip()
            val = t.get(field)
            if val is not None:
                if phase_key == 'I' and 'I' in phase and 'II' not in phase and 'III' not in phase:
                    values.append(val)
                elif phase_key == 'II' and 'II' in phase and 'III' not in phase:
                    values.append(val)
                elif phase_key == 'III' and 'III' in phase and 'IV' not in phase:
                    values.append(val)
                elif phase_key == 'IV' and 'IV' in phase:
                    values.append(val)
        return safe_median(values)

    enrollment_benchmarks = {
        'median_enrollment_duration_months': safe_median(enrollment_durations),
        'median_pts_site_month': safe_median(pts_site_months),
        'median_target_accrual': safe_median(target_accruals),
        'enrollment_duration_by_phase': {
            p: phase_median('enrollment_duration_months', p) for p in ['I', 'II', 'III', 'IV']
        },
        'pts_site_month_by_phase': {
            p: phase_median('pts_site_month', p) for p in ['I', 'II', 'III', 'IV']
        },
    }

    # Sponsor landscape
    sponsor_trials = defaultdict(lambda: {'count': 0, 'phases': set()})
    sponsor_types = Counter()
    cro_counts = Counter()

    for t in trials:
        sponsor = t.get('sponsor')
        if sponsor and sponsor != 'nan':
            sponsor_trials[sponsor]['count'] += 1
            if t.get('phase'):
                sponsor_trials[sponsor]['phases'].add(t['phase'])

        stype = t.get('sponsor_type')
        if stype and stype != 'nan':
            sponsor_types[stype] += 1

        cro = t.get('cro')
        if cro and cro != 'nan':
            cro_counts[cro] += 1

    top_sponsors = sorted(
        [{'name': k, 'trial_count': v['count'], 'phases': list(v['phases'])}
         for k, v in sponsor_trials.items()],
        key=lambda x: x['trial_count'],
        reverse=True
    )[:10]

    top_cros = [{'name': k, 'trial_count': v} for k, v in cro_counts.most_common(10)]

    sponsor_landscape = {
        'top_sponsors': top_sponsors,
        'top_cros': top_cros,
        'sponsor_type_breakdown': dict(sponsor_types),
    }

    # Drug landscape
    drug_trials = defaultdict(lambda: {'count': 0, 'mechanism': None, 'phases': set()})
    mechanism_counts = Counter()

    for t in trials:
        drug = t.get('drug')
        if drug and drug != 'nan':
            drug_trials[drug]['count'] += 1
            if t.get('mechanism'):
                drug_trials[drug]['mechanism'] = t['mechanism']
            if t.get('phase'):
                drug_trials[drug]['phases'].add(t['phase'])

        mech = t.get('mechanism')
        if mech and mech != 'nan':
            mechanism_counts[mech] += 1

    top_drugs = sorted(
        [{'name': k, 'mechanism': v['mechanism'], 'trial_count': v['count'], 'phases': list(v['phases'])}
         for k, v in drug_trials.items()],
        key=lambda x: x['trial_count'],
        reverse=True
    )[:10]

    top_mechanisms = [{'name': k, 'trial_count': v} for k, v in mechanism_counts.most_common(10)]

    drug_landscape = {
        'top_drugs': top_drugs,
        'top_mechanisms': top_mechanisms,
    }

    # Endpoint landscape
    endpoint_counts = Counter()
    for t in trials:
        ep = t.get('primary_endpoint')
        if ep and ep != 'nan':
            # Truncate long endpoints
            ep_short = ep[:100] if len(ep) > 100 else ep
            endpoint_counts[ep_short] += 1

    top_endpoints = [{'name': k, 'trial_count': v} for k, v in endpoint_counts.most_common(10)]

    endpoint_landscape = {
        'top_endpoints': top_endpoints,
    }

    # Timeline trends
    year_counts = Counter()
    for t in trials:
        start = t.get('start_date')
        if start:
            try:
                year = str(start)[:4]
                if year.isdigit() and 2000 <= int(year) <= 2030:
                    year_counts[year] += 1
            except Exception:
                pass

    timeline_trends = {
        'trials_by_year': dict(sorted(year_counts.items())),
    }

    logger.info(
        f"Parsed {len(trials)} trials from TrialTrove export '{filename}', "
        f"{len(all_nct_ids)} NCT IDs found, {active_trials} active"
    )

    return {
        'export_type': 'trialtrove',
        'file_name': filename,
        'total_records': len(trials),
        'query_context': query_context,
        'trials': trials,
        'analytics': {
            'competition_summary': competition_summary,
            'enrollment_benchmarks': enrollment_benchmarks,
            'sponsor_landscape': sponsor_landscape,
            'drug_landscape': drug_landscape,
            'endpoint_landscape': endpoint_landscape,
            'timeline_trends': timeline_trends,
        },
        'nct_ids': list(set(all_nct_ids)),
    }
