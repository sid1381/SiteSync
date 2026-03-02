"""
AI-Powered Sponsor Feasibility Scorer
Uses industry-standard rubric (ASCO, Tufts CSDD, Oracle) to assess sites.
"""
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from app.services.openai_client import UnifiedOpenAIClient

logger = logging.getLogger(__name__)


@dataclass
class CategoryScore:
    """Score for a single rubric category"""
    category: str
    weight: float
    score: int  # 0-100
    confidence: str  # HIGH, MODERATE, LOW
    verification_status: str  # VERIFIED, PARTIAL, UNVERIFIED
    reasoning: str
    details: List[str]
    data_source: str


@dataclass
class FeasibilityFlag:
    """Red/Yellow/Gray flag for risks and gaps"""
    severity: str  # RED, YELLOW, GRAY
    title: str
    details: str
    risk_assessment: str
    recommendation: str
    data_source: str
    related_category: str


@dataclass
class SiteAssessmentResult:
    """Complete assessment result for a site"""
    site_id: str
    facility_name: str
    city: str
    state: str
    country: str

    # Scores
    overall_score: int
    overall_confidence: str
    category_scores: List[CategoryScore]

    # Flags
    red_flags: List[FeasibilityFlag]
    yellow_flags: List[FeasibilityFlag]
    gray_flags: List[FeasibilityFlag]

    # AI outputs
    recommendation: str
    suggested_questions: List[str]
    strengths: List[str]
    considerations: List[str]

    # Metadata
    data_sources: List[str]
    has_complete_profile: bool
    assessed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "site_id": self.site_id,
            "facility_name": self.facility_name,
            "city": self.city,
            "state": self.state,
            "country": self.country,
            "overall_score": self.overall_score,
            "overall_confidence": self.overall_confidence,
            "category_scores": [asdict(c) for c in self.category_scores],
            "red_flags": [asdict(f) for f in self.red_flags],
            "yellow_flags": [asdict(f) for f in self.yellow_flags],
            "gray_flags": [asdict(f) for f in self.gray_flags],
            "recommendation": self.recommendation,
            "suggested_questions": self.suggested_questions,
            "strengths": self.strengths,
            "considerations": self.considerations,
            "data_sources": self.data_sources,
            "has_complete_profile": self.has_complete_profile,
            "assessed_at": self.assessed_at
        }


class SponsorFeasibilityScorer:
    """
    AI-powered feasibility scorer for sponsor-side site assessment.

    Uses industry-standard rubric:
    - Enrollment Potential (25%)
    - Therapeutic Experience (25%)
    - Investigator Quality (20%)
    - Operational Capacity (15%)
    - Site Infrastructure (15%)
    """

    SCORING_RUBRIC = {
        "enrollment_potential": {
            "weight": 0.25,
            "description": "Historical enrollment performance and patient access",
            "metrics": [
                "Historical enrollment vs targets",
                "Screen failure rate",
                "Patient retention rate",
                "Patient population access"
            ],
            "scoring_guide": {
                "90-100": "Consistently exceeds enrollment targets (>100%), low screen fail (<20%), high retention (>90%)",
                "70-89": "Meets enrollment targets (80-100%), moderate screen fail (20-35%), good retention (80-90%)",
                "50-69": "Below target enrollment (60-80%), higher screen fail (35-50%), moderate retention (70-80%)",
                "below_50": "Significantly under-enrolls (<60%), high screen fail (>50%), poor retention (<70%)"
            }
        },
        "therapeutic_experience": {
            "weight": 0.25,
            "description": "Experience in the specific therapeutic area and trial phase",
            "metrics": [
                "Number of trials in indication",
                "Phase-specific experience",
                "Completion rate in indication",
                "Related therapeutic experience"
            ],
            "scoring_guide": {
                "90-100": "10+ completed trials in exact indication, extensive phase experience, >90% completion",
                "70-89": "5-9 trials in indication, good phase match, 80-90% completion",
                "50-69": "1-4 trials in indication or related areas, some phase experience, 70-80% completion",
                "below_50": "No trials in indication (RED FLAG), limited phase experience, <70% completion"
            }
        },
        "investigator_quality": {
            "weight": 0.20,
            "description": "PI qualifications, experience, and KOL status",
            "metrics": [
                "PI total trial experience",
                "PI publications/KOL status",
                "Specialty match",
                "Sub-investigator depth"
            ],
            "scoring_guide": {
                "90-100": "KOL with 50+ trials, extensive publications, exact specialty match, strong team",
                "70-89": "Experienced PI (20-50 trials), some publications, good specialty fit",
                "50-69": "Moderate experience (10-20 trials), relevant background",
                "below_50": "Limited experience (<10 trials), specialty mismatch"
            }
        },
        "operational_capacity": {
            "weight": 0.15,
            "description": "Current workload and ability to take on new trials",
            "metrics": [
                "Active trial load",
                "Competing trials in same indication",
                "Historical throughput",
                "Staff availability indicators"
            ],
            "scoring_guide": {
                "90-100": "Low active load (<5 trials), no competing studies, high throughput history",
                "70-89": "Moderate load (5-10 trials), 1 competing study, good throughput",
                "50-69": "Higher load (10-15 trials), 2-3 competing studies",
                "below_50": "Overloaded (>15 trials), multiple competing studies (YELLOW FLAG)"
            }
        },
        "site_infrastructure": {
            "weight": 0.15,
            "description": "Facilities, equipment, and operational capabilities",
            "metrics": [
                "Required equipment availability",
                "Facility type and capabilities",
                "Data management systems",
                "Regulatory compliance history"
            ],
            "scoring_guide": {
                "90-100": "All required equipment verified, academic medical center, strong systems",
                "70-89": "Most equipment available, good facility, adequate systems",
                "50-69": "Some equipment gaps, smaller facility",
                "below_50": "Significant equipment gaps (GRAY FLAG - needs verification)"
            }
        }
    }

    def __init__(self):
        self.openai_client = UnifiedOpenAIClient()

    def assess_site(
        self,
        site_data: Dict[str, Any],
        protocol_requirements: Dict[str, Any],
        site_id: str
    ) -> SiteAssessmentResult:
        """
        Run full AI-powered assessment on a site.

        Args:
            site_data: Site profile data (from CT.gov or demo profile)
            protocol_requirements: Protocol requirements
            site_id: Unique site identifier

        Returns:
            SiteAssessmentResult with scores, flags, and recommendations
        """
        logger.info(f"Assessing site: {site_data.get('facility_name', 'Unknown')}")

        has_complete_profile = site_data.get("has_demo_profile", False)

        # Build the AI prompt
        prompt = self._build_assessment_prompt(site_data, protocol_requirements)

        # Get AI assessment
        try:
            ai_response = self.openai_client.create_json_completion(
                prompt=prompt,
                system_message=self._get_system_prompt(),
                temperature=0.3  # Lower temperature for consistent scoring
            )

            assessment_data = ai_response if isinstance(ai_response, dict) else json.loads(ai_response)

        except Exception as e:
            logger.error(f"AI assessment failed: {e}")
            # Return fallback assessment
            return self._create_fallback_assessment(site_data, site_id, has_complete_profile)

        # Parse AI response into structured result
        return self._parse_ai_response(
            assessment_data,
            site_data,
            site_id,
            has_complete_profile
        )

    def _get_system_prompt(self) -> str:
        """System prompt for the AI assessor"""
        return """You are an expert clinical trial feasibility analyst working for a top-tier life sciences consulting firm.

Your role is to assess clinical trial sites for sponsors using an industry-standard rubric based on ASCO, Tufts CSDD, and Oracle methodologies.

You must:
1. Score each category objectively based on available data
2. Clearly distinguish between VERIFIED data (from ClinicalTrials.gov) and INFERRED/UNKNOWN data
3. Flag specific risks (RED = critical, YELLOW = moderate concern, GRAY = data gap)
4. Provide actionable recommendations
5. Suggest specific questions for the site qualification call

Be precise, professional, and evidence-based. Always cite the data source for each assessment."""

    def _build_assessment_prompt(
        self,
        site_data: Dict[str, Any],
        protocol_requirements: Dict[str, Any]
    ) -> str:
        """Build the assessment prompt with site data and protocol requirements"""

        rubric_text = json.dumps(self.SCORING_RUBRIC, indent=2)
        site_text = json.dumps(site_data, indent=2, default=str)
        protocol_text = json.dumps(protocol_requirements, indent=2, default=str)

        return f"""Assess this clinical trial site for the given protocol using the industry-standard scoring rubric.

## PROTOCOL REQUIREMENTS
{protocol_text}

## SITE DATA
{site_text}

## SCORING RUBRIC
{rubric_text}

## INSTRUCTIONS

1. Score each of the 5 categories (0-100) based on available data
2. For each category, provide:
   - score (0-100)
   - confidence (HIGH if data is verified, MODERATE if partially verified, LOW if inferred)
   - verification_status (VERIFIED, PARTIAL, or UNVERIFIED)
   - reasoning (2-3 sentences explaining the score)
   - key details (bullet points of evidence)

3. Identify FLAGS:
   - RED FLAGS: Critical risks that may disqualify the site (e.g., no therapeutic experience, PI issues)
   - YELLOW FLAGS: Moderate concerns requiring discussion (e.g., high trial load, competing studies)
   - GRAY FLAGS: Data gaps that need verification (e.g., equipment unknown, staff availability unclear)

4. Calculate OVERALL SCORE as weighted average of category scores

5. Write a RECOMMENDATION paragraph (3-5 sentences) summarizing:
   - Overall fit for the protocol
   - Key strengths
   - Key considerations
   - Whether to shortlist

6. Suggest 3-5 QUESTIONS for the site qualification call based on gaps/concerns

## RESPONSE FORMAT (JSON)
{{
    "overall_score": 85,
    "overall_confidence": "MODERATE",
    "category_scores": [
        {{
            "category": "Enrollment Potential",
            "weight": 0.25,
            "score": 88,
            "confidence": "MODERATE",
            "verification_status": "PARTIAL",
            "reasoning": "Site has completed X trials with Y enrollment...",
            "details": ["Detail 1", "Detail 2"],
            "data_source": "ClinicalTrials.gov"
        }}
    ],
    "red_flags": [
        {{
            "severity": "RED",
            "title": "Flag title",
            "details": "Detailed explanation",
            "risk_assessment": "Impact on trial",
            "recommendation": "Action to take",
            "data_source": "Source",
            "related_category": "Category name"
        }}
    ],
    "yellow_flags": [],
    "gray_flags": [],
    "recommendation": "Full recommendation paragraph...",
    "suggested_questions": ["Question 1", "Question 2"],
    "strengths": ["Strength 1", "Strength 2"],
    "considerations": ["Consideration 1", "Consideration 2"]
}}

Respond ONLY with valid JSON. Be thorough but concise."""

    def _parse_ai_response(
        self,
        ai_data: Dict,
        site_data: Dict,
        site_id: str,
        has_complete_profile: bool
    ) -> SiteAssessmentResult:
        """Parse AI response into structured SiteAssessmentResult"""

        # Parse category scores
        category_scores = []
        for cat_data in ai_data.get("category_scores", []):
            category_scores.append(CategoryScore(
                category=cat_data.get("category", "Unknown"),
                weight=cat_data.get("weight", 0.2),
                score=cat_data.get("score", 50),
                confidence=cat_data.get("confidence", "LOW"),
                verification_status=cat_data.get("verification_status", "UNVERIFIED"),
                reasoning=cat_data.get("reasoning", ""),
                details=cat_data.get("details", []),
                data_source=cat_data.get("data_source", "Unknown")
            ))

        # Parse flags
        def parse_flags(flags_data: List[Dict]) -> List[FeasibilityFlag]:
            return [
                FeasibilityFlag(
                    severity=f.get("severity", "GRAY"),
                    title=f.get("title", "Unknown Flag"),
                    details=f.get("details", ""),
                    risk_assessment=f.get("risk_assessment", ""),
                    recommendation=f.get("recommendation", ""),
                    data_source=f.get("data_source", "Unknown"),
                    related_category=f.get("related_category", "")
                )
                for f in flags_data
            ]

        red_flags = parse_flags(ai_data.get("red_flags", []))
        yellow_flags = parse_flags(ai_data.get("yellow_flags", []))
        gray_flags = parse_flags(ai_data.get("gray_flags", []))

        # Determine data sources
        data_sources = ["ClinicalTrials.gov"]
        if has_complete_profile:
            data_sources.append("SiteSync Profile")

        return SiteAssessmentResult(
            site_id=site_id,
            facility_name=site_data.get("facility_name", "Unknown"),
            city=site_data.get("city", ""),
            state=site_data.get("state", ""),
            country=site_data.get("country", "United States"),
            overall_score=ai_data.get("overall_score", 50),
            overall_confidence=ai_data.get("overall_confidence", "LOW"),
            category_scores=category_scores,
            red_flags=red_flags,
            yellow_flags=yellow_flags,
            gray_flags=gray_flags,
            recommendation=ai_data.get("recommendation", "Assessment could not be completed."),
            suggested_questions=ai_data.get("suggested_questions", []),
            strengths=ai_data.get("strengths", []),
            considerations=ai_data.get("considerations", []),
            data_sources=data_sources,
            has_complete_profile=has_complete_profile
        )

    def _create_fallback_assessment(
        self,
        site_data: Dict,
        site_id: str,
        has_complete_profile: bool
    ) -> SiteAssessmentResult:
        """Create a basic assessment when AI fails"""

        # Calculate basic scores from available data
        total_trials = site_data.get("total_trials", 0)
        completed_trials = site_data.get("completed_trials", 0)
        completion_rate = site_data.get("completion_rate", 0)
        active_trials = site_data.get("active_trials", 0)
        competing_trials = len(site_data.get("competing_trials", []))

        # Simple heuristic scoring
        therapeutic_score = min(90, 50 + (total_trials * 3))
        enrollment_score = int(completion_rate * 100) if completion_rate else 60
        capacity_score = max(40, 90 - (active_trials * 3) - (competing_trials * 10))
        investigator_score = 70 if site_data.get("investigators") else 50
        infrastructure_score = 85 if has_complete_profile else 55

        overall = int(
            therapeutic_score * 0.25 +
            enrollment_score * 0.25 +
            investigator_score * 0.20 +
            capacity_score * 0.15 +
            infrastructure_score * 0.15
        )

        category_scores = [
            CategoryScore("Enrollment Potential", 0.25, enrollment_score, "LOW", "PARTIAL",
                         f"Based on {completion_rate*100:.0f}% completion rate",
                         [f"{completed_trials} completed trials"], "ClinicalTrials.gov"),
            CategoryScore("Therapeutic Experience", 0.25, therapeutic_score, "MODERATE", "VERIFIED",
                         f"Site has {total_trials} trials in database",
                         [f"{total_trials} total trials", f"{completed_trials} completed"], "ClinicalTrials.gov"),
            CategoryScore("Investigator Quality", 0.20, investigator_score, "LOW", "PARTIAL",
                         "PI identified from trial records",
                         [f"{len(site_data.get('investigators', []))} investigators found"], "ClinicalTrials.gov"),
            CategoryScore("Operational Capacity", 0.15, capacity_score, "MODERATE", "VERIFIED",
                         f"{active_trials} active trials, {competing_trials} competing",
                         [f"{active_trials} active", f"{competing_trials} competing"], "ClinicalTrials.gov"),
            CategoryScore("Site Infrastructure", 0.15, infrastructure_score,
                         "HIGH" if has_complete_profile else "LOW",
                         "VERIFIED" if has_complete_profile else "UNVERIFIED",
                         "Full profile available" if has_complete_profile else "Equipment data not available",
                         ["Complete profile" if has_complete_profile else "Data gap"],
                         "SiteSync Profile" if has_complete_profile else "Unknown")
        ]

        # Generate flags
        yellow_flags = []
        gray_flags = []

        if active_trials > 10:
            yellow_flags.append(FeasibilityFlag(
                "YELLOW", "High Active Trial Load",
                f"Site has {active_trials} active trials",
                "May impact recruitment speed and staff availability",
                "Discuss dedicated FTE allocation",
                "ClinicalTrials.gov", "Operational Capacity"
            ))

        if competing_trials > 0:
            yellow_flags.append(FeasibilityFlag(
                "YELLOW", f"{competing_trials} Competing Trial(s)",
                f"Site has {competing_trials} active trials in same indication",
                "Competition for same patient population",
                "Discuss patient pool segmentation strategy",
                "ClinicalTrials.gov", "Operational Capacity"
            ))

        if not has_complete_profile:
            gray_flags.append(FeasibilityFlag(
                "GRAY", "Equipment Inventory Unknown",
                "Required equipment availability not verified",
                "Cannot confirm protocol equipment requirements met",
                "Verify equipment in site qualification call",
                "Data Gap", "Site Infrastructure"
            ))
            gray_flags.append(FeasibilityFlag(
                "GRAY", "Staff Availability Unknown",
                "Coordinator and staff capacity not verified",
                "Cannot confirm adequate staffing",
                "Discuss FTE allocation in site call",
                "Data Gap", "Operational Capacity"
            ))

        return SiteAssessmentResult(
            site_id=site_id,
            facility_name=site_data.get("facility_name", "Unknown"),
            city=site_data.get("city", ""),
            state=site_data.get("state", ""),
            country=site_data.get("country", "United States"),
            overall_score=overall,
            overall_confidence="LOW",
            category_scores=category_scores,
            red_flags=[],
            yellow_flags=yellow_flags,
            gray_flags=gray_flags,
            recommendation=f"Site has {total_trials} trials with {completion_rate*100:.0f}% completion rate. Further evaluation recommended.",
            suggested_questions=[
                "What is your dedicated FTE capacity for this study?",
                "Do you have the required equipment for this protocol?",
                "What is your typical startup timeline?",
                "How do you manage competing studies in the same indication?"
            ],
            strengths=[f"{total_trials} trials in database", f"{completion_rate*100:.0f}% completion rate"],
            considerations=[f"{active_trials} active trials", f"{competing_trials} competing studies"] if competing_trials else [f"{active_trials} active trials"],
            data_sources=["ClinicalTrials.gov"] + (["SiteSync Profile"] if has_complete_profile else []),
            has_complete_profile=has_complete_profile
        )

    def assess_multiple_sites(
        self,
        sites_data: List[Dict[str, Any]],
        protocol_requirements: Dict[str, Any]
    ) -> List[SiteAssessmentResult]:
        """Assess multiple sites and return ranked results"""

        results = []
        for site_data in sites_data:
            site_id = site_data.get("id", "unknown")
            result = self.assess_site(site_data, protocol_requirements, site_id)
            results.append(result)

        # Sort by overall score descending
        results.sort(key=lambda x: x.overall_score, reverse=True)

        return results
