"""
AI-Powered Feasibility Scorer for Site-Facing Tool.
Uses GPT-4o with industry rubric to assess site-protocol fit.
Unlike sponsor view (inferred data), site view has complete profiles = higher confidence.
"""
import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

from app.services.openai_client import UnifiedOpenAIClient
from app.services.scoring_rubric import SCORING_RUBRIC, calculate_criterion_score, get_threshold_for_value, get_rubric_summary

logger = logging.getLogger(__name__)


@dataclass
class CriterionScore:
    """Individual criterion score within a category"""
    criterion_id: str
    criterion_name: str
    site_value: Any  # Actual value from site profile
    site_value_formatted: str  # Human-readable format
    threshold_matched: str  # Label of matched threshold
    points_earned: int
    max_points: int
    is_max: bool
    next_threshold: Optional[Dict]  # {points_gain, required_value, label}
    data_source: str  # Where in the profile this came from


@dataclass
class ScoreComponent:
    """Individual category score - maintains backward compatibility"""
    category: str
    score: float  # 0-100
    weight: float
    weighted_score: float
    confidence: str  # HIGH, MODERATE, LOW
    reasoning: str
    details: List[str]
    improvement_suggestions: List[str]  # Actionable improvements
    scoring_breakdown: Optional[Dict] = None  # Legacy field for backward compatibility
    criteria_scores: Optional[List[CriterionScore]] = None  # New: detailed per-criterion scores
    total_points_earned: Optional[int] = None
    total_max_points: Optional[int] = None


@dataclass
class FeasibilityFlag:
    """Detailed flag with context and recommendations"""
    severity: str  # RED, YELLOW, GREEN (green = strength)
    category: str
    title: str
    details: str
    impact: str  # How it affects the score
    recommendation: str
    potential_score_gain: Optional[int] = None  # Points gained if addressed


@dataclass
class AIFeasibilityResult:
    """
    Enhanced feasibility result with AI reasoning.
    Maintains backward compatibility with FeasibilityResult.
    """
    # Core scores (backward compatible)
    total_score: float
    grade: str  # "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit"
    components: List[ScoreComponent]

    # Flags (enhanced from simple strings)
    flags: List[str]  # Backward compatible - simple strings
    detailed_flags: List[FeasibilityFlag]  # New - rich flag objects

    # Gaps and improvements
    gaps: List[str]  # Backward compatible
    improvement_opportunities: List[Dict]  # New - prioritized improvements

    # AI narrative
    ai_assessment: Dict  # Backward compatible structure

    # Protocol comparison
    requirements_comparison: List[Dict]  # Backward compatible

    # New metadata
    confidence_level: str  # Overall confidence
    data_completeness: float  # 0-1, how complete the site profile is
    assessed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        """Convert to dict - maintains backward compatibility"""
        return {
            "total_score": self.total_score,
            "grade": self.grade,
            "components": [
                {
                    "category": c.category,
                    "score": c.score,
                    "weight": c.weight,
                    "weighted_score": c.weighted_score,
                    # Backward compatible field (frontend expects this)
                    "rationale": c.reasoning,
                    # Enhanced fields
                    "confidence": c.confidence,
                    "reasoning": c.reasoning,
                    "details": c.details,
                    "improvement_suggestions": c.improvement_suggestions,
                    # Legacy scoring breakdown for backward compatibility
                    "scoring_breakdown": c.scoring_breakdown,
                    # New: criteria-based scoring
                    "criteria_scores": [
                        {
                            "criterion_id": cs.criterion_id,
                            "criterion_name": cs.criterion_name,
                            "site_value": cs.site_value,
                            "site_value_formatted": cs.site_value_formatted,
                            "threshold_matched": cs.threshold_matched,
                            "points_earned": cs.points_earned,
                            "max_points": cs.max_points,
                            "is_max": cs.is_max,
                            "next_threshold": cs.next_threshold,
                            "data_source": cs.data_source
                        }
                        for cs in (c.criteria_scores or [])
                    ] if c.criteria_scores else None,
                    "total_points_earned": c.total_points_earned,
                    "total_max_points": c.total_max_points
                }
                for c in self.components
            ],
            "flags": self.flags,
            "detailed_flags": [asdict(f) for f in self.detailed_flags],
            "gaps": self.gaps,
            "improvement_opportunities": self.improvement_opportunities,
            "ai_assessment": self.ai_assessment,
            "requirements_comparison": self.requirements_comparison,
            "confidence_level": self.confidence_level,
            "data_completeness": self.data_completeness,
            "assessed_at": self.assessed_at
        }


class AIFeasibilityScorer:
    """
    AI-powered feasibility scorer for site-facing assessments.

    Uses complete site profile data (not inferred) for high-confidence scoring.
    Provides actionable improvement suggestions.
    """

    # Maintain same weights as original for backward compatibility
    WEIGHTS = {
        "historical_performance": 0.30,
        "patient_indication": 0.25,
        "equipment_facilities": 0.20,
        "staffing_certifications": 0.15,
        "emr_workflows": 0.10
    }

    CATEGORY_DESCRIPTIONS = {
        "historical_performance": {
            "name": "Historical Performance & Experience",
            "description": "Past trial experience, enrollment history, completion rates",
            "metrics": [
                "Number of completed trials in therapeutic area",
                "Historical enrollment vs targets",
                "Trial completion rate",
                "Phase-specific experience"
            ]
        },
        "patient_indication": {
            "name": "Patient Population & Indication Match",
            "description": "Access to target patient population, indication experience",
            "metrics": [
                "Patient volume for target indication",
                "Demographics match (age, sex, ethnicity)",
                "Inclusion/exclusion criteria compatibility",
                "Competing trials for same population"
            ]
        },
        "equipment_facilities": {
            "name": "Equipment & Facilities",
            "description": "Required equipment availability, facility capabilities",
            "metrics": [
                "Required equipment availability",
                "Facility certifications",
                "Lab capabilities",
                "Storage requirements (temp-controlled, etc.)"
            ]
        },
        "staffing_certifications": {
            "name": "Staffing & Certifications",
            "description": "PI qualifications, staff experience, required certifications",
            "metrics": [
                "PI experience and qualifications",
                "Coordinator experience",
                "Required certifications (GCP, etc.)",
                "Staff availability and capacity"
            ]
        },
        "emr_workflows": {
            "name": "EMR & Data Workflows",
            "description": "Electronic systems, data capture capabilities, workflows",
            "metrics": [
                "EMR/EHR system compatibility",
                "EDC experience",
                "Data query response time",
                "ePRO/eCOA capabilities"
            ]
        }
    }

    GRADE_THRESHOLDS = {
        85: "Strong Fit",
        70: "Good Fit",
        55: "Moderate Fit",
        0: "Weak Fit"
    }

    def __init__(self):
        self.openai_client = UnifiedOpenAIClient()

    async def calculate_feasibility(
        self,
        site_profile: Dict[str, Any],
        protocol_requirements: Dict[str, Any],
        survey_responses: Optional[Dict[str, Any]] = None
    ) -> AIFeasibilityResult:
        """
        Calculate AI-powered feasibility score.

        Args:
            site_profile: Complete site profile data
            protocol_requirements: Extracted protocol requirements
            survey_responses: Optional survey response data

        Returns:
            AIFeasibilityResult with scores, flags, and recommendations
        """
        logger.info(f"AI feasibility assessment for site: {site_profile.get('name', 'Unknown')}")

        # Calculate data completeness
        data_completeness = self._calculate_data_completeness(site_profile, survey_responses)

        # Build AI prompt
        prompt = self._build_assessment_prompt(
            site_profile,
            protocol_requirements,
            survey_responses,
            data_completeness
        )

        # Get AI assessment
        try:
            ai_response = self.openai_client.create_json_completion(
                prompt=prompt,
                system_message=self._get_system_prompt(),
                temperature=0.3,
                max_tokens=6000  # Large response for detailed assessment
            )

            assessment_data = json.loads(ai_response) if isinstance(ai_response, str) else ai_response

        except Exception as e:
            logger.error(f"AI assessment failed: {e}")
            return self._create_fallback_assessment(
                site_profile, protocol_requirements, survey_responses, data_completeness
            )

        # Parse AI response into result
        return self._parse_ai_response(
            assessment_data,
            site_profile,
            protocol_requirements,
            data_completeness
        )

    def _get_system_prompt(self) -> str:
        """System prompt for site-facing feasibility assessment"""
        return """You are an expert clinical trial feasibility analyst assessing a site's fit for a specific protocol.

Unlike sponsor-side assessments (which use inferred data), you have ACCESS TO COMPLETE SITE PROFILE DATA directly provided by the site. This means:
- Data confidence should generally be HIGH
- Focus on actionable improvement suggestions, not data gaps
- Identify specific steps the site can take to improve their score
- Highlight strengths as GREEN flags

Your assessment should be:
1. ACCURATE - Score based on actual data provided
2. ACTIONABLE - Every weakness should have a specific improvement suggestion
3. CONSTRUCTIVE - Help sites understand how to become better candidates
4. SPECIFIC - Reference actual data points in your reasoning

Score fairly but constructively. Sites use this to improve their competitiveness."""

    def _build_assessment_prompt(
        self,
        site_profile: Dict,
        protocol_requirements: Dict,
        survey_responses: Optional[Dict],
        data_completeness: float
    ) -> str:
        """Build the assessment prompt using objective criteria-based rubric"""

        # Get the rubric summary for the AI to reference
        rubric_summary = get_rubric_summary()

        site_text = json.dumps(site_profile, indent=2, default=str)
        protocol_text = json.dumps(protocol_requirements, indent=2, default=str)
        survey_text = json.dumps(survey_responses, indent=2, default=str) if survey_responses else "{}"

        return f"""Assess this site's feasibility using the OBJECTIVE SCORING RUBRIC below.

## SCORING RUBRIC (Use These Exact Thresholds)
{rubric_summary}

## SITE PROFILE DATA
{site_text}

## SURVEY RESPONSES
{survey_text}

## PROTOCOL REQUIREMENTS
{protocol_text}

## CRITICAL INSTRUCTIONS

You MUST score each category by evaluating the site against EACH CRITERION in the rubric.

For each criterion:
1. Extract the relevant value from the site profile
2. Find which threshold range the value falls into
3. Assign EXACTLY the points defined in that threshold
4. Document the site's actual value and the threshold matched

## RESPONSE FORMAT (JSON)

{{
    "category_scores": [
        {{
            "category": "historical_performance",
            "score": 85,
            "confidence": "HIGH",
            "reasoning": "Strong historical performance with extensive trial experience.",
            "criteria_scores": [
                {{
                    "criterion_id": "trials_in_indication",
                    "criterion_name": "Trials in Therapeutic Area",
                    "site_value": 45,
                    "site_value_formatted": "45 trials",
                    "threshold_matched": "Extensive (16+ trials)",
                    "points_earned": 30,
                    "max_points": 30,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "historical_performance.studies_by_therapeutic_area"
                }},
                {{
                    "criterion_id": "completion_rate",
                    "criterion_name": "Trial Completion Rate",
                    "site_value": 92,
                    "site_value_formatted": "92%",
                    "threshold_matched": "Good (86-94%)",
                    "points_earned": 20,
                    "max_points": 25,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 5, "required_value": 95, "label": "Excellent (>95%)"}},
                    "data_source": "historical_performance.completion_rate"
                }},
                {{
                    "criterion_id": "enrollment_performance",
                    "criterion_name": "Enrollment vs Targets",
                    "site_value": 110,
                    "site_value_formatted": "110%",
                    "threshold_matched": "Exceeds targets (>100%)",
                    "points_earned": 25,
                    "max_points": 25,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "historical_performance.enrollment_rate"
                }},
                {{
                    "criterion_id": "years_experience",
                    "criterion_name": "Years Conducting Research",
                    "site_value": 25,
                    "site_value_formatted": "25 years",
                    "threshold_matched": "Veteran (20+ years)",
                    "points_earned": 20,
                    "max_points": 20,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "historical_performance.years_conducting_research"
                }}
            ],
            "total_points_earned": 95,
            "total_max_points": 100,
            "improvement_suggestions": ["Increase completion rate to 95%+ for additional 5 points"]
        }},
        {{
            "category": "patient_indication",
            "score": 88,
            "confidence": "HIGH",
            "reasoning": "Excellent patient population access with strong demographics match.",
            "criteria_scores": [
                {{
                    "criterion_id": "patient_volume",
                    "criterion_name": "Patient Volume for Indication",
                    "site_value": 1200,
                    "site_value_formatted": "1,200 patients/year",
                    "threshold_matched": "High volume (1000+/year)",
                    "points_earned": 30,
                    "max_points": 30,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "population_capabilities.patient_population.available_patients_by_condition"
                }},
                {{
                    "criterion_id": "demographics_match",
                    "criterion_name": "Demographics Alignment",
                    "site_value": 85,
                    "site_value_formatted": "85%",
                    "threshold_matched": "Good match (70-89%)",
                    "points_earned": 18,
                    "max_points": 25,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 7, "required_value": 90, "label": "Excellent match (>90%)"}},
                    "data_source": "Calculated from age/demographics alignment"
                }},
                {{
                    "criterion_id": "ie_criteria_fit",
                    "criterion_name": "I/E Criteria Compatibility",
                    "site_value": 80,
                    "site_value_formatted": "80%",
                    "threshold_matched": "High compatibility (>80%)",
                    "points_earned": 25,
                    "max_points": 25,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "Estimated from population characteristics"
                }},
                {{
                    "criterion_id": "competing_trials",
                    "criterion_name": "Competing Trial Impact",
                    "site_value": 2,
                    "site_value_formatted": "2 competing trials",
                    "threshold_matched": "2-3 competing trials",
                    "points_earned": 8,
                    "max_points": 20,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 6, "required_value": 1, "label": "1 competing trial"}},
                    "data_source": "historical_performance.active_studies"
                }}
            ],
            "total_points_earned": 81,
            "total_max_points": 100,
            "improvement_suggestions": ["Reduce competing trial enrollment to minimize overlap"]
        }},
        {{
            "category": "equipment_facilities",
            "score": 92,
            "confidence": "HIGH",
            "reasoning": "Comprehensive equipment and facility capabilities.",
            "criteria_scores": [
                {{
                    "criterion_id": "required_equipment",
                    "criterion_name": "Required Equipment Availability",
                    "site_value": 100,
                    "site_value_formatted": "100%",
                    "threshold_matched": "All equipment available",
                    "points_earned": 40,
                    "max_points": 40,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "facilities_and_equipment.imaging_equipment"
                }},
                {{
                    "criterion_id": "facility_certifications",
                    "criterion_name": "Facility Certifications",
                    "site_value": 100,
                    "site_value_formatted": "All certifications",
                    "threshold_matched": "All certifications",
                    "points_earned": 25,
                    "max_points": 25,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "compliance_and_training.certifications"
                }},
                {{
                    "criterion_id": "lab_capabilities",
                    "criterion_name": "Laboratory Capabilities",
                    "site_value": 90,
                    "site_value_formatted": "Full on-site lab",
                    "threshold_matched": "Full on-site capability",
                    "points_earned": 20,
                    "max_points": 20,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "facilities_and_equipment.laboratory"
                }},
                {{
                    "criterion_id": "storage_requirements",
                    "criterion_name": "Storage Requirements",
                    "site_value": 85,
                    "site_value_formatted": "-80°C freezer available",
                    "threshold_matched": "Most met",
                    "points_earned": 10,
                    "max_points": 15,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 5, "required_value": 100, "label": "All requirements met"}},
                    "data_source": "facilities_and_equipment.pharmacy"
                }}
            ],
            "total_points_earned": 95,
            "total_max_points": 100,
            "improvement_suggestions": []
        }},
        {{
            "category": "staffing_certifications",
            "score": 90,
            "confidence": "HIGH",
            "reasoning": "Highly qualified PI with experienced research team.",
            "criteria_scores": [
                {{
                    "criterion_id": "pi_qualifications",
                    "criterion_name": "PI Experience & Qualifications",
                    "site_value": 50,
                    "site_value_formatted": "50 trials conducted",
                    "threshold_matched": "KOL with 50+ trials",
                    "points_earned": 35,
                    "max_points": 35,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "staff_and_experience.principal_investigator"
                }},
                {{
                    "criterion_id": "coordinator_experience",
                    "criterion_name": "Study Coordinator Experience",
                    "site_value": 5,
                    "site_value_formatted": "5+ years experience",
                    "threshold_matched": "Highly experienced (5+ years)",
                    "points_earned": 25,
                    "max_points": 25,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "staff_and_experience.study_coordinators"
                }},
                {{
                    "criterion_id": "required_certifications",
                    "criterion_name": "Required Certifications",
                    "site_value": 100,
                    "site_value_formatted": "All current",
                    "threshold_matched": "All certifications current",
                    "points_earned": 25,
                    "max_points": 25,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "compliance_and_training.gcp_training"
                }},
                {{
                    "criterion_id": "staff_capacity",
                    "criterion_name": "Staff Capacity & Availability",
                    "site_value": 4,
                    "site_value_formatted": "4 coordinators",
                    "threshold_matched": "3+ dedicated FTEs",
                    "points_earned": 15,
                    "max_points": 15,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "staff_and_experience.study_coordinators.count"
                }}
            ],
            "total_points_earned": 100,
            "total_max_points": 100,
            "improvement_suggestions": []
        }},
        {{
            "category": "emr_workflows",
            "score": 82,
            "confidence": "MODERATE",
            "reasoning": "Strong EDC and EMR capabilities with room for ePRO enhancement.",
            "criteria_scores": [
                {{
                    "criterion_id": "edc_experience",
                    "criterion_name": "EDC System Experience",
                    "site_value": 15,
                    "site_value_formatted": "15 trials with EDC",
                    "threshold_matched": "Expert (10+ trials)",
                    "points_earned": 30,
                    "max_points": 30,
                    "is_max": true,
                    "next_threshold": null,
                    "data_source": "operational_capabilities.data_systems"
                }},
                {{
                    "criterion_id": "emr_integration",
                    "criterion_name": "EMR/EHR Integration",
                    "site_value": 75,
                    "site_value_formatted": "Partial integration",
                    "threshold_matched": "Partially integrated",
                    "points_earned": 17,
                    "max_points": 25,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 8, "required_value": 90, "label": "Fully integrated"}},
                    "data_source": "operational_capabilities.emr_system"
                }},
                {{
                    "criterion_id": "epro_ecoa",
                    "criterion_name": "ePRO/eCOA Capabilities",
                    "site_value": 60,
                    "site_value_formatted": "Basic capability",
                    "threshold_matched": "Basic capability",
                    "points_earned": 16,
                    "max_points": 25,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 9, "required_value": 80, "label": "Advanced capability"}},
                    "data_source": "operational_capabilities.data_systems"
                }},
                {{
                    "criterion_id": "data_quality",
                    "criterion_name": "Data Quality Track Record",
                    "site_value": 85,
                    "site_value_formatted": "7% query rate",
                    "threshold_matched": "Good (5-10% query rate)",
                    "points_earned": 14,
                    "max_points": 20,
                    "is_max": false,
                    "next_threshold": {{"points_gain": 6, "required_value": 90, "label": "Excellent (<5% query rate)"}},
                    "data_source": "historical_performance.data_quality"
                }}
            ],
            "total_points_earned": 77,
            "total_max_points": 100,
            "improvement_suggestions": ["Upgrade EMR integration to achieve full connectivity", "Invest in advanced ePRO/eCOA platform"]
        }}
    ],
    "flags": [
        {{
            "severity": "GREEN",
            "category": "staffing_certifications",
            "title": "KOL-Level PI",
            "details": "PI has conducted 50+ trials, qualifying as Key Opinion Leader",
            "impact": "Maximum 35/35 points for PI qualifications",
            "recommendation": "Highlight KOL status in sponsor communications",
            "potential_score_gain": null
        }},
        {{
            "severity": "YELLOW",
            "category": "emr_workflows",
            "title": "ePRO/eCOA Enhancement Needed",
            "details": "Basic ePRO capability (16/25 points) - advanced capability would add 9 points",
            "impact": "-9 points from maximum in EMR category",
            "recommendation": "Upgrade to advanced ePRO/eCOA platform for studies requiring patient-reported outcomes",
            "potential_score_gain": 9
        }}
    ],
    "improvement_opportunities": [
        {{
            "action": "Upgrade ePRO/eCOA to advanced capability",
            "category": "emr_workflows",
            "estimated_impact": 9,
            "difficulty": "Medium",
            "details": "Reach 80%+ ePRO capability for maximum points"
        }}
    ],
    "ai_assessment": {{
        "summary": "Site demonstrates strong overall feasibility with exceptional staffing (100/100) and equipment (95/100). Primary improvement opportunity is in EMR workflows where ePRO capabilities could be enhanced.",
        "strengths": ["KOL-level PI (50+ trials)", "High patient volume (1,200/year)", "All required equipment available", "Comprehensive certifications"],
        "considerations": ["Basic ePRO capability limits EMR score", "Partial EMR integration"],
        "recommendation": "Highly Recommended"
    }},
    "requirements_comparison": [
        {{
            "requirement": "FibroScan",
            "category": "Equipment",
            "protocol_need": "Required for liver stiffness measurement",
            "site_capability": "FibroScan available",
            "status": "MET",
            "notes": "Device available - contributes to 100% equipment availability"
        }}
    ]
}}

## IMPORTANT RULES

1. For EACH criterion in the rubric, you MUST provide a criteria_scores entry
2. The points_earned MUST match EXACTLY what the rubric threshold specifies (no arbitrary values)
3. site_value should be the actual numeric value extracted from the site profile
4. threshold_matched should be the exact label from the rubric
5. If data is missing, use conservative estimates and set confidence to "LOW"
6. The category score = (total_points_earned / total_max_points) * 100
7. Always include next_threshold info for non-max scores to show improvement path

Respond ONLY with valid JSON."""

    def _calculate_data_completeness(
        self,
        site_profile: Dict,
        survey_responses: Optional[Dict]
    ) -> float:
        """Calculate how complete the site data is"""
        expected_fields = [
            "population_capabilities", "staff_and_experience",
            "facilities_and_equipment", "operational_capabilities",
            "historical_performance", "compliance_and_training"
        ]

        filled = sum(1 for f in expected_fields if site_profile.get(f))
        base_completeness = filled / len(expected_fields)

        # Boost if survey responses exist
        if survey_responses and len(survey_responses) > 0:
            base_completeness = min(1.0, base_completeness + 0.2)

        return base_completeness

    def _parse_ai_response(
        self,
        ai_data: Dict,
        site_profile: Dict,
        protocol_requirements: Dict,
        data_completeness: float
    ) -> AIFeasibilityResult:
        """Parse AI response into AIFeasibilityResult"""

        # Parse category scores
        components = []
        total_weighted = 0

        for cat_data in ai_data.get("category_scores", []):
            category = cat_data.get("category", "unknown")
            score = cat_data.get("score", 50)
            weight = self.WEIGHTS.get(category, 0.2)
            weighted = score * weight
            total_weighted += weighted

            # Extract criteria scores (new format)
            criteria_scores_data = cat_data.get("criteria_scores", [])
            criteria_scores = []
            for cs_data in criteria_scores_data:
                criteria_scores.append(CriterionScore(
                    criterion_id=cs_data.get("criterion_id", ""),
                    criterion_name=cs_data.get("criterion_name", ""),
                    site_value=cs_data.get("site_value", 0),
                    site_value_formatted=cs_data.get("site_value_formatted", ""),
                    threshold_matched=cs_data.get("threshold_matched", ""),
                    points_earned=cs_data.get("points_earned", 0),
                    max_points=cs_data.get("max_points", 0),
                    is_max=cs_data.get("is_max", False),
                    next_threshold=cs_data.get("next_threshold"),
                    data_source=cs_data.get("data_source", "")
                ))

            # Extract totals
            total_points_earned = cat_data.get("total_points_earned")
            total_max_points = cat_data.get("total_max_points")

            # Build details from criteria scores if available
            details = cat_data.get("details", [])
            if criteria_scores and not details:
                # Generate details from criteria scores
                details = [
                    f"{cs.criterion_name}: {cs.points_earned}/{cs.max_points} pts ({cs.threshold_matched})"
                    for cs in criteria_scores
                ]

            # Legacy scoring_breakdown for backward compatibility
            scoring_breakdown = cat_data.get("scoring_breakdown")
            if not scoring_breakdown and criteria_scores:
                # Generate legacy format from criteria scores
                scoring_breakdown = {
                    "base_score": 0,
                    "positive_factors": [
                        {"points": cs.points_earned, "reason": f"{cs.criterion_name}: {cs.site_value_formatted}"}
                        for cs in criteria_scores
                    ],
                    "negative_factors": [],
                    "final_score": score
                }

            components.append(ScoreComponent(
                category=self.CATEGORY_DESCRIPTIONS.get(category, {}).get("name", category),
                score=score,
                weight=weight,
                weighted_score=round(weighted, 2),
                confidence=cat_data.get("confidence", "MODERATE"),
                reasoning=cat_data.get("reasoning", ""),
                details=details,
                improvement_suggestions=cat_data.get("improvement_suggestions", []),
                scoring_breakdown=scoring_breakdown,
                criteria_scores=criteria_scores if criteria_scores else None,
                total_points_earned=total_points_earned,
                total_max_points=total_max_points
            ))

        total_score = round(total_weighted, 1)

        # Determine grade
        grade = "Weak Fit"
        for threshold, g in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if total_score >= threshold:
                grade = g
                break

        # Parse flags
        detailed_flags = []
        simple_flags = []  # Backward compatible

        for flag_data in ai_data.get("flags", []):
            flag = FeasibilityFlag(
                severity=flag_data.get("severity", "YELLOW"),
                category=flag_data.get("category", ""),
                title=flag_data.get("title", ""),
                details=flag_data.get("details", ""),
                impact=flag_data.get("impact", ""),
                recommendation=flag_data.get("recommendation", ""),
                potential_score_gain=flag_data.get("potential_score_gain")
            )
            detailed_flags.append(flag)

            # Create simple flag string for backward compatibility
            if flag.severity in ["RED", "YELLOW"]:
                simple_flags.append(f"{flag.title}: {flag.details}")

        # Parse gaps (from YELLOW/RED flags)
        gaps = [
            f.recommendation
            for f in detailed_flags
            if f.severity in ["RED", "YELLOW"] and f.recommendation
        ]

        # Parse improvement opportunities
        improvements = ai_data.get("improvement_opportunities", [])

        # Parse AI assessment
        ai_assessment = ai_data.get("ai_assessment", {})

        # Parse requirements comparison
        requirements_comparison = ai_data.get("requirements_comparison", [])

        # Determine overall confidence
        confidences = [c.confidence for c in components]
        if all(c == "HIGH" for c in confidences):
            overall_confidence = "HIGH"
        elif any(c == "LOW" for c in confidences):
            overall_confidence = "MODERATE"
        else:
            overall_confidence = "HIGH" if data_completeness > 0.8 else "MODERATE"

        return AIFeasibilityResult(
            total_score=total_score,
            grade=grade,
            components=components,
            flags=simple_flags,
            detailed_flags=detailed_flags,
            gaps=gaps,
            improvement_opportunities=improvements,
            ai_assessment=ai_assessment,
            requirements_comparison=requirements_comparison,
            confidence_level=overall_confidence,
            data_completeness=data_completeness
        )

    def _create_fallback_assessment(
        self,
        site_profile: Dict,
        protocol_requirements: Dict,
        survey_responses: Optional[Dict],
        data_completeness: float
    ) -> AIFeasibilityResult:
        """Create basic assessment when AI fails using rubric-based scoring"""

        components = []
        total_weighted = 0

        # Map categories to profile sections
        category_profile_map = {
            "historical_performance": "historical_performance",
            "patient_indication": "population_capabilities",
            "equipment_facilities": "facilities_and_equipment",
            "staffing_certifications": "staff_and_experience",
            "emr_workflows": "operational_capabilities"
        }

        for category, weight in self.WEIGHTS.items():
            profile_section = category_profile_map.get(category, "")
            section_data = site_profile.get(profile_section, {})
            has_data = bool(section_data)

            # Get rubric criteria for this category
            rubric_category = SCORING_RUBRIC.get(category, {})
            rubric_criteria = rubric_category.get("criteria", [])

            criteria_scores = []
            total_points = 0
            max_points = 0

            for criterion in rubric_criteria:
                crit_max = criterion.get("max_points", 0)
                max_points += crit_max

                # Default to middle threshold if no data
                thresholds = criterion.get("thresholds", [])
                if has_data and thresholds:
                    # Use middle threshold as fallback estimate
                    mid_idx = len(thresholds) // 2
                    threshold = thresholds[mid_idx]
                    points = threshold.get("points", 0)
                    label = threshold.get("label", "Estimated")
                else:
                    # Use lowest threshold if no data
                    threshold = thresholds[-1] if thresholds else {"points": 0, "label": "No data"}
                    points = threshold.get("points", 0)
                    label = threshold.get("label", "No data")

                total_points += points

                # Find next threshold for improvement
                next_thresh = None
                for t in thresholds:
                    if t.get("points", 0) > points:
                        next_thresh = {
                            "points_gain": t["points"] - points,
                            "required_value": t.get("min", 0),
                            "label": t.get("label", "")
                        }
                        break

                criteria_scores.append(CriterionScore(
                    criterion_id=criterion.get("id", ""),
                    criterion_name=criterion.get("name", ""),
                    site_value=0,
                    site_value_formatted="Estimated (AI unavailable)",
                    threshold_matched=label,
                    points_earned=points,
                    max_points=crit_max,
                    is_max=points == crit_max,
                    next_threshold=next_thresh,
                    data_source="Fallback estimation"
                ))

            # Calculate score as percentage
            score = round((total_points / max_points * 100) if max_points > 0 else 50)
            weighted = score * weight
            total_weighted += weighted

            # Create legacy fallback scoring breakdown
            fallback_breakdown = {
                "base_score": 0,
                "positive_factors": [
                    {"points": cs.points_earned, "reason": f"{cs.criterion_name}: {cs.threshold_matched}"}
                    for cs in criteria_scores
                ],
                "negative_factors": [],
                "final_score": score
            }

            components.append(ScoreComponent(
                category=self.CATEGORY_DESCRIPTIONS.get(category, {}).get("name", category),
                score=score,
                weight=weight,
                weighted_score=round(weighted, 2),
                confidence="LOW",
                reasoning="Fallback assessment - AI scoring unavailable. Using rubric-based estimation.",
                details=[f"{cs.criterion_name}: {cs.points_earned}/{cs.max_points} pts" for cs in criteria_scores],
                improvement_suggestions=["Complete site profile for accurate AI-powered assessment"],
                scoring_breakdown=fallback_breakdown,
                criteria_scores=criteria_scores,
                total_points_earned=total_points,
                total_max_points=max_points
            ))

        total_score = round(total_weighted, 1)

        grade = "Weak Fit"
        for threshold, g in sorted(self.GRADE_THRESHOLDS.items(), reverse=True):
            if total_score >= threshold:
                grade = g
                break

        return AIFeasibilityResult(
            total_score=total_score,
            grade=grade,
            components=components,
            flags=["AI assessment unavailable - using fallback scoring"],
            detailed_flags=[
                FeasibilityFlag(
                    severity="YELLOW",
                    category="System",
                    title="Fallback Scoring Active",
                    details="AI assessment was unavailable, using simplified scoring",
                    impact="Scores may be less accurate",
                    recommendation="Try recalculating feasibility",
                    potential_score_gain=None
                )
            ],
            gaps=["Complete site profile for accurate assessment"],
            improvement_opportunities=[{
                "action": "Complete all site profile sections",
                "category": "General",
                "estimated_impact": 10,
                "difficulty": "Medium",
                "details": "Fuller profiles receive more accurate assessments"
            }],
            ai_assessment={
                "summary": "Fallback assessment based on data completeness.",
                "strengths": ["Site profile created"],
                "considerations": ["AI assessment unavailable", "Complete profile for better results"],
                "recommendation": "Recommended with Conditions"
            },
            requirements_comparison=[],
            confidence_level="LOW",
            data_completeness=data_completeness
        )


# Convenience function for backward compatibility with existing code
async def calculate_ai_feasibility_score(
    protocol_requirements: Dict,
    site_profile: Dict,
    pi_name: Optional[str] = None,
    site_name: Optional[str] = None,
    survey_responses: Optional[Dict] = None
) -> Dict:
    """
    Wrapper function that maintains backward compatibility with existing calculate_feasibility_score.

    Returns a dict in the same format as the old FeasibilityResult.to_dict()
    """
    scorer = AIFeasibilityScorer()

    # Add site name to profile if provided
    if site_name:
        site_profile["name"] = site_name

    result = await scorer.calculate_feasibility(
        site_profile=site_profile,
        protocol_requirements=protocol_requirements,
        survey_responses=survey_responses
    )

    return result.to_dict()
