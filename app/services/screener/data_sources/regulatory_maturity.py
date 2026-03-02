"""
WHO GBT Maturity Level + Stringent Regulatory Authority (SRA) bonus data.

Sources:
- WHO GBT ML3/ML4 list (December 2025):
  https://cdn.who.int/media/docs/default-source/medicines/regulatory-systems/wla/list-of-nras-operating-at-ml3-and-ml4.pdf
- ICH Members: https://www.ich.org/page/members-observers
- WHO SRA concept: established regulators that are ICH founding/standing members
  or participate in recognized regional schemes (EMA network)

Last updated: 2025-12-01 (WHO list date)
"""

from typing import Tuple

# Tier A: ICH Founding/Standing Members + Recognized SRAs
# These regulators ARE the benchmark - they set the standards others are measured against.
# Includes EMA member states (EU/EEA) since EMA is recognized as a regional regulatory
# system by WHO WLA and is an ICH founding member.
SRA_COUNTRIES: dict[str, str] = {
    # ICH Founding Members
    "US": "FDA (ICH Founding Member)",
    "JP": "PMDA (ICH Founding Member)",
    "CH": "Swissmedic (ICH Founding Member)",  # Switzerland hosts ICH
    # ICH Standing Regulatory Members
    "CA": "Health Canada (ICH Standing Member)",
    "BR": "ANVISA (ICH Standing Member)",
    "KR": "MFDS (ICH Standing Member)",  # Republic of Korea
    "SG": "HSA (ICH Observer, recognized SRA)",  # Singapore
    # EMA Network (WHO WLA recognizes as single regional regulatory system)
    # Major EU clinical trial countries:
    "DE": "BfArM/PEI (EMA Network)",
    "FR": "ANSM (EMA Network)",
    "IT": "AIFA (EMA Network)",
    "ES": "AEMPS (EMA Network)",
    "NL": "MEB (EMA Network)",
    "BE": "FAMHP (EMA Network)",
    "AT": "AGES (EMA Network)",
    "PL": "URPL (EMA Network)",
    "SE": "MPA (EMA Network)",
    "DK": "DKMA (EMA Network)",
    "FI": "Fimea (EMA Network)",
    "IE": "HPRA (EMA Network)",
    "PT": "Infarmed (EMA Network)",
    "CZ": "SUKL (EMA Network)",
    "HU": "OGYEI (EMA Network)",
    "RO": "ANMDM (EMA Network)",
    "BG": "BDA (EMA Network)",
    "HR": "HALMED (EMA Network)",
    "SK": "SIDC (EMA Network)",
    "GR": "EOF (EMA Network)",
    "NO": "NoMA (EMA/EEA)",
    "IS": "IMCA (EMA/EEA)",
    # Other recognized SRAs
    "GB": "MHRA (Post-Brexit, recognized SRA)",
    "AU": "TGA (ICH Observer, recognized SRA)",
    "NZ": "Medsafe (recognized SRA)",
    "IL": "MOH Pharmaceutical Division (recognized SRA)",
}

# Tier B: WHO GBT ML4 countries (advanced performance + continuous improvement)
# Source: WHO ML3/ML4 list, December 2025
# Note: KR and SG are already in SRA_COUNTRIES (higher tier)
WHO_GBT_ML4: dict[str, str] = {
    "SA": "SFDA (WHO GBT ML4)",  # Saudi Arabia
}

# Tier C: WHO GBT ML3 countries (stable, well-functioning regulatory systems)
# Source: WHO ML3/ML4 list, December 2025
WHO_GBT_ML3: dict[str, str] = {
    "CN": "NMPA (WHO GBT ML3)",  # China
    "EG": "EDA (WHO GBT ML3)",  # Egypt
    "ET": "EFDA (WHO GBT ML3)",  # Ethiopia
    "GH": "FDA Ghana (WHO GBT ML3)",  # Ghana
    "IN": "CDSCO (WHO GBT ML3)",  # India
    "ID": "BPOM (WHO GBT ML3)",  # Indonesia
    "NG": "NAFDAC (WHO GBT ML3)",  # Nigeria
    "RW": "Rwanda FDA (WHO GBT ML3)",  # Rwanda
    "SN": "ARP (WHO GBT ML3)",  # Senegal
    "RS": "ALIMS (WHO GBT ML3)",  # Serbia
    "ZA": "SAHPRA (WHO GBT ML3)",  # South Africa
    "TH": "Thai FDA (WHO GBT ML3)",  # Thailand
    "TR": "TITCK (WHO GBT ML3)",  # Turkey
    "TZ": "TMDA (WHO GBT ML3)",  # Tanzania
    "VN": "DAV (WHO GBT ML3)",  # Viet Nam
    "ZW": "MCAZ (WHO GBT ML3)",  # Zimbabwe
}


def get_regulatory_maturity_bonus(country_code: str) -> Tuple[float, str, str]:
    """
    Returns (bonus_points, tier_label, authority_name) for a country.

    Bonus points:
    - SRA (Tier A): +15 points
    - WHO GBT ML4 (Tier B): +12 points
    - WHO GBT ML3 (Tier C): +8 points
    - No data: +0 points

    If a country appears in both SRA and GBT lists (e.g., KR is both ICH member
    and ML4), the higher bonus applies (SRA +15).
    """
    code = country_code.upper()

    # Check SRA first (highest bonus)
    if code in SRA_COUNTRIES:
        return (15.0, "SRA", SRA_COUNTRIES[code])

    # Then ML4
    if code in WHO_GBT_ML4:
        return (12.0, "WHO GBT ML4", WHO_GBT_ML4[code])

    # Then ML3
    if code in WHO_GBT_ML3:
        return (8.0, "WHO GBT ML3", WHO_GBT_ML3[code])

    # No recognized regulatory maturity data
    return (0.0, "Unclassified", "No WHO GBT or SRA classification")


def get_all_classified_countries() -> dict:
    """Return all countries with regulatory maturity classification for reference."""
    result = {}
    for code, name in SRA_COUNTRIES.items():
        result[code] = {"tier": "SRA", "bonus": 15.0, "authority": name}
    for code, name in WHO_GBT_ML4.items():
        if code not in result:  # Don't override SRA
            result[code] = {"tier": "WHO GBT ML4", "bonus": 12.0, "authority": name}
    for code, name in WHO_GBT_ML3.items():
        if code not in result:
            result[code] = {"tier": "WHO GBT ML3", "bonus": 8.0, "authority": name}
    return result
