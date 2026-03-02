"""
World Bank Data Source for SiteSync Screener.

Fetches country-level indicators from the World Bank API for data-driven
regulatory and infrastructure scoring. Replaces GPT-generated scores with
real data points.

Indicators used:
- RQ.EST: Regulatory Quality Index (-2.5 to 2.5)
- SH.MED.PHYS.ZS: Physicians per 1,000 people
- LP.LPI.OVRL.XQ: Logistics Performance Index (1-5)
- SH.XPD.CHEX.GD.ZS: Health expenditure % of GDP

API docs: https://datahelpdesk.worldbank.org/knowledgebase/topics/125589
"""

import asyncio
import logging
import json
import subprocess
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

# Cache file location (relative to project root)
CACHE_DIR = Path(__file__).parent.parent.parent.parent.parent / ".cache"
CACHE_FILE = CACHE_DIR / "worldbank_indicators.json"
CACHE_TTL_DAYS = 30  # World Bank data updates annually, so cache aggressively

# ISO 3166-1 alpha-3 to alpha-2 country code mapping
# World Bank API returns 3-letter codes, but we use 2-letter codes internally
ISO_ALPHA3_TO_ALPHA2 = {
    # Major clinical trial countries
    "USA": "US", "GBR": "GB", "DEU": "DE", "FRA": "FR", "ITA": "IT",
    "ESP": "ES", "CAN": "CA", "AUS": "AU", "JPN": "JP", "CHN": "CN",
    "KOR": "KR", "IND": "IN", "BRA": "BR", "MEX": "MX", "ARG": "AR",
    "NLD": "NL", "BEL": "BE", "CHE": "CH", "AUT": "AT", "POL": "PL",
    "CZE": "CZ", "HUN": "HU", "ISR": "IL", "ZAF": "ZA", "RUS": "RU",
    "TWN": "TW", "HKG": "HK", "SGP": "SG", "NZL": "NZ", "IRL": "IE",
    "DNK": "DK", "SWE": "SE", "NOR": "NO", "FIN": "FI", "PRT": "PT",
    "GRC": "GR", "TUR": "TR", "UKR": "UA", "ROU": "RO", "BGR": "BG",
    "HRV": "HR", "SVK": "SK", "SVN": "SI", "SRB": "RS", "MYS": "MY",
    "THA": "TH", "PHL": "PH", "IDN": "ID", "VNM": "VN", "EGY": "EG",
    "SAU": "SA", "ARE": "AE", "CHL": "CL", "COL": "CO", "PER": "PE",
    # Additional countries that may appear
    "LTU": "LT", "LVA": "LV", "EST": "EE", "CYP": "CY", "MLT": "MT",
    "LUX": "LU", "PAK": "PK", "BGD": "BD", "LKA": "LK", "MMR": "MM",
    "KHM": "KH", "LAO": "LA", "MNG": "MN", "KAZ": "KZ", "UZB": "UZ",
    "GEO": "GE", "ARM": "AM", "AZE": "AZ", "BLR": "BY", "MDA": "MD",
    "ALB": "AL", "MKD": "MK", "BIH": "BA", "MNE": "ME", "XKX": "XK",
    "MAR": "MA", "TUN": "TN", "DZA": "DZ", "NGA": "NG", "KEN": "KE",
    "GHA": "GH", "ETH": "ET", "TZA": "TZ", "UGA": "UG", "ZWE": "ZW",
    "JOR": "JO", "LBN": "LB", "IRQ": "IQ", "IRN": "IR", "KWT": "KW",
    "QAT": "QA", "BHR": "BH", "OMN": "OM", "ECU": "EC", "VEN": "VE",
    "BOL": "BO", "PRY": "PY", "URY": "UY", "CRI": "CR", "PAN": "PA",
    "GTM": "GT", "HND": "HN", "SLV": "SV", "NIC": "NI", "DOM": "DO",
    "PRI": "PR", "JAM": "JM", "TTO": "TT", "CUB": "CU",
}


def alpha3_to_alpha2(alpha3: str) -> str:
    """Convert ISO 3166-1 alpha-3 code to alpha-2 code."""
    if not alpha3:
        return ""
    return ISO_ALPHA3_TO_ALPHA2.get(alpha3.upper(), "")


@dataclass
class CountryIndicators:
    """Normalized country-level indicators from World Bank (0-100 scale)."""
    country_code: str
    country_name: str

    # Normalized scores (0-100)
    regulatory_quality: Optional[float] = None  # From RQ.EST
    physician_density: Optional[float] = None   # From SH.MED.PHYS.ZS
    logistics_index: Optional[float] = None     # From LP.LPI.OVRL.XQ
    health_expenditure: Optional[float] = None  # From SH.XPD.CHEX.GD.ZS

    # Raw values for display
    regulatory_quality_raw: Optional[float] = None  # Actual RQ.EST value (-2.5 to 2.5)
    physician_density_raw: Optional[float] = None   # Actual physicians per 1,000
    logistics_index_raw: Optional[float] = None     # Actual LPI (1-5)
    health_expenditure_raw: Optional[float] = None  # Actual % of GDP

    # Population data (for addressable patient pool calculations)
    population: Optional[int] = None  # Total population (not normalized)

    # Data freshness
    data_year: Optional[int] = None
    last_updated: Optional[str] = None

    def get_composite_regulatory_score(self) -> Optional[float]:
        """
        Calculate composite regulatory/infrastructure score.

        Formula:
        - 50% Regulatory Quality Index
        - 30% Logistics Performance Index
        - 20% Health Expenditure % GDP
        """
        components = []
        weights = []

        if self.regulatory_quality is not None:
            components.append(self.regulatory_quality * 0.5)
            weights.append(0.5)
        if self.logistics_index is not None:
            components.append(self.logistics_index * 0.3)
            weights.append(0.3)
        if self.health_expenditure is not None:
            components.append(self.health_expenditure * 0.2)
            weights.append(0.2)

        if not components:
            return None

        # Normalize by actual weights used (in case some indicators missing)
        total_weight = sum(weights)
        return sum(components) / total_weight if total_weight > 0 else None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Indicator definitions with normalization parameters
INDICATORS = {
    "RQ.EST": {
        "name": "Regulatory Quality Index",
        "field": "regulatory_quality",
        "raw_field": "regulatory_quality_raw",
        "min_val": -2.5,
        "max_val": 2.5,
        "normalize": lambda x: ((x + 2.5) / 5.0) * 100,  # -2.5→0, 2.5→100
    },
    "SH.MED.PHYS.ZS": {
        "name": "Physicians per 1,000",
        "field": "physician_density",
        "raw_field": "physician_density_raw",
        "min_val": 0,
        "max_val": 5.0,  # Cap at 5 physicians per 1,000
        "normalize": lambda x: min(100, (x / 5.0) * 100),
    },
    "LP.LPI.OVRL.XQ": {
        "name": "Logistics Performance Index",
        "field": "logistics_index",
        "raw_field": "logistics_index_raw",
        "min_val": 1.0,
        "max_val": 5.0,
        "normalize": lambda x: ((x - 1.0) / 4.0) * 100,  # 1→0, 5→100
    },
    "SH.XPD.CHEX.GD.ZS": {
        "name": "Health Expenditure % GDP",
        "field": "health_expenditure",
        "raw_field": "health_expenditure_raw",
        "min_val": 0,
        "max_val": 20.0,  # Cap at 20% of GDP
        "normalize": lambda x: min(100, (x / 20.0) * 100),
    },
    "SP.POP.TOTL": {
        "name": "Total Population",
        "field": "population",
        "raw_field": None,  # No separate raw field - population is stored as-is
        "min_val": 0,
        "max_val": None,  # No max - store raw count
        "normalize": lambda x: int(x),  # Store as integer, not normalized
        "is_raw_value": True,  # Special flag to skip normalization
    },
}


class WorldBankDataSource:
    """
    Fetches and caches country-level indicators from the World Bank API.

    Usage:
        wb = WorldBankDataSource()
        indicators = await wb.get_country_indicators(["US", "GB", "DE"])
        us_data = indicators.get("US")
        print(f"US regulatory score: {us_data.regulatory_quality}")
    """

    BASE_URL = "https://api.worldbank.org/v2"

    def __init__(self, timeout: float = 30.0):
        """Initialize the World Bank data source."""
        self.timeout = timeout
        self._cache: Dict[str, CountryIndicators] = {}
        self._cache_loaded = False
        self._load_cache()

    def _load_cache(self) -> None:
        """Load cached indicators from disk."""
        if not CACHE_FILE.exists():
            logger.debug("No World Bank cache file found")
            return

        try:
            with open(CACHE_FILE, "r") as f:
                cache_data = json.load(f)

            # Check cache freshness
            cache_date = datetime.fromisoformat(cache_data.get("cached_at", "2000-01-01"))
            if datetime.now() - cache_date > timedelta(days=CACHE_TTL_DAYS):
                logger.info(f"World Bank cache expired (cached {cache_date.date()})")
                return

            # Load country data
            for code, data in cache_data.get("countries", {}).items():
                self._cache[code.upper()] = CountryIndicators(**data)

            self._cache_loaded = True
            logger.info(f"Loaded World Bank cache: {len(self._cache)} countries")

        except Exception as e:
            logger.warning(f"Failed to load World Bank cache: {e}")

    def _save_cache(self) -> None:
        """Save indicators to disk cache."""
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

            cache_data = {
                "cached_at": datetime.now().isoformat(),
                "countries": {
                    code: ind.to_dict()
                    for code, ind in self._cache.items()
                }
            }

            with open(CACHE_FILE, "w") as f:
                json.dump(cache_data, f, indent=2)

            logger.info(f"Saved World Bank cache: {len(self._cache)} countries")

        except Exception as e:
            logger.warning(f"Failed to save World Bank cache: {e}")

    async def get_country_indicators(
        self,
        country_codes: List[str],
        force_refresh: bool = False
    ) -> Dict[str, CountryIndicators]:
        """
        Get indicators for multiple countries.

        Args:
            country_codes: List of ISO 3166-1 alpha-2 country codes (e.g., ["US", "GB"])
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            Dict mapping country code to CountryIndicators
        """
        # Normalize country codes
        codes = [c.upper() for c in country_codes]

        # Check cache first
        if not force_refresh:
            cached_results = {}
            missing_codes = []

            for code in codes:
                if code in self._cache:
                    cached_results[code] = self._cache[code]
                else:
                    missing_codes.append(code)

            if not missing_codes:
                logger.debug(f"World Bank cache hit: all {len(codes)} countries cached")
                return cached_results

            logger.info(f"World Bank: {len(cached_results)} cached, {len(missing_codes)} to fetch")
            codes = missing_codes
        else:
            cached_results = {}

        # Fetch missing countries from API
        fetched = await self._fetch_indicators(codes)

        # Merge results
        result = {**cached_results, **fetched}

        # Update cache
        self._cache.update(fetched)
        if fetched:
            self._save_cache()

        return result

    async def _fetch_indicators(
        self,
        country_codes: List[str]
    ) -> Dict[str, CountryIndicators]:
        """Fetch indicators from World Bank API."""
        if not country_codes:
            return {}

        # Initialize results
        results: Dict[str, CountryIndicators] = {}
        for code in country_codes:
            results[code] = CountryIndicators(
                country_code=code,
                country_name="",
                last_updated=datetime.now().isoformat(),
            )

        # Batch countries (API accepts semicolon-separated codes)
        # Limit to 50 per request to avoid URL length issues
        batch_size = 50
        batches = [
            country_codes[i:i + batch_size]
            for i in range(0, len(country_codes), batch_size)
        ]

        # Use explicit timeout settings and disable HTTP/2 for better Docker compatibility
        timeout_config = httpx.Timeout(
            connect=15.0,   # Connection timeout
            read=45.0,      # Read timeout (World Bank API can be slow)
            write=10.0,
            pool=10.0,
        )
        async with httpx.AsyncClient(
            timeout=timeout_config,
            http2=False,  # Disable HTTP/2 to avoid Docker networking issues
            follow_redirects=True,
        ) as client:
            for indicator_code, indicator_info in INDICATORS.items():
                for batch in batches:
                    try:
                        await self._fetch_single_indicator(
                            client, batch, indicator_code, indicator_info, results
                        )
                        # Rate limit: small delay between requests
                        await asyncio.sleep(0.2)
                    except Exception as e:
                        logger.error(f"Failed to fetch {indicator_code} for batch: {e}")

        # Log results
        for code, ind in results.items():
            if ind.regulatory_quality is not None:
                logger.info(
                    f"World Bank data for {code}: RQ={ind.regulatory_quality_raw:.2f} "
                    f"({ind.regulatory_quality:.0f}), PHYS={ind.physician_density_raw or 'N/A'}, "
                    f"LPI={ind.logistics_index_raw or 'N/A'}"
                )
            else:
                logger.warning(f"No World Bank data available for {code}")

        return results

    async def _fetch_single_indicator(
        self,
        client: httpx.AsyncClient,
        country_codes: List[str],
        indicator_code: str,
        indicator_info: Dict,
        results: Dict[str, CountryIndicators]
    ) -> None:
        """Fetch a single indicator for multiple countries."""
        # Build URL with semicolon-separated country codes
        codes_str = ";".join(country_codes)
        url = (
            f"{self.BASE_URL}/country/{codes_str}/indicator/{indicator_code}"
            f"?format=json&date=2015:2024&per_page=1000"
        )

        logger.debug(f"Fetching World Bank indicator: {indicator_code}")

        try:
            response = await client.get(url)
            response.raise_for_status()

            data = response.json()

            # World Bank API returns [metadata, data_array]
            if not isinstance(data, list) or len(data) < 2:
                logger.warning(f"Unexpected World Bank response format for {indicator_code}")
                return

            data_points = data[1]
            if not data_points:
                logger.debug(f"No data points for {indicator_code}")
                return

            # Group by country and get latest value
            country_values: Dict[str, tuple] = {}  # code -> (value, year)
            unmapped_codes = set()

            for point in data_points:
                # World Bank returns 3-letter ISO codes - convert to 2-letter
                alpha3 = point.get("countryiso3code", "")
                code = alpha3_to_alpha2(alpha3) if alpha3 else ""

                if not code:
                    # Fallback: try to get 2-letter code from country.id
                    code = point.get("country", {}).get("id", "")

                if not code and alpha3:
                    # Track unmapped 3-letter codes for debugging
                    unmapped_codes.add(alpha3)
                    continue

                code = code.upper()
                value = point.get("value")
                year = point.get("date")
                country_name = point.get("country", {}).get("value", "")

                if value is None:
                    continue

                # Keep latest year's value
                if code not in country_values or (year and year > country_values[code][1]):
                    country_values[code] = (value, year, country_name)

            # Update results
            field = indicator_info["field"]
            raw_field = indicator_info["raw_field"]
            normalize_fn = indicator_info["normalize"]

            for code, (value, year, name) in country_values.items():
                if code in results:
                    # Set raw value (if field exists)
                    if raw_field:
                        setattr(results[code], raw_field, value)
                    # Set normalized/processed value
                    try:
                        processed = normalize_fn(value)
                        setattr(results[code], field, processed)
                    except Exception as e:
                        logger.warning(f"Failed to normalize {indicator_code} for {code}: {e}")

                    # Set country name if not already set
                    if name and not results[code].country_name:
                        results[code].country_name = name

                    # Track data year (use earliest year among indicators)
                    if year:
                        try:
                            year_int = int(year)
                            if results[code].data_year is None or year_int < results[code].data_year:
                                results[code].data_year = year_int
                        except ValueError:
                            pass

            # Count how many matched our requested countries
            matched = sum(1 for code in country_values if code in results)
            logger.info(
                f"World Bank {indicator_code}: {matched}/{len(results)} countries matched "
                f"({len(country_values)} total in API response)"
            )
            if unmapped_codes:
                logger.debug(f"Unmapped 3-letter codes: {sorted(unmapped_codes)[:10]}...")

        except httpx.HTTPError as e:
            logger.warning(f"httpx failed for {indicator_code}, trying curl fallback: {e}")
            # Fallback to curl subprocess (works better in some Docker environments)
            await self._fetch_single_indicator_via_curl(
                url, indicator_code, indicator_info, results
            )
        except Exception as e:
            logger.error(f"Error processing {indicator_code}: {e}")

    async def _fetch_single_indicator_via_curl(
        self,
        url: str,
        indicator_code: str,
        indicator_info: Dict,
        results: Dict[str, CountryIndicators]
    ) -> None:
        """
        Fallback method using curl subprocess for World Bank API.

        This works better in some Docker environments where httpx/asyncio
        has connectivity issues with external APIs.
        """
        try:
            # Run curl as a subprocess (non-blocking via asyncio)
            process = await asyncio.create_subprocess_exec(
                'curl', '-s', '-m', '45', url,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=60.0
            )

            if process.returncode != 0:
                logger.error(f"curl failed for {indicator_code}: {stderr.decode()}")
                return

            data = json.loads(stdout.decode())

            # Same parsing logic as _fetch_single_indicator
            if not isinstance(data, list) or len(data) < 2:
                logger.warning(f"Unexpected World Bank response format for {indicator_code} (curl)")
                return

            data_points = data[1]
            if not data_points:
                logger.debug(f"No data points for {indicator_code} (curl)")
                return

            # Group by country and get latest value
            country_values: Dict[str, tuple] = {}

            for point in data_points:
                alpha3 = point.get("countryiso3code", "")
                code = alpha3_to_alpha2(alpha3) if alpha3 else ""

                if not code:
                    code = point.get("country", {}).get("id", "")

                if not code:
                    continue

                code = code.upper()
                value = point.get("value")
                year = point.get("date")
                country_name = point.get("country", {}).get("value", "")

                if value is None:
                    continue

                if code not in country_values or (year and year > country_values[code][1]):
                    country_values[code] = (value, year, country_name)

            # Update results
            field = indicator_info["field"]
            raw_field = indicator_info["raw_field"]
            normalize_fn = indicator_info["normalize"]

            for code, (value, year, name) in country_values.items():
                if code in results:
                    if raw_field:
                        setattr(results[code], raw_field, value)
                    try:
                        processed = normalize_fn(value)
                        setattr(results[code], field, processed)
                    except Exception as e:
                        logger.warning(f"Failed to normalize {indicator_code} for {code}: {e}")

                    if name and not results[code].country_name:
                        results[code].country_name = name

                    if year:
                        try:
                            year_int = int(year)
                            if results[code].data_year is None or year_int < results[code].data_year:
                                results[code].data_year = year_int
                        except ValueError:
                            pass

            matched = sum(1 for code in country_values if code in results)
            logger.info(
                f"World Bank {indicator_code} (curl fallback): {matched}/{len(results)} countries matched"
            )

        except asyncio.TimeoutError:
            logger.error(f"curl timeout for {indicator_code}")
        except Exception as e:
            logger.error(f"curl fallback failed for {indicator_code}: {e}")

    def get_cached_country(self, country_code: str) -> Optional[CountryIndicators]:
        """Get cached indicators for a single country (sync)."""
        return self._cache.get(country_code.upper())

    def clear_cache(self) -> None:
        """Clear the in-memory and disk cache."""
        self._cache.clear()
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
        logger.info("World Bank cache cleared")

    def get_populations(self, country_codes: List[str]) -> Dict[str, int]:
        """
        Get population counts for countries (from cache).

        Returns dict of country_code -> population (int).
        Missing countries return 0.
        """
        result = {}
        for code in country_codes:
            code_upper = code.upper()
            if code_upper in self._cache:
                pop = self._cache[code_upper].population
                if pop:
                    result[code_upper] = pop
        return result


# Singleton instance for reuse
_instance: Optional[WorldBankDataSource] = None


def get_worldbank_source() -> WorldBankDataSource:
    """Get the singleton World Bank data source."""
    global _instance
    if _instance is None:
        _instance = WorldBankDataSource()
    return _instance
