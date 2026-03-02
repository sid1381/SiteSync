"""
Prevalence Estimation Service for SiteSync Screener.

Estimates disease prevalence per country using GPT-4o as a structured
epidemiology lookup engine, NOT as an opinion generator.

Key features:
- Results are CACHED per indication × country permanently
- GPT is called at temperature 0 for maximum determinism
- GPT returns specific numbers with source citations
- Results feed mathematical formulas for addressable patient pools

This replaces the opinion-based prevalence_score with data-driven estimates.
"""

import json
import re
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# Cache directory for prevalence data
CACHE_DIR = Path(__file__).parent.parent.parent.parent.parent / ".cache" / "prevalence"


@dataclass
class PrevalenceData:
    """Prevalence data for a single country and indication."""
    country_code: str
    country_name: str
    prevalence_per_100k: Optional[float] = None  # Published prevalence rate
    incidence_per_100k: Optional[float] = None   # Annual incidence rate
    data_source: str = ""                         # Citation string
    data_year: Optional[int] = None
    confidence: str = "modeled"                   # 'published', 'regional_estimate', 'modeled'
    notes: str = ""

    # Calculated fields (populated later with population data)
    estimated_patients: Optional[int] = None      # Total patients in country
    eligibility_fraction: float = 1.0             # Fraction after exclusion criteria
    addressable_pool: Optional[int] = None        # Patients eligible for trial

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CompetitionMetrics:
    """Competition pressure metrics for a country."""
    competing_trials: int = 0                     # Number of recruiting trials
    competition_demand: int = 0                   # Estimated patient demand from trials
    addressable_pool: int = 0                     # Available patient pool
    competition_ratio: float = 0.0                # demand / supply ratio
    competition_score: float = 100.0              # 0-100 score (100 = no competition)
    pressure_level: str = "low"                   # 'low', 'moderate', 'high', 'extreme'

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def normalize_indication(indication: str) -> str:
    """
    Normalize indication string for cache key.

    Strips qualifiers like "active", "moderate-to-severe", parentheticals.
    "Active ulcerative colitis (UC)" -> "ulcerative_colitis"
    """
    if not indication:
        return "unknown"

    text = indication.lower().strip()

    # Remove parenthetical abbreviations
    text = re.sub(r'\s*\([^)]*\)\s*', ' ', text)

    # Remove common qualifiers
    qualifiers = [
        'active', 'moderate', 'severe', 'mild', 'chronic', 'acute',
        'moderate-to-severe', 'moderate to severe', 'advanced', 'metastatic',
        'refractory', 'relapsed', 'untreated', 'previously treated',
        'newly diagnosed', 'recurrent', 'progressive', 'stable',
    ]
    for qual in qualifiers:
        text = re.sub(rf'\b{qual}\b', '', text, flags=re.IGNORECASE)

    # Normalize whitespace and convert to underscore
    text = '_'.join(text.split())

    # Remove non-alphanumeric except underscores
    text = re.sub(r'[^a-z0-9_]', '', text)

    # Remove leading/trailing underscores and collapse multiple
    text = re.sub(r'_+', '_', text).strip('_')

    return text or "unknown"


class PrevalenceSource:
    """
    Data source for disease prevalence estimates.

    Uses GPT-4o as a structured epidemiology lookup engine with permanent caching.
    """

    def __init__(self, openai_client=None):
        """Initialize with optional OpenAI client."""
        self.openai = openai_client
        if self.openai is None:
            try:
                from app.services.openai_client import get_openai_client
                self.openai = get_openai_client()
            except Exception as e:
                logger.warning(f"OpenAI not available for prevalence estimates: {e}")

        # Ensure cache directory exists
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, indication: str) -> Path:
        """Get cache file path for an indication."""
        slug = normalize_indication(indication)
        return CACHE_DIR / f"{slug}.json"

    def _load_cache(self, indication: str) -> Dict[str, PrevalenceData]:
        """Load cached prevalence data for an indication."""
        cache_path = self._get_cache_path(indication)
        if not cache_path.exists():
            return {}

        try:
            with open(cache_path, 'r') as f:
                data = json.load(f)

            # Convert to PrevalenceData objects
            result = {}
            for code, item in data.items():
                result[code] = PrevalenceData(
                    country_code=item.get("country_code", code),
                    country_name=item.get("country_name", ""),
                    prevalence_per_100k=item.get("prevalence_per_100k"),
                    incidence_per_100k=item.get("incidence_per_100k"),
                    data_source=item.get("data_source", ""),
                    data_year=item.get("data_year"),
                    confidence=item.get("confidence", "modeled"),
                    notes=item.get("notes", ""),
                )
            return result
        except Exception as e:
            logger.warning(f"Error loading prevalence cache: {e}")
            return {}

    def _save_cache(self, indication: str, data: Dict[str, PrevalenceData]):
        """Save prevalence data to cache."""
        cache_path = self._get_cache_path(indication)
        try:
            # Convert to serializable dict
            serializable = {code: item.to_dict() for code, item in data.items()}
            with open(cache_path, 'w') as f:
                json.dump(serializable, f, indent=2)
            logger.info(f"Cached prevalence data to {cache_path}")
        except Exception as e:
            logger.error(f"Error saving prevalence cache: {e}")

    async def get_prevalence(
        self,
        indication: str,
        countries: List[str],
        indication_detail: str = "",
    ) -> Dict[str, PrevalenceData]:
        """
        Get prevalence estimates for an indication across countries.

        Args:
            indication: Primary indication (e.g., "Ulcerative colitis")
            countries: List of country codes (e.g., ["US", "GB", "DE"])
            indication_detail: Additional detail (e.g., "Moderate-to-severe active UC")

        Returns:
            Dict mapping country_code -> PrevalenceData
        """
        if not indication:
            logger.warning("No indication provided for prevalence lookup")
            return {}

        # Load cache
        cache = self._load_cache(indication)

        # Find countries not in cache
        countries_upper = [c.upper() for c in countries if c]
        cached_countries = set(cache.keys())
        missing_countries = [c for c in countries_upper if c not in cached_countries]

        logger.info(
            f"Prevalence lookup for '{indication}': "
            f"{len(cached_countries & set(countries_upper))} cached, "
            f"{len(missing_countries)} to fetch"
        )

        # Fetch missing countries from GPT
        if missing_countries and self.openai:
            new_data = await self._fetch_prevalence_from_gpt(
                indication=indication,
                indication_detail=indication_detail,
                countries=missing_countries,
            )

            # Merge into cache
            cache.update(new_data)

            # Save updated cache
            self._save_cache(indication, cache)

        # Return only requested countries
        return {code: cache[code] for code in countries_upper if code in cache}

    async def _fetch_prevalence_from_gpt(
        self,
        indication: str,
        indication_detail: str,
        countries: List[str],
    ) -> Dict[str, PrevalenceData]:
        """
        Fetch prevalence data from GPT-4o as structured epidemiology lookup.

        Uses batching to handle large country lists (max 10 countries per batch
        to stay within token limits while ensuring complete data for each).
        """
        if not self.openai:
            logger.warning("No OpenAI client available for prevalence fetch")
            return {}

        # Build country code to name mapping
        from app.services.screener.data_sources.base import COUNTRY_CODE_MAP

        # Reverse the map to get code -> name
        code_to_name = {v: k.title() for k, v in COUNTRY_CODE_MAP.items()}
        # Use more common names for major countries
        code_to_name.update({
            "US": "United States",
            "GB": "United Kingdom",
            "DE": "Germany",
            "FR": "France",
            "IT": "Italy",
            "ES": "Spain",
            "CA": "Canada",
            "AU": "Australia",
            "JP": "Japan",
            "CN": "China",
            "KR": "South Korea",
            "NL": "Netherlands",
            "BE": "Belgium",
            "CH": "Switzerland",
            "AT": "Austria",
            "PL": "Poland",
            "CZ": "Czech Republic",
            "HU": "Hungary",
            "IL": "Israel",
            "ZA": "South Africa",
            "BR": "Brazil",
            "MX": "Mexico",
            "AR": "Argentina",
        })

        # Batch countries to avoid token limits (10 countries per batch)
        BATCH_SIZE = 10
        all_results: Dict[str, PrevalenceData] = {}

        # Split into batches
        batches = [countries[i:i + BATCH_SIZE] for i in range(0, len(countries), BATCH_SIZE)]
        logger.info(f"Fetching prevalence data for {len(countries)} countries in {len(batches)} batches via GPT-4o")

        for batch_idx, batch in enumerate(batches):
            batch_results = await self._fetch_batch_prevalence(
                indication=indication,
                indication_detail=indication_detail,
                countries=batch,
                code_to_name=code_to_name,
                batch_num=batch_idx + 1,
                total_batches=len(batches),
            )
            all_results.update(batch_results)

        logger.info(f"Received prevalence data for {len(all_results)} countries total")
        return all_results

    async def _fetch_batch_prevalence(
        self,
        indication: str,
        indication_detail: str,
        countries: List[str],
        code_to_name: Dict[str, str],
        batch_num: int,
        total_batches: int,
    ) -> Dict[str, PrevalenceData]:
        """
        Fetch prevalence data for a single batch of countries.
        """
        country_list = ", ".join([
            f"{code} ({code_to_name.get(code, code)})"
            for code in countries
        ])

        # Build the prompt
        indication_context = indication
        if indication_detail and indication_detail.lower() != indication.lower():
            indication_context = f"{indication} ({indication_detail})"

        system_prompt = """You are an epidemiology data specialist. You provide published disease
prevalence and incidence estimates based on peer-reviewed literature,
WHO/GBD data, and national health statistics. You must cite specific
numbers from published sources. If data is unavailable for a specific
country, provide a regional estimate and flag it as estimated. Never
guess — use published data or clearly mark extrapolations.

IMPORTANT: You MUST return data for ALL countries requested. Do not skip any country."""

        user_prompt = f"""For the disease indication '{indication_context}', provide epidemiological data
for EACH of the following {len(countries)} countries: {country_list}

For EACH country, return:
1. prevalence_per_100k: Published prevalence rate per 100,000 population
2. incidence_per_100k: Published annual incidence rate per 100,000 (if available, otherwise null)
3. data_source: The source of this estimate (e.g., 'GBD 2021', 'Ng et al. Lancet 2017', 'national registry data')
4. data_year: Year of the estimate
5. confidence: 'published' if from a specific study for this country,
   'regional_estimate' if extrapolated from regional data,
   'modeled' if from GBD/WHO modeling
6. notes: Any relevant context (e.g., 'higher in urban areas', 'rising incidence')

Return a JSON object with a "countries" array containing EXACTLY {len(countries)} entries, one per country:
{{"countries": [
  {{"country_code": "US", "country_name": "United States", "prevalence_per_100k": 214, "incidence_per_100k": 12.2, "data_source": "Ng et al. Lancet 2017", "data_year": 2017, "confidence": "published", "notes": ""}},
  ...
]}}

CRITICAL: Return data for ALL {len(countries)} countries. Do not truncate or skip any country."""

        logger.info(f"Batch {batch_num}/{total_batches}: Fetching {len(countries)} countries")

        try:
            response = self.openai.create_json_completion(
                prompt=user_prompt,
                system_message=system_prompt,
                temperature=0,  # Maximum determinism for epidemiology data
                max_tokens=4000,  # Increased for complete responses
            )

            # Parse response - expect {"countries": [...]}
            if isinstance(response, dict) and "countries" in response:
                data_list = response["countries"]
            elif isinstance(response, dict) and "data" in response:
                data_list = response["data"]
            elif isinstance(response, list):
                data_list = response
            else:
                # Try to extract any list-like structure
                data_list = [response] if response else []

            # Convert to PrevalenceData objects
            result = {}
            for item in data_list:
                if not isinstance(item, dict):
                    continue
                code = item.get("country_code", "").upper()
                if not code:
                    continue

                result[code] = PrevalenceData(
                    country_code=code,
                    country_name=item.get("country_name", ""),
                    prevalence_per_100k=item.get("prevalence_per_100k"),
                    incidence_per_100k=item.get("incidence_per_100k"),
                    data_source=item.get("data_source", "GPT-4o estimate"),
                    data_year=item.get("data_year"),
                    confidence=item.get("confidence", "modeled"),
                    notes=item.get("notes", ""),
                )

            logger.info(f"Batch {batch_num}/{total_batches}: Received {len(result)}/{len(countries)} countries")

            # Log warning if we got fewer than expected
            if len(result) < len(countries):
                missing = set(countries) - set(result.keys())
                logger.warning(f"Batch {batch_num}: Missing countries: {missing}")

            return result

        except Exception as e:
            logger.error(f"Batch {batch_num}: Error fetching prevalence from GPT: {e}")
            return {}

    def calculate_addressable_pool(
        self,
        prevalence_data: Dict[str, PrevalenceData],
        populations: Dict[str, int],
        num_exclusion_criteria: int = 0,
    ) -> Dict[str, PrevalenceData]:
        """
        Calculate addressable patient pools based on prevalence and population.

        Args:
            prevalence_data: Dict of country_code -> PrevalenceData
            populations: Dict of country_code -> population count
            num_exclusion_criteria: Number of exclusion criteria from protocol (currently unused)

        Returns:
            Updated PrevalenceData dict with calculated fields
        """
        # TODO: Make eligibility_fraction a user-configurable parameter.
        # The previous "0.95^N" formula based on exclusion criteria count was not
        # defensible. For now, use full estimated patients as addressable pool.
        # Future: Allow sponsors to input their own eligibility fraction based on
        # historical screening failure rates or protocol-specific estimates.
        eligibility_fraction = 1.0

        logger.info(
            f"Eligibility fraction: {eligibility_fraction:.0%} "
            f"(using full patient pool; eligibility adjustment is TODO)"
        )

        for code, data in prevalence_data.items():
            population = populations.get(code.upper(), 0)

            if population and data.prevalence_per_100k:
                # Calculate estimated patients
                data.estimated_patients = int(
                    (data.prevalence_per_100k / 100000) * population
                )

                # Apply eligibility fraction
                data.eligibility_fraction = eligibility_fraction
                data.addressable_pool = int(
                    data.estimated_patients * eligibility_fraction
                )
            else:
                data.estimated_patients = None
                data.eligibility_fraction = eligibility_fraction
                data.addressable_pool = None

        return prevalence_data

    def calculate_competition_metrics(
        self,
        addressable_pools: Dict[str, int],
        competing_trials: Dict[str, int],
        avg_patients_per_trial: int = 50,
    ) -> Dict[str, CompetitionMetrics]:
        """
        Calculate competition pressure metrics (demand/supply ratio).

        Args:
            addressable_pools: Dict of country_code -> addressable patient pool
            competing_trials: Dict of country_code -> number of recruiting trials
            avg_patients_per_trial: Average patients per trial per country

        Returns:
            Dict of country_code -> CompetitionMetrics
        """
        result = {}

        for code in set(addressable_pools.keys()) | set(competing_trials.keys()):
            pool = addressable_pools.get(code, 0)
            trials = competing_trials.get(code, 0)

            # Calculate demand
            demand = trials * avg_patients_per_trial

            # Calculate competition ratio
            if pool > 0:
                ratio = demand / pool
            else:
                ratio = float('inf') if demand > 0 else 0

            # Convert to score (0-100, where 100 = no competition)
            if ratio == float('inf'):
                score = 0
            else:
                score = max(0, 100 * (1 - ratio))

            # Determine pressure level
            if ratio < 0.01:
                pressure = "low"
            elif ratio < 0.1:
                pressure = "moderate"
            elif ratio < 0.5:
                pressure = "high"
            else:
                pressure = "extreme"

            result[code] = CompetitionMetrics(
                competing_trials=trials,
                competition_demand=demand,
                addressable_pool=pool,
                competition_ratio=ratio if ratio != float('inf') else 999.99,
                competition_score=score,
                pressure_level=pressure,
            )

        return result

    def normalize_prevalence_scores(
        self,
        prevalence_data: Dict[str, PrevalenceData],
    ) -> Dict[str, float]:
        """
        Normalize prevalence rates to 0-100 scores.

        Country with highest prevalence = 100, others proportional.

        Returns:
            Dict of country_code -> prevalence_score (0-100)
        """
        # Get all valid prevalence values
        valid_prevalences = {
            code: data.prevalence_per_100k
            for code, data in prevalence_data.items()
            if data.prevalence_per_100k is not None and data.prevalence_per_100k > 0
        }

        if not valid_prevalences:
            # Default to 70 for all if no data
            return {code: 70.0 for code in prevalence_data.keys()}

        max_prevalence = max(valid_prevalences.values())

        result = {}
        for code in prevalence_data.keys():
            if code in valid_prevalences:
                result[code] = (valid_prevalences[code] / max_prevalence) * 100
            else:
                # Use median for countries without data
                result[code] = 50.0

        return result


# =============================================================================
# GBD PREVALENCE CSV PARSER
# =============================================================================

# Country name to ISO code mapping for GBD exports
GBD_COUNTRY_MAP = {
    # Standard names that match easily
    "united states of america": "US",
    "united states": "US",
    "usa": "US",
    "united kingdom": "GB",
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
    "republic of korea": "KR",
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
    "brazil": "BR",
    "mexico": "MX",
    "argentina": "AR",
    "india": "IN",
    "russia": "RU",
    "russian federation": "RU",
    "turkey": "TR",
    "türkiye": "TR",
    "taiwan": "TW",
    "taiwan (province of china)": "TW",
    "hong kong": "HK",
    "hong kong special administrative region of china": "HK",
    "singapore": "SG",
    "new zealand": "NZ",
    "sweden": "SE",
    "norway": "NO",
    "denmark": "DK",
    "finland": "FI",
    "ireland": "IE",
    "portugal": "PT",
    "greece": "GR",
    "romania": "RO",
    "bulgaria": "BG",
    "ukraine": "UA",
    "thailand": "TH",
    "malaysia": "MY",
    "indonesia": "ID",
    "philippines": "PH",
    "vietnam": "VN",
    "egypt": "EG",
    "saudi arabia": "SA",
    "united arab emirates": "AE",
    "colombia": "CO",
    "chile": "CL",
    "peru": "PE",
}


def parse_gbd_prevalence(file_content: bytes, filename: str) -> Dict[str, PrevalenceData]:
    """
    Parse GBD Results Tool CSV export into structured prevalence data.

    GBD CSV format has columns:
    - location_name/Location: Country name (e.g., "United States of America")
    - cause_name/Cause: Disease name
    - measure_name/Measure: "Prevalence" or "Incidence"
    - metric_name/Metric: "Rate" (per 100k) or "Number" or "Percent"
    - year/Year: Data year
    - val/Value: The estimate value
    - upper/Upper: Upper uncertainty bound
    - lower/Lower: Lower uncertainty bound
    - age_name/Age: Age group (we want "All ages" or "Age-standardized")
    - sex_name/Sex: "Both" preferred

    Returns:
        Dict mapping country_code -> PrevalenceData
    """
    import pandas as pd
    import io

    logger.info(f"Parsing GBD prevalence file: {filename}")

    # Detect file format
    try:
        # Try CSV first
        if filename.lower().endswith('.csv'):
            df = pd.read_csv(io.BytesIO(file_content))
        else:
            # Try Excel
            df = pd.read_excel(io.BytesIO(file_content))
    except Exception as e:
        logger.error(f"Failed to read GBD file: {e}")
        raise ValueError(f"Cannot read file as CSV or Excel: {e}")

    logger.info(f"GBD file has {len(df)} rows and columns: {list(df.columns)}")

    # Flexible column detection
    def find_col(candidates: List[str]) -> Optional[str]:
        cols_lower = {c.lower().strip(): c for c in df.columns}
        for candidate in candidates:
            if candidate.lower() in cols_lower:
                return cols_lower[candidate.lower()]
            # Partial match
            for col_lower, col_original in cols_lower.items():
                if candidate.lower() in col_lower:
                    return col_original
        return None

    # Map columns
    location_col = find_col(['location_name', 'location', 'country'])
    measure_col = find_col(['measure_name', 'measure'])
    metric_col = find_col(['metric_name', 'metric'])
    year_col = find_col(['year'])
    val_col = find_col(['val', 'value'])
    age_col = find_col(['age_name', 'age'])
    sex_col = find_col(['sex_name', 'sex'])
    cause_col = find_col(['cause_name', 'cause'])

    if not location_col or not val_col:
        raise ValueError(
            f"Cannot find required columns (location_name, val). "
            f"Available columns: {list(df.columns)}"
        )

    # Filter data:
    # - measure = "Prevalence" (also extract Incidence separately)
    # - metric = "Rate" (per 100k)
    # - age = "Age-standardized" or "All ages"
    # - sex = "Both"

    def filter_rows(df: pd.DataFrame, measure_type: str) -> pd.DataFrame:
        filtered = df.copy()

        # Filter by measure if column exists
        if measure_col and measure_type:
            filtered = filtered[
                filtered[measure_col].str.lower().str.contains(measure_type.lower(), na=False)
            ]

        # Filter by metric (Rate preferred)
        if metric_col:
            rate_mask = filtered[metric_col].str.lower().str.contains('rate', na=False)
            if rate_mask.any():
                filtered = filtered[rate_mask]

        # Filter by age (Age-standardized or All ages)
        if age_col:
            age_mask = (
                filtered[age_col].str.lower().str.contains('age-standardized', na=False) |
                filtered[age_col].str.lower().str.contains('all ages', na=False)
            )
            if age_mask.any():
                filtered = filtered[age_mask]

        # Filter by sex (Both preferred)
        if sex_col:
            sex_mask = filtered[sex_col].str.lower().str.contains('both', na=False)
            if sex_mask.any():
                filtered = filtered[sex_mask]

        return filtered

    prevalence_df = filter_rows(df, 'prevalence')
    incidence_df = filter_rows(df, 'incidence')

    logger.info(f"Filtered to {len(prevalence_df)} prevalence rows, {len(incidence_df)} incidence rows")

    # Build prevalence data by country
    result: Dict[str, PrevalenceData] = {}

    # Get indication from cause column
    indication = "Unknown indication"
    if cause_col and len(df) > 0:
        causes = df[cause_col].dropna().unique()
        if len(causes) > 0:
            indication = str(causes[0])

    # Get data year
    data_year = None
    if year_col and len(df) > 0:
        years = df[year_col].dropna().unique()
        if len(years) > 0:
            try:
                data_year = int(years[0])
            except (ValueError, TypeError):
                pass

    # Process prevalence rows
    for _, row in prevalence_df.iterrows():
        try:
            location = str(row[location_col]).strip()
            if not location or location.lower() == 'nan':
                continue

            # Map location to country code
            location_lower = location.lower()
            country_code = GBD_COUNTRY_MAP.get(location_lower)

            if not country_code:
                # Try pycountry if available
                try:
                    import pycountry
                    country = pycountry.countries.search_fuzzy(location)[0]
                    country_code = country.alpha_2
                except Exception:
                    logger.debug(f"Could not map location: {location}")
                    continue

            # Get prevalence value
            val = row[val_col]
            if pd.isna(val):
                continue

            try:
                prevalence_per_100k = float(val)
            except (ValueError, TypeError):
                continue

            # Get year for this row
            row_year = data_year
            if year_col and pd.notna(row.get(year_col)):
                try:
                    row_year = int(row[year_col])
                except (ValueError, TypeError):
                    pass

            # Create or update PrevalenceData
            if country_code not in result:
                result[country_code] = PrevalenceData(
                    country_code=country_code,
                    country_name=location,
                    prevalence_per_100k=prevalence_per_100k,
                    incidence_per_100k=None,
                    data_source=f"IHME GBD {row_year or 'unknown'}",
                    data_year=row_year,
                    confidence="published",
                    notes=f"Uploaded from GBD Results Tool export ({filename})",
                )
            else:
                # Update if we don't have prevalence yet
                if result[country_code].prevalence_per_100k is None:
                    result[country_code].prevalence_per_100k = prevalence_per_100k

        except Exception as e:
            logger.debug(f"Skipping GBD row: {e}")
            continue

    # Add incidence data to existing countries
    for _, row in incidence_df.iterrows():
        try:
            location = str(row[location_col]).strip()
            location_lower = location.lower()
            country_code = GBD_COUNTRY_MAP.get(location_lower)

            if not country_code:
                try:
                    import pycountry
                    country = pycountry.countries.search_fuzzy(location)[0]
                    country_code = country.alpha_2
                except Exception:
                    continue

            if country_code not in result:
                continue

            val = row[val_col]
            if pd.isna(val):
                continue

            try:
                incidence_per_100k = float(val)
                result[country_code].incidence_per_100k = incidence_per_100k
            except (ValueError, TypeError):
                continue

        except Exception:
            continue

    logger.info(
        f"Parsed GBD file: {len(result)} countries matched, "
        f"indication: {indication}, year: {data_year}"
    )

    return result


# Singleton pattern for the source
_prevalence_source = None


def get_prevalence_source(openai_client=None) -> PrevalenceSource:
    """Get or create the prevalence source singleton."""
    global _prevalence_source
    if _prevalence_source is None:
        _prevalence_source = PrevalenceSource(openai_client)
    return _prevalence_source
