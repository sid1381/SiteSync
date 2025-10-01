"""
Comprehensive Feasibility Scorer with Disqualifier Logic
Implements SME-guided scoring with critical disqualifier checks
"""

from typing import Dict, List, Any, Tuple
from dataclasses import dataclass

@dataclass
class FeasibilityResult:
    score: int
    confidence: float
    category_scores: Dict[str, float]
    disqualifier: str = None
    recommendation: str = ""
    critical_gaps: List[str] = None
    flags: List[str] = None

class ComprehensiveFeasibilityScorer:
    """
    Comprehensive feasibility scoring with disqualifier logic for clinical research sites
    """

    def __init__(self):
        self.category_weights = {
            "population_access": 30,
            "equipment_match": 25,
            "staff_capacity": 20,
            "historical_performance": 15,
            "operational_readiness": 10
        }

    def calculate_feasibility_score(self, site_profile: Dict, protocol_requirements: Dict = None) -> FeasibilityResult:
        """
        Calculate comprehensive feasibility score with disqualifier checks
        """

        # STEP 1: Critical Disqualifier Checks
        disqualifier = self._check_disqualifiers(site_profile, protocol_requirements)
        if disqualifier:
            return FeasibilityResult(
                score=0,
                confidence=0.9,
                category_scores={},
                disqualifier=disqualifier,
                recommendation="Not Recommended - Critical disqualifier",
                critical_gaps=[disqualifier],
                flags=[f"Disqualified: {disqualifier}"]
            )

        # STEP 2: Calculate category scores
        category_scores = {
            "population_access": self._score_population_access(site_profile, protocol_requirements),
            "equipment_match": self._score_equipment_match(site_profile, protocol_requirements),
            "staff_capacity": self._score_staff_capacity(site_profile, protocol_requirements),
            "historical_performance": self._score_historical_performance(site_profile),
            "operational_readiness": self._score_operational_readiness(site_profile)
        }

        # STEP 3: Calculate weighted total score
        total_score = sum(
            category_scores[category] * (self.category_weights[category] / 100)
            for category in category_scores
        )

        # STEP 4: Calculate confidence based on data completeness
        confidence = self._calculate_confidence(site_profile)

        # STEP 5: Identify critical gaps and flags
        critical_gaps = self._identify_critical_gaps(site_profile, category_scores)
        flags = self._generate_flags(site_profile, category_scores)

        # STEP 6: Generate recommendation
        recommendation = self._get_recommendation(int(total_score))

        return FeasibilityResult(
            score=int(total_score),
            confidence=confidence,
            category_scores=category_scores,
            recommendation=recommendation,
            critical_gaps=critical_gaps,
            flags=flags
        )

    def _check_disqualifiers(self, site_profile: Dict, protocol_requirements: Dict = None) -> str:
        """
        Check for critical disqualifiers that would make the site unsuitable
        """

        # Check for basic staff presence
        staff = site_profile.get('staff_and_experience', {})
        coordinators = staff.get('coordinators', {}).get('count', 0)
        investigators = staff.get('investigators', {}).get('count', 0)

        if coordinators == 0 and investigators == 0:
            return "no_research_staff"

        # Check for basic patient population
        pop_caps = site_profile.get('population_capabilities', {})
        annual_volume = pop_caps.get('annual_patient_volume', 0)

        if annual_volume == 0:
            return "no_patient_population"

        # Check for basic compliance/training
        compliance = site_profile.get('compliance_and_training', {})
        if not compliance.get('GCP_training'):
            return "no_gcp_training"

        # Check for poor performance history
        history = site_profile.get('historical_performance', {})
        if history.get('protocol_deviation_rate', "").startswith(">10%"):
            return "poor_compliance_history"

        # No critical disqualifiers found
        return None

    def _score_population_access(self, site_profile: Dict, protocol_requirements: Dict = None) -> float:
        """
        Score population access capabilities (0-100)
        """
        pop_caps = site_profile.get('population_capabilities', {})

        score = 0

        # Annual patient volume scoring
        annual_volume = pop_caps.get('annual_patient_volume', 0)
        if annual_volume >= 10000:
            score += 40
        elif annual_volume >= 5000:
            score += 30
        elif annual_volume >= 1000:
            score += 20
        elif annual_volume > 0:
            score += 10

        # Age group diversity
        age_groups = pop_caps.get('age_groups_treated', [])
        if len(age_groups) >= 3:
            score += 20
        elif len(age_groups) >= 2:
            score += 15
        elif len(age_groups) >= 1:
            score += 10

        # Health condition diversity
        conditions = pop_caps.get('common_health_conditions', [])
        if len(conditions) >= 5:
            score += 25
        elif len(conditions) >= 3:
            score += 20
        elif len(conditions) >= 1:
            score += 15

        # Special populations capability
        if pop_caps.get('special_populations'):
            score += 15

        return min(score, 100)

    def _score_equipment_match(self, site_profile: Dict, protocol_requirements: Dict = None) -> float:
        """
        Score equipment and facility capabilities (0-100)
        """
        facilities = site_profile.get('facilities_and_equipment', {})

        score = 0

        # Imaging capabilities
        imaging = facilities.get('imaging', [])
        imaging_score = min(len(imaging) * 10, 30)  # Up to 30 points
        score += imaging_score

        # Lab capabilities
        lab_caps = facilities.get('lab_capabilities', {})
        if lab_caps.get('onsite_clinical_lab'):
            score += 20
        if lab_caps.get('CLIA_certified'):
            score += 15
        if lab_caps.get('freezer_-80C'):
            score += 15
        if lab_caps.get('temperature_monitoring'):
            score += 10

        # Procedure rooms and facilities
        procedure_rooms = facilities.get('procedure_rooms', 0)
        if procedure_rooms >= 4:
            score += 10
        elif procedure_rooms >= 2:
            score += 7
        elif procedure_rooms >= 1:
            score += 5

        return min(score, 100)

    def _score_staff_capacity(self, site_profile: Dict, protocol_requirements: Dict = None) -> float:
        """
        Score staff capacity and experience (0-100)
        """
        staff = site_profile.get('staff_and_experience', {})

        score = 0

        # Coordinators
        coordinators = staff.get('coordinators', {})
        coord_count = coordinators.get('count', 0)
        if coord_count >= 5:
            score += 25
        elif coord_count >= 3:
            score += 20
        elif coord_count >= 2:
            score += 15
        elif coord_count >= 1:
            score += 10

        # Investigators
        investigators = staff.get('investigators', {})
        inv_count = investigators.get('count', 0)
        if inv_count >= 3:
            score += 20
        elif inv_count >= 2:
            score += 15
        elif inv_count >= 1:
            score += 10

        # Experience and training
        coord_experience = coordinators.get('average_years_experience', 0)
        if coord_experience >= 5:
            score += 15
        elif coord_experience >= 3:
            score += 10
        elif coord_experience >= 1:
            score += 5

        # Certifications
        certifications = coordinators.get('certifications', [])
        if len(certifications) >= 2:
            score += 15
        elif len(certifications) >= 1:
            score += 10

        # Coverage
        if investigators.get('coverage', '').find('24/7') != -1:
            score += 15

        return min(score, 100)

    def _score_historical_performance(self, site_profile: Dict) -> float:
        """
        Score historical performance and experience (0-100)
        """
        history = site_profile.get('historical_performance', {})

        score = 0

        # Study volume
        studies_5_years = history.get('studies_conducted_last_5_years', 0)
        if studies_5_years >= 30:
            score += 25
        elif studies_5_years >= 20:
            score += 20
        elif studies_5_years >= 10:
            score += 15
        elif studies_5_years >= 5:
            score += 10

        # Enrollment success rate
        enrollment_success = history.get('enrollment_success_rate', '')
        if '85%' in enrollment_success or '90%' in enrollment_success or '95%' in enrollment_success:
            score += 25
        elif '75%' in enrollment_success or '80%' in enrollment_success:
            score += 20
        elif '70%' in enrollment_success:
            score += 15

        # Retention rate
        retention_rate = history.get('retention_rate', '')
        if '95%' in retention_rate or '90%' in retention_rate:
            score += 20
        elif '85%' in retention_rate:
            score += 15
        elif '80%' in retention_rate:
            score += 10

        # Protocol deviation rate
        deviation_rate = history.get('protocol_deviation_rate', '')
        if '<2%' in deviation_rate or '<3%' in deviation_rate:
            score += 15
        elif '<5%' in deviation_rate:
            score += 10

        # Query resolution time
        query_time = history.get('average_query_resolution_time', '')
        if '3 days' in query_time or '2 days' in query_time or '1 day' in query_time:
            score += 15
        elif '5 days' in query_time or '4 days' in query_time:
            score += 10

        return min(score, 100)

    def _score_operational_readiness(self, site_profile: Dict) -> float:
        """
        Score operational capabilities and readiness (0-100)
        """
        ops = site_profile.get('operational_capabilities', {})

        score = 0

        # Inpatient/outpatient capabilities
        if ops.get('inpatient_support'):
            score += 25
        if ops.get('outpatient_clinic'):
            score += 25

        # Department coordination
        departments = ops.get('departments_involved', [])
        if len(departments) >= 4:
            score += 20
        elif len(departments) >= 2:
            score += 15
        elif len(departments) >= 1:
            score += 10

        # Data systems
        if ops.get('data_systems'):
            if 'CTMS' in ops['data_systems'] and 'EDC' in ops['data_systems']:
                score += 15
            elif 'CTMS' in ops['data_systems'] or 'EDC' in ops['data_systems']:
                score += 10

        # Monitoring accommodations
        if ops.get('monitoring_accommodations'):
            score += 10

        # Pharmacy
        if ops.get('pharmacy'):
            score += 5

        return min(score, 100)

    def _calculate_confidence(self, site_profile: Dict) -> float:
        """
        Calculate confidence based on data completeness
        """
        total_sections = 6
        completed_sections = 0

        sections = [
            'population_capabilities',
            'staff_and_experience',
            'facilities_and_equipment',
            'operational_capabilities',
            'historical_performance',
            'compliance_and_training'
        ]

        for section in sections:
            section_data = site_profile.get(section, {})
            if section_data and len(section_data) > 0:
                completed_sections += 1

        return completed_sections / total_sections

    def _identify_critical_gaps(self, site_profile: Dict, category_scores: Dict) -> List[str]:
        """
        Identify critical gaps that need attention
        """
        gaps = []

        if category_scores.get('population_access', 0) < 50:
            gaps.append("Limited patient population access")

        if category_scores.get('equipment_match', 0) < 50:
            gaps.append("Equipment capabilities may be insufficient")

        if category_scores.get('staff_capacity', 0) < 50:
            gaps.append("Staff capacity concerns")

        if category_scores.get('historical_performance', 0) < 50:
            gaps.append("Limited historical performance data")

        return gaps

    def _generate_flags(self, site_profile: Dict, category_scores: Dict) -> List[str]:
        """
        Generate warning flags for potential issues
        """
        flags = []

        # Check current study load
        history = site_profile.get('historical_performance', {})
        current_studies = history.get('current_active_studies', 0)
        if current_studies >= 10:
            flags.append("High current study load")
        elif current_studies >= 6:
            flags.append("Moderate current study load")

        # Check for low scores
        for category, score in category_scores.items():
            if score < 60:
                flags.append(f"Low {category.replace('_', ' ')} score")

        return flags

    def _get_recommendation(self, score: int) -> str:
        """
        Generate recommendation based on total score
        """
        if score >= 85:
            return "Highly Recommended - Excellent fit"
        elif score >= 70:
            return "Recommended - Good fit with minor gaps"
        elif score >= 50:
            return "Conditional - Significant gaps need addressing"
        else:
            return "Not Recommended - Major feasibility concerns"