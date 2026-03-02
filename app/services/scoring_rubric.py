"""
Industry-Standard Feasibility Scoring Rubric

Each category has specific criteria with defined thresholds.
The AI evaluates site data against these criteria for objective scoring.
"""
from typing import Dict, List, Optional, Any

SCORING_RUBRIC = {
    "historical_performance": {
        "name": "Historical Performance & Experience",
        "weight": 0.30,
        "max_score": 100,
        "criteria": [
            {
                "id": "trials_in_indication",
                "name": "Trials in Therapeutic Area",
                "max_points": 30,
                "description": "Number of completed trials in the target indication",
                "thresholds": [
                    {"min": 16, "max": None, "points": 30, "label": "Extensive (16+ trials)"},
                    {"min": 6, "max": 15, "points": 20, "label": "Good (6-15 trials)"},
                    {"min": 1, "max": 5, "points": 10, "label": "Limited (1-5 trials)"},
                    {"min": 0, "max": 0, "points": 0, "label": "None"}
                ]
            },
            {
                "id": "completion_rate",
                "name": "Trial Completion Rate",
                "max_points": 25,
                "description": "Percentage of trials completed vs terminated",
                "thresholds": [
                    {"min": 95, "max": 100, "points": 25, "label": "Excellent (>95%)"},
                    {"min": 86, "max": 94, "points": 20, "label": "Good (86-94%)"},
                    {"min": 70, "max": 85, "points": 15, "label": "Moderate (70-85%)"},
                    {"min": 0, "max": 69, "points": 5, "label": "Below Average (<70%)"}
                ]
            },
            {
                "id": "enrollment_performance",
                "name": "Enrollment vs Targets",
                "max_points": 25,
                "description": "Historical enrollment performance relative to targets",
                "thresholds": [
                    {"min": 100, "max": None, "points": 25, "label": "Exceeds targets (>100%)"},
                    {"min": 80, "max": 99, "points": 15, "label": "Meets targets (80-99%)"},
                    {"min": 50, "max": 79, "points": 8, "label": "Below targets (50-79%)"},
                    {"min": 0, "max": 49, "points": 3, "label": "Significantly below (<50%)"}
                ]
            },
            {
                "id": "years_experience",
                "name": "Years Conducting Research",
                "max_points": 20,
                "description": "Site/PI experience in clinical research",
                "thresholds": [
                    {"min": 20, "max": None, "points": 20, "label": "Veteran (20+ years)"},
                    {"min": 11, "max": 19, "points": 15, "label": "Experienced (11-19 years)"},
                    {"min": 5, "max": 10, "points": 10, "label": "Established (5-10 years)"},
                    {"min": 0, "max": 4, "points": 5, "label": "Emerging (<5 years)"}
                ]
            }
        ]
    },
    "patient_indication": {
        "name": "Patient Population & Indication Match",
        "weight": 0.25,
        "max_score": 100,
        "criteria": [
            {
                "id": "patient_volume",
                "name": "Patient Volume for Indication",
                "max_points": 30,
                "description": "Annual patient volume for target indication",
                "thresholds": [
                    {"min": 1000, "max": None, "points": 30, "label": "High volume (1000+/year)"},
                    {"min": 500, "max": 999, "points": 22, "label": "Good volume (500-999/year)"},
                    {"min": 100, "max": 499, "points": 14, "label": "Moderate (100-499/year)"},
                    {"min": 0, "max": 99, "points": 6, "label": "Limited (<100/year)"}
                ]
            },
            {
                "id": "demographics_match",
                "name": "Demographics Alignment",
                "max_points": 25,
                "description": "How well patient demographics match protocol requirements",
                "thresholds": [
                    {"min": 90, "max": 100, "points": 25, "label": "Excellent match (>90%)"},
                    {"min": 70, "max": 89, "points": 18, "label": "Good match (70-89%)"},
                    {"min": 50, "max": 69, "points": 10, "label": "Partial match (50-69%)"},
                    {"min": 0, "max": 49, "points": 4, "label": "Poor match (<50%)"}
                ]
            },
            {
                "id": "ie_criteria_fit",
                "name": "I/E Criteria Compatibility",
                "max_points": 25,
                "description": "Patient population fit with inclusion/exclusion criteria",
                "thresholds": [
                    {"min": 80, "max": 100, "points": 25, "label": "High compatibility (>80%)"},
                    {"min": 60, "max": 79, "points": 17, "label": "Moderate (60-79%)"},
                    {"min": 40, "max": 59, "points": 10, "label": "Limited (40-59%)"},
                    {"min": 0, "max": 39, "points": 4, "label": "Poor fit (<40%)"}
                ]
            },
            {
                "id": "competing_trials",
                "name": "Competing Trial Impact",
                "max_points": 20,
                "description": "Impact of competing trials on patient availability",
                "thresholds": [
                    {"min": 0, "max": 0, "points": 20, "label": "No competing trials"},
                    {"min": 1, "max": 1, "points": 14, "label": "1 competing trial"},
                    {"min": 2, "max": 3, "points": 8, "label": "2-3 competing trials"},
                    {"min": 4, "max": None, "points": 3, "label": "4+ competing trials"}
                ]
            }
        ]
    },
    "equipment_facilities": {
        "name": "Equipment & Facilities",
        "weight": 0.20,
        "max_score": 100,
        "criteria": [
            {
                "id": "required_equipment",
                "name": "Required Equipment Availability",
                "max_points": 40,
                "description": "Percentage of protocol-required equipment available",
                "thresholds": [
                    {"min": 100, "max": 100, "points": 40, "label": "All equipment available"},
                    {"min": 80, "max": 99, "points": 30, "label": "Most available (80-99%)"},
                    {"min": 50, "max": 79, "points": 18, "label": "Partial (50-79%)"},
                    {"min": 0, "max": 49, "points": 6, "label": "Significant gaps (<50%)"}
                ]
            },
            {
                "id": "facility_certifications",
                "name": "Facility Certifications",
                "max_points": 25,
                "description": "Required facility certifications and accreditations",
                "thresholds": [
                    {"min": 100, "max": 100, "points": 25, "label": "All certifications"},
                    {"min": 75, "max": 99, "points": 18, "label": "Most certifications"},
                    {"min": 50, "max": 74, "points": 10, "label": "Some certifications"},
                    {"min": 0, "max": 49, "points": 4, "label": "Missing critical certs"}
                ]
            },
            {
                "id": "lab_capabilities",
                "name": "Laboratory Capabilities",
                "max_points": 20,
                "description": "On-site vs central lab capabilities",
                "thresholds": [
                    {"min": 90, "max": 100, "points": 20, "label": "Full on-site capability"},
                    {"min": 60, "max": 89, "points": 14, "label": "Good capability"},
                    {"min": 30, "max": 59, "points": 8, "label": "Basic capability"},
                    {"min": 0, "max": 29, "points": 3, "label": "Limited"}
                ]
            },
            {
                "id": "storage_requirements",
                "name": "Storage Requirements",
                "max_points": 15,
                "description": "Temperature-controlled storage, sample handling",
                "thresholds": [
                    {"min": 100, "max": 100, "points": 15, "label": "All requirements met"},
                    {"min": 70, "max": 99, "points": 10, "label": "Most met"},
                    {"min": 40, "max": 69, "points": 5, "label": "Partial"},
                    {"min": 0, "max": 39, "points": 2, "label": "Not met"}
                ]
            }
        ]
    },
    "staffing_certifications": {
        "name": "Staffing & Certifications",
        "weight": 0.15,
        "max_score": 100,
        "criteria": [
            {
                "id": "pi_qualifications",
                "name": "PI Experience & Qualifications",
                "max_points": 35,
                "description": "Principal Investigator experience and KOL status",
                "thresholds": [
                    {"min": 50, "max": None, "points": 35, "label": "KOL with 50+ trials"},
                    {"min": 20, "max": 49, "points": 28, "label": "Very experienced (20-49)"},
                    {"min": 10, "max": 19, "points": 20, "label": "Experienced (10-19)"},
                    {"min": 5, "max": 9, "points": 12, "label": "Moderate (5-9)"},
                    {"min": 0, "max": 4, "points": 5, "label": "Limited (<5 trials)"}
                ]
            },
            {
                "id": "coordinator_experience",
                "name": "Study Coordinator Experience",
                "max_points": 25,
                "description": "Coordinator experience in similar trials",
                "thresholds": [
                    {"min": 5, "max": None, "points": 25, "label": "Highly experienced (5+ years)"},
                    {"min": 3, "max": 4, "points": 18, "label": "Experienced (3-4 years)"},
                    {"min": 1, "max": 2, "points": 10, "label": "Some experience (1-2 years)"},
                    {"min": 0, "max": 0, "points": 4, "label": "New coordinator"}
                ]
            },
            {
                "id": "required_certifications",
                "name": "Required Certifications",
                "max_points": 25,
                "description": "GCP, protocol-specific certifications",
                "thresholds": [
                    {"min": 100, "max": 100, "points": 25, "label": "All certifications current"},
                    {"min": 80, "max": 99, "points": 18, "label": "Most current"},
                    {"min": 50, "max": 79, "points": 10, "label": "Some current"},
                    {"min": 0, "max": 49, "points": 3, "label": "Significant gaps"}
                ]
            },
            {
                "id": "staff_capacity",
                "name": "Staff Capacity & Availability",
                "max_points": 15,
                "description": "Dedicated FTEs and availability",
                "thresholds": [
                    {"min": 3, "max": None, "points": 15, "label": "3+ dedicated FTEs"},
                    {"min": 2, "max": 2, "points": 11, "label": "2 dedicated FTEs"},
                    {"min": 1, "max": 1, "points": 7, "label": "1 dedicated FTE"},
                    {"min": 0, "max": 0, "points": 2, "label": "No dedicated staff"}
                ]
            }
        ]
    },
    "emr_workflows": {
        "name": "EMR & Data Workflows",
        "weight": 0.10,
        "max_score": 100,
        "criteria": [
            {
                "id": "edc_experience",
                "name": "EDC System Experience",
                "max_points": 30,
                "description": "Experience with electronic data capture systems",
                "thresholds": [
                    {"min": 10, "max": None, "points": 30, "label": "Expert (10+ trials)"},
                    {"min": 5, "max": 9, "points": 22, "label": "Experienced (5-9 trials)"},
                    {"min": 1, "max": 4, "points": 12, "label": "Some experience (1-4)"},
                    {"min": 0, "max": 0, "points": 4, "label": "No EDC experience"}
                ]
            },
            {
                "id": "emr_integration",
                "name": "EMR/EHR Integration",
                "max_points": 25,
                "description": "Electronic health record integration capability",
                "thresholds": [
                    {"min": 90, "max": 100, "points": 25, "label": "Fully integrated"},
                    {"min": 60, "max": 89, "points": 17, "label": "Partially integrated"},
                    {"min": 30, "max": 59, "points": 9, "label": "Manual extraction"},
                    {"min": 0, "max": 29, "points": 3, "label": "No integration"}
                ]
            },
            {
                "id": "epro_ecoa",
                "name": "ePRO/eCOA Capabilities",
                "max_points": 25,
                "description": "Electronic patient-reported outcomes capability",
                "thresholds": [
                    {"min": 80, "max": 100, "points": 25, "label": "Advanced capability"},
                    {"min": 50, "max": 79, "points": 16, "label": "Basic capability"},
                    {"min": 20, "max": 49, "points": 8, "label": "Limited"},
                    {"min": 0, "max": 19, "points": 0, "label": "No capability"}
                ]
            },
            {
                "id": "data_quality",
                "name": "Data Quality Track Record",
                "max_points": 20,
                "description": "Historical query rates and data quality",
                "thresholds": [
                    {"min": 90, "max": 100, "points": 20, "label": "Excellent (<5% query rate)"},
                    {"min": 75, "max": 89, "points": 14, "label": "Good (5-10% query rate)"},
                    {"min": 50, "max": 74, "points": 8, "label": "Average (10-20% query)"},
                    {"min": 0, "max": 49, "points": 3, "label": "Below average (>20%)"}
                ]
            }
        ]
    }
}


def get_threshold_for_value(thresholds: List[Dict], value: float) -> Dict:
    """Find the matching threshold for a given value."""
    for threshold in thresholds:
        min_val = threshold.get("min", 0)
        max_val = threshold.get("max")

        if max_val is None:  # No upper bound
            if value >= min_val:
                return threshold
        elif min_val <= value <= max_val:
            return threshold

    # Return lowest threshold if no match
    return thresholds[-1]


def get_next_threshold(thresholds: List[Dict], current: Dict) -> Optional[Dict]:
    """Get the next higher threshold (for improvement suggestions)."""
    current_points = current["points"]

    for threshold in thresholds:
        if threshold["points"] > current_points:
            return {
                "points_gain": threshold["points"] - current_points,
                "required_value": threshold["min"],
                "label": threshold["label"]
            }

    return None  # Already at max


def calculate_criterion_score(criterion: Dict, value: float) -> Dict:
    """Calculate score for a single criterion based on site data."""
    threshold = get_threshold_for_value(criterion["thresholds"], value)
    next_thresh = get_next_threshold(criterion["thresholds"], threshold)

    return {
        "criterion_id": criterion["id"],
        "criterion_name": criterion["name"],
        "max_points": criterion["max_points"],
        "earned_points": threshold["points"],
        "site_value": value,
        "threshold_label": threshold["label"],
        "is_max": threshold["points"] == criterion["max_points"],
        "points_missed": criterion["max_points"] - threshold["points"],
        "next_threshold": next_thresh
    }


def get_rubric_summary() -> str:
    """Generate a text summary of the rubric for the AI prompt."""
    summary_lines = []

    for cat_id, category in SCORING_RUBRIC.items():
        summary_lines.append(f"\n## {category['name']} (Weight: {category['weight']*100:.0f}%)")
        summary_lines.append(f"Max Score: {category['max_score']} points")
        summary_lines.append("\nCriteria:")

        for criterion in category['criteria']:
            summary_lines.append(f"\n### {criterion['name']} ({criterion['max_points']} pts max)")
            summary_lines.append(f"   {criterion['description']}")
            summary_lines.append("   Thresholds:")
            for t in criterion['thresholds']:
                max_str = f"-{t['max']}" if t['max'] is not None else "+"
                summary_lines.append(f"     - {t['min']}{max_str}: {t['points']} pts ({t['label']})")

    return "\n".join(summary_lines)
