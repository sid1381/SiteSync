"""
GPT-powered web enrichment for clinical trial site profiles.

Uses GPT-4o to search the web for site information and return structured data.
This service gathers publicly available information about research sites including
institution type, parent organization, therapeutic areas, and notable investigators.
"""
import json
import logging
from typing import Optional, Dict, Any

from app.services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


async def enrich_site_from_web(
    site_name: str,
    city: str,
    country: str,
    indication: Optional[str] = None,
    pi_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Use GPT-4o to gather publicly available information about a clinical trial site.

    This function uses GPT-4o's knowledge to provide information about research
    institutions. Note that GPT-4o does not have real-time web search, but can provide
    information from its training data about well-known institutions.

    Args:
        site_name: Name of the research site/institution
        city: City where the site is located
        country: Country where the site is located
        indication: Optional therapeutic area of interest
        pi_name: Optional known principal investigator name

    Returns:
        Dict containing structured site intelligence with fields like:
        - institution_name: Canonical name
        - institution_type: Academic, Community Hospital, etc.
        - parent_organization: Parent health system
        - website_url: Institution website
        - description: Brief description
        - bed_count: Approximate facility size
        - has_research_office: Whether they have a CTU
        - therapeutic_areas: Key research areas
        - notable_investigators: Key researchers
        - confidence: high/medium/low
        - sources: Data source notes
    """

    prompt = f"""You are a clinical trial site intelligence researcher. Provide information about the following clinical research site based on your knowledge.

Site: "{site_name}"
Location: {city}, {country}
{f'Therapeutic area of interest: {indication}' if indication else ''}
{f'Known PI: {pi_name}' if pi_name else ''}

Based on your knowledge of this institution, provide:
1. Official/canonical name of the institution
2. Institution type: "Academic Medical Center", "Community Hospital", "Dedicated Research Site", "Private Practice", "Government/VA", or "Unknown"
3. Parent institution or health system name (if applicable)
4. Website URL (the actual institutional website if you know it)
5. Key therapeutic areas or departments relevant to clinical research
6. Notable investigators or department heads (especially in {indication if indication else 'the relevant therapeutic area'} if known)
7. Approximate bed count or facility size if you know it
8. Whether they have a dedicated clinical trials office or research department
9. Brief description of the institution (1-2 sentences)

IMPORTANT:
- Only provide information you are confident about from your training data
- If you're uncertain about a field, return null for that field
- Do NOT fabricate specific details like exact bed counts if unknown
- For smaller or less well-known sites, it's OK to return mostly null values with confidence: "low"
- Focus on factual, verifiable information

Return ONLY valid JSON in this exact format, nothing else:
{{
  "institution_name": "canonical name or null",
  "institution_type": "Academic Medical Center | Community Hospital | Dedicated Research Site | Private Practice | Government/VA | Unknown",
  "parent_organization": "parent health system name or null",
  "website_url": "URL or null",
  "description": "1-2 sentence description or null",
  "bed_count": number or null,
  "has_research_office": true/false/null,
  "therapeutic_areas": ["list", "of", "areas"] or [],
  "notable_investigators": [
    {{"name": "...", "role": "...", "department": "..."}}
  ] or [],
  "recent_news": [],
  "confidence": "high" | "medium" | "low",
  "sources": ["GPT-4o knowledge base"],
  "enrichment_notes": "any caveats about the data quality or confidence level"
}}"""

    try:
        client = get_openai_client()

        result_text = client.chat_completion(
            system_message="You are a clinical trial site intelligence researcher. Return only valid JSON. Never fabricate information - return null for unknown fields.",
            user_message=prompt,
            temperature=0.1,
            max_tokens=2000,
            response_format={"type": "json_object"}
        )

        result = json.loads(result_text)

        # Validate and clean the result
        result['_source'] = 'gpt_knowledge_enrichment'
        result['_model'] = 'gpt-4o'

        # Ensure required fields exist
        if 'confidence' not in result:
            result['confidence'] = 'low'
        if 'sources' not in result:
            result['sources'] = ['GPT-4o knowledge base']
        if 'institution_type' not in result or result['institution_type'] is None:
            result['institution_type'] = 'Unknown'
        if 'therapeutic_areas' not in result:
            result['therapeutic_areas'] = []
        if 'notable_investigators' not in result:
            result['notable_investigators'] = []

        logger.info(
            f"Site enrichment for '{site_name}' in {city}: "
            f"confidence={result.get('confidence')}, "
            f"type={result.get('institution_type')}"
        )

        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GPT response for site '{site_name}': {e}")
        return {
            "institution_type": "Unknown",
            "confidence": "low",
            "therapeutic_areas": [],
            "notable_investigators": [],
            "enrichment_notes": "Failed to parse enrichment response",
            "sources": [],
            "_source": "gpt_knowledge_enrichment",
            "_error": str(e)
        }

    except Exception as e:
        logger.error(f"Site enrichment failed for site '{site_name}': {e}")
        return {
            "institution_type": "Unknown",
            "confidence": "low",
            "therapeutic_areas": [],
            "notable_investigators": [],
            "enrichment_notes": f"Enrichment unavailable: {str(e)}",
            "sources": [],
            "_source": "gpt_knowledge_enrichment",
            "_error": str(e)
        }
