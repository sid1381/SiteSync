import httpx
import asyncio
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import json

@dataclass
class ScoreComponent:
    category: str
    score: float  # 0-100
    weight: float  # decimal weight (0.30 = 30%)
    weighted_score: float
    rationale: str
    flags: List[str]
    requirements_met: List[str]
    requirements_missing: List[str]

@dataclass
class FeasibilityResult:
    total_score: float
    grade: str  # "Strong Fit", "Good Fit", "Moderate Fit", "Weak Fit"
    components: List[ScoreComponent]
    flags: List[str]
    gaps: List[str]
    requirements_comparison: List[Dict]  # Protocol vs Site table data
    ai_assessment: Dict  # AI-generated narrative assessment

    def to_dict(self) -> Dict:
        return {
            "total_score": self.total_score,
            "grade": self.grade,
            "components": [asdict(c) for c in self.components],
            "flags": self.flags,
            "gaps": self.gaps,
            "requirements_comparison": self.requirements_comparison,
            "ai_assessment": self.ai_assessment
        }


class FeasibilityScorer:
    """
    Calculates feasibility scores by comparing protocol requirements
    against site capabilities and historical performance data.
    """

    WEIGHTS = {
        "historical_performance": 0.30,
        "patient_indication": 0.25,
        "equipment_facilities": 0.20,
        "staffing_certifications": 0.15,
        "emr_workflows": 0.10
    }

    CT_GOV_API_BASE = "https://clinicaltrials.gov/api/v2"

    def __init__(self):
        self.http_client = None

    def _get_grade(self, score: float) -> str:
        if score >= 85:
            return "Strong Fit"
        elif score >= 70:
            return "Good Fit"
        elif score >= 55:
            return "Moderate Fit"
        else:
            return "Weak Fit"

    async def calculate_feasibility(
        self,
        protocol_requirements: Dict,
        site_profile: Dict,
        pi_name: Optional[str] = None,
        site_name: Optional[str] = None
    ) -> FeasibilityResult:
        """Main entry point for feasibility scoring"""

        components = []
        all_flags = []
        all_gaps = []
        requirements_comparison = []

        # Extract PI name from site profile if not provided
        if not pi_name:
            staff = site_profile.get("staff_and_experience", {})
            pi = staff.get("principal_investigator", {})
            pi_name = pi.get("name", "")

        # 1. Historical Performance (30%) - from CT.gov
        hist_score = await self._score_historical_performance(
            pi_name, site_name, protocol_requirements, site_profile
        )
        components.append(hist_score)
        all_flags.extend(hist_score.flags)

        # 2. Patient Indication (25%) - site profile + protocol match
        patient_score, patient_comparisons = self._score_patient_indication(
            protocol_requirements, site_profile
        )
        components.append(patient_score)
        all_flags.extend(patient_score.flags)
        requirements_comparison.extend(patient_comparisons)

        # 3. Equipment & Facilities (20%) - site profile vs requirements
        equip_score, equip_comparisons = self._score_equipment_facilities(
            protocol_requirements, site_profile
        )
        components.append(equip_score)
        all_flags.extend(equip_score.flags)
        requirements_comparison.extend(equip_comparisons)

        # 4. Staffing & Certifications (15%)
        staff_score, staff_comparisons = self._score_staffing(
            protocol_requirements, site_profile
        )
        components.append(staff_score)
        all_flags.extend(staff_score.flags)
        requirements_comparison.extend(staff_comparisons)

        # 5. EMR & Workflows (10%)
        emr_score = self._score_emr_workflows(
            protocol_requirements, site_profile
        )
        components.append(emr_score)
        all_flags.extend(emr_score.flags)

        # Calculate total
        total = sum(c.weighted_score for c in components)

        # Identify gaps (scores below 60 in any category)
        for c in components:
            if c.score < 60:
                all_gaps.append(f"{c.category}: {c.rationale}")

        # Generate AI-powered narrative assessment
        ai_assessment = await self._generate_ai_assessment(
            protocol_requirements,
            site_profile,
            {
                "total_score": total,
                "grade": self._get_grade(total),
                "flags": all_flags,
                "gaps": all_gaps
            }
        )

        return FeasibilityResult(
            total_score=round(total, 1),
            grade=self._get_grade(total),
            components=components,
            flags=all_flags,
            gaps=all_gaps,
            requirements_comparison=requirements_comparison,
            ai_assessment=ai_assessment
        )

    async def _query_ctgov(self, query_params: Dict) -> Dict:
        """Query ClinicalTrials.gov API v2"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.CT_GOV_API_BASE}/studies",
                    params=query_params
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            print(f"CT.gov API error: {e}")
            return {"studies": []}

    async def _score_historical_performance(
        self,
        pi_name: Optional[str],
        site_name: Optional[str],
        protocol_requirements: Dict,
        site_profile: Dict
    ) -> ScoreComponent:
        """
        Score based on PI/site historical trial performance
        Uses CT.gov API + site profile historical_performance
        """
        score = 70  # Default baseline
        rationale_parts = []
        flags = []
        met = []
        missing = []

        # Check site's internal historical data first
        historical = site_profile.get("historical_performance", {})

        studies_completed = historical.get("studies_completed_last_5_years", 0)
        patients_enrolled = historical.get("patients_enrolled_last_5_years", 0)
        phase_experience = historical.get("phase_experience", {})
        therapeutic_exp = historical.get("therapeutic_experience", [])

        # Score based on studies completed
        if studies_completed >= 40:
            score = 90
            met.append(f"{studies_completed} studies completed in 5 years")
            rationale_parts.append(f"Excellent track record: {studies_completed} studies")
        elif studies_completed >= 20:
            score = 80
            met.append(f"{studies_completed} studies completed")
            rationale_parts.append(f"Strong experience: {studies_completed} studies")
        elif studies_completed >= 10:
            score = 70
            met.append(f"{studies_completed} studies completed")
            rationale_parts.append(f"Moderate experience: {studies_completed} studies")
        else:
            score = 55
            missing.append("Limited trial history (<10 studies in 5 years)")
            flags.append("Limited site trial experience")
            rationale_parts.append(f"Limited experience: {studies_completed} studies")

        # Check phase experience match
        required_phase = protocol_requirements.get("study_identification", {}).get("phase", "")
        if required_phase:
            phase_key = required_phase.replace(" ", "_")
            if phase_experience.get(phase_key, False):
                score += 5
                met.append(f"{required_phase} experience confirmed")
            else:
                flags.append(f"No documented {required_phase} experience")
                missing.append(f"{required_phase} experience")

        # Check therapeutic area match
        indication = protocol_requirements.get("patient_population", {}).get("primary_indication", "").lower()
        if indication:
            therapeutic_match = any(indication in t.lower() for t in therapeutic_exp)
            if therapeutic_match:
                score += 5
                met.append("Therapeutic area experience confirmed")
            else:
                flags.append(f"No documented experience in {indication}")

        # Query CT.gov for PI if available (bonus points)
        if pi_name and len(pi_name) > 3:
            try:
                results = await self._query_ctgov({
                    "query.term": pi_name,
                    "filter.overallStatus": "COMPLETED",
                    "pageSize": 10
                })
                ct_trials = len(results.get("studies", []))
                if ct_trials > 0:
                    score = min(score + 5, 100)
                    met.append(f"PI found in CT.gov with {ct_trials} completed trials")
                    rationale_parts.append(f"PI verified in CT.gov")
            except Exception as e:
                print(f"CT.gov lookup failed: {e}")

        score = min(score, 100)
        weighted = score * self.WEIGHTS["historical_performance"]

        return ScoreComponent(
            category="Historical Performance",
            score=score,
            weight=self.WEIGHTS["historical_performance"],
            weighted_score=round(weighted, 1),
            rationale="; ".join(rationale_parts) if rationale_parts else "Baseline score applied",
            flags=flags,
            requirements_met=met,
            requirements_missing=missing
        )

    def _score_patient_indication(
        self,
        protocol_requirements: Dict,
        site_profile: Dict
    ) -> tuple[ScoreComponent, List[Dict]]:
        """
        Score based on patient population match
        """
        score = 70
        rationale_parts = []
        flags = []
        met = []
        missing = []
        comparisons = []

        patient_pop = protocol_requirements.get("patient_population", {})
        indication = patient_pop.get("primary_indication", "").lower()

        timeline = protocol_requirements.get("study_timeline", {})
        enrollment_target = timeline.get("enrollment_target", 0)

        age_min = patient_pop.get("age_min", 0)
        age_max = patient_pop.get("age_max", 100)

        population = site_profile.get("population_capabilities", {})
        patient_data = population.get("patient_population", {})
        available_patients = patient_data.get("available_patients_by_condition", {})
        annual_visits = patient_data.get("annual_patient_visits", 0)

        # Match indication
        matched_count = 0
        matched_condition = None
        for condition, count in available_patients.items():
            if indication and (indication in condition.lower() or condition.lower() in indication):
                matched_count = count
                matched_condition = condition
                break

        # Also check for partial matches (NASH, nash, etc.)
        if not matched_count and indication:
            for condition, count in available_patients.items():
                # Check for key terms
                indication_terms = indication.replace("-", " ").split()
                for term in indication_terms:
                    if len(term) > 3 and term in condition.lower():
                        matched_count = count
                        matched_condition = condition
                        break

        # Build comparison row for indication
        if matched_count > 0:
            if enrollment_target and matched_count >= enrollment_target * 3:
                score = 95
                status = "✅"
                rationale_parts.append(f"{matched_count:,} patients available (3x+ target)")
                met.append(f"{matched_condition}: {matched_count:,} patients")
            elif enrollment_target and matched_count >= enrollment_target:
                score = 80
                status = "✅"
                rationale_parts.append(f"{matched_count:,} patients available (meets target)")
                met.append(f"Patient volume meets enrollment target")
            else:
                score = 65
                status = "⚠️"
                rationale_parts.append(f"Only {matched_count:,} patients (target: {enrollment_target})")
                flags.append("Patient volume may be tight for enrollment")
                missing.append(f"Need {enrollment_target}, have {matched_count}")

            comparisons.append({
                "requirement": f"{indication.title()} Patients",
                "protocol_needs": f"{enrollment_target} needed" if enrollment_target else "Required",
                "site_has": f"{matched_count:,} available",
                "status": status
            })
        else:
            score = 50
            rationale_parts.append(f"No documented patients for {indication or 'required indication'}")
            flags.append("Cannot verify patient population for indication")
            missing.append(f"No {indication} patients documented")
            comparisons.append({
                "requirement": f"{indication.title() if indication else 'Target'} Patients",
                "protocol_needs": f"{enrollment_target} needed" if enrollment_target else "Required",
                "site_has": "Not documented",
                "status": "❌"
            })

        # Check annual volume
        if annual_visits >= 30000:
            score = min(score + 5, 100)
            met.append(f"High volume site: {annual_visits:,} annual visits")

        comparisons.append({
            "requirement": "Annual Patient Volume",
            "protocol_needs": "High volume preferred",
            "site_has": f"{annual_visits:,} visits/year",
            "status": "✅" if annual_visits >= 10000 else "⚠️"
        })

        weighted = score * self.WEIGHTS["patient_indication"]

        return ScoreComponent(
            category="Patient Indication",
            score=score,
            weight=self.WEIGHTS["patient_indication"],
            weighted_score=round(weighted, 1),
            rationale="; ".join(rationale_parts),
            flags=flags,
            requirements_met=met,
            requirements_missing=missing
        ), comparisons

    def _score_equipment_facilities(
        self,
        protocol_requirements: Dict,
        site_profile: Dict
    ) -> tuple[ScoreComponent, List[Dict]]:
        """
        Score based on equipment and facility match
        """
        score = 100
        rationale_parts = []
        flags = []
        met = []
        missing = []
        comparisons = []

        required_equipment = protocol_requirements.get("equipment_required", [])
        facilities = site_profile.get("facilities_and_equipment", {})
        imaging = facilities.get("imaging", {})
        lab = facilities.get("laboratory", {})
        pharmacy = facilities.get("pharmacy", {})

        if not required_equipment:
            rationale_parts.append("No specific equipment requirements")
            return ScoreComponent(
                category="Equipment & Facilities",
                score=90,
                weight=self.WEIGHTS["equipment_facilities"],
                weighted_score=round(90 * self.WEIGHTS["equipment_facilities"], 1),
                rationale="No specific equipment requirements identified",
                flags=[],
                requirements_met=["Standard facilities available"],
                requirements_missing=[]
            ), []

        for equip in required_equipment:
            equip_name = equip.get("name", "") if isinstance(equip, dict) else str(equip)
            equip_lower = equip_name.lower()
            criticality = equip.get("criticality", "required") if isinstance(equip, dict) else "required"
            found = False
            site_has = "Not found"

            # Check imaging equipment
            for img_name, available in imaging.items():
                if available and (equip_lower in img_name.lower() or img_name.lower() in equip_lower):
                    found = True
                    site_has = f"✅ {img_name}"
                    break

            # Check lab capabilities
            if not found:
                lab_caps = lab.get("capabilities", [])
                for cap in lab_caps:
                    if equip_lower in cap.lower():
                        found = True
                        site_has = f"✅ {cap}"
                        break

            # Check pharmacy/storage
            if not found and ("storage" in equip_lower or "freezer" in equip_lower or "-80" in equip_lower):
                storage = pharmacy.get("investigational_drug_storage", {})
                if storage.get("freezer_minus80C") or storage.get("freezer_-80C"):
                    found = True
                    site_has = "✅ -80°C Freezer"

            # Update score
            if found:
                met.append(equip_name)
            else:
                if criticality == "critical":
                    score -= 20
                    flags.append(f"CRITICAL: Missing {equip_name}")
                else:
                    score -= 10
                missing.append(equip_name)
                site_has = "❌ Not available"

            comparisons.append({
                "requirement": equip_name,
                "protocol_needs": f"Required ({criticality})" if isinstance(equip, dict) else "Required",
                "site_has": site_has,
                "status": "✅" if found else "❌"
            })

        score = max(score, 20)  # Floor

        if missing:
            rationale_parts.append(f"Missing: {', '.join(missing)}")
        else:
            rationale_parts.append("All required equipment available")

        weighted = score * self.WEIGHTS["equipment_facilities"]

        return ScoreComponent(
            category="Equipment & Facilities",
            score=score,
            weight=self.WEIGHTS["equipment_facilities"],
            weighted_score=round(weighted, 1),
            rationale="; ".join(rationale_parts),
            flags=flags,
            requirements_met=met,
            requirements_missing=missing
        ), comparisons

    def _score_staffing(
        self,
        protocol_requirements: Dict,
        site_profile: Dict
    ) -> tuple[ScoreComponent, List[Dict]]:
        """
        Score based on staffing match
        """
        score = 70
        rationale_parts = []
        flags = []
        met = []
        missing = []
        comparisons = []

        required_staff = protocol_requirements.get("staff_requirements", [])
        staff = site_profile.get("staff_and_experience", {})

        pi = staff.get("principal_investigator", {})
        pi_name = pi.get("name", "Unknown")
        pi_specialty = pi.get("specialty", "").lower()
        pi_years = pi.get("years_experience", 0)
        pi_trials = pi.get("trials_conducted", 0)

        coordinators = staff.get("study_coordinators", {})
        coord_count = coordinators.get("count", 0)

        # Check PI requirements
        required_pi_spec = None
        for req in required_staff:
            if isinstance(req, dict) and req.get("role", "").upper() == "PI":
                required_pi_spec = req.get("specialization", "").lower()
                break

        # PI scoring
        if pi_years >= 15:
            score += 15
            met.append(f"Experienced PI: {pi_name} ({pi_years} years)")
            rationale_parts.append(f"Highly experienced PI")
        elif pi_years >= 10:
            score += 10
            met.append(f"PI: {pi_name} ({pi_years} years)")
        elif pi_years >= 5:
            score += 5
        else:
            flags.append("PI has limited experience")
            missing.append("Experienced PI (10+ years preferred)")

        # PI specialty match
        if required_pi_spec:
            if required_pi_spec in pi_specialty:
                score += 5
                met.append(f"PI specialty matches: {pi_specialty}")
            else:
                flags.append(f"PI specialty ({pi_specialty}) may not match requirement ({required_pi_spec})")

        comparisons.append({
            "requirement": "Principal Investigator",
            "protocol_needs": required_pi_spec.title() if required_pi_spec else "Required",
            "site_has": f"✅ {pi_name} ({pi_specialty.title()}, {pi_years}y exp)",
            "status": "✅" if pi_years >= 5 else "⚠️"
        })

        # Coordinator scoring
        if coord_count >= 4:
            score += 10
            met.append(f"{coord_count} study coordinators")
            comparisons.append({
                "requirement": "Study Coordinators",
                "protocol_needs": "Adequate staffing",
                "site_has": f"✅ {coord_count} coordinators",
                "status": "✅"
            })
        elif coord_count >= 2:
            score += 5
            comparisons.append({
                "requirement": "Study Coordinators",
                "protocol_needs": "Adequate staffing",
                "site_has": f"⚠️ {coord_count} coordinators",
                "status": "⚠️"
            })
            flags.append("CRC bandwidth may be limited")
        else:
            flags.append("Insufficient coordinator staffing")
            missing.append("Additional study coordinators needed")
            comparisons.append({
                "requirement": "Study Coordinators",
                "protocol_needs": "Adequate staffing",
                "site_has": f"❌ Only {coord_count} coordinator(s)",
                "status": "❌"
            })

        score = min(max(score, 30), 100)
        weighted = score * self.WEIGHTS["staffing_certifications"]

        return ScoreComponent(
            category="Staffing & Certifications",
            score=score,
            weight=self.WEIGHTS["staffing_certifications"],
            weighted_score=round(weighted, 1),
            rationale="; ".join(rationale_parts) if rationale_parts else "Standard staffing assessment",
            flags=flags,
            requirements_met=met,
            requirements_missing=missing
        ), comparisons

    def _score_emr_workflows(
        self,
        protocol_requirements: Dict,
        site_profile: Dict
    ) -> ScoreComponent:
        """
        Score based on EMR and operational workflows
        """
        score = 70
        rationale_parts = []
        flags = []
        met = []
        missing = []

        operational = site_profile.get("operational_capabilities", {})
        compliance = site_profile.get("compliance_and_training", {})

        # Check key operational metrics
        startup_time = operational.get("average_startup_time_days", 90)
        retention_rate = operational.get("retention_rate", "")
        irb_time = compliance.get("average_irb_approval_time_days", 60)

        # Startup time scoring
        if startup_time <= 45:
            score += 10
            met.append(f"Fast startup: {startup_time} days")
            rationale_parts.append("Quick study startup capability")
        elif startup_time <= 60:
            score += 5
            met.append(f"Standard startup: {startup_time} days")
        else:
            flags.append(f"Slow startup time: {startup_time} days")

        # Retention rate
        if "90" in str(retention_rate) or "95" in str(retention_rate):
            score += 10
            met.append(f"Excellent retention: {retention_rate}")

        # IRB timing
        if irb_time <= 30:
            score += 5
            met.append(f"Fast IRB: {irb_time} days")
        elif irb_time > 45:
            flags.append(f"IRB approval may be slow: {irb_time} days")

        # GCP training
        gcp = compliance.get("gcp_training", "")
        if "current" in str(gcp).lower():
            score += 5
            met.append("GCP certified")

        score = min(score, 100)
        weighted = score * self.WEIGHTS["emr_workflows"]

        return ScoreComponent(
            category="EMR & Workflows",
            score=score,
            weight=self.WEIGHTS["emr_workflows"],
            weighted_score=round(weighted, 1),
            rationale="; ".join(rationale_parts) if rationale_parts else "Standard operational capabilities",
            flags=flags,
            requirements_met=met,
            requirements_missing=missing
        )

    async def _generate_ai_assessment(
        self,
        protocol_requirements: Dict,
        site_profile: Dict,
        rule_based_result: Dict
    ) -> Dict:
        """
        Use GPT-4o to generate a narrative assessment of the site-protocol fit.
        Runs after rule-based scoring to add insights and recommendations.
        """
        from app.services.openai_client import UnifiedOpenAIClient

        try:
            client = UnifiedOpenAIClient()

            # Extract key protocol requirements
            phase = protocol_requirements.get('study_identification', {}).get('phase', 'Unknown')
            indication = protocol_requirements.get('patient_population', {}).get('primary_indication', 'Unknown')
            enrollment_target = protocol_requirements.get('study_timeline', {}).get('enrollment_target', 'Unknown')
            duration_weeks = protocol_requirements.get('study_timeline', {}).get('total_duration_weeks', 'Unknown')

            # Extract equipment (handle both dict and list formats)
            equipment_raw = protocol_requirements.get('equipment_required', [])
            if isinstance(equipment_raw, list):
                equipment = [e.get('name', e) if isinstance(e, dict) else str(e) for e in equipment_raw]
            else:
                equipment = []

            # Extract site capabilities
            historical_studies = site_profile.get('historical_performance', {}).get('studies_completed_last_5_years', 'Unknown')
            patient_population = site_profile.get('population_capabilities', {}).get('patient_population', {}).get('available_patients_by_condition', {})

            # Extract PI info
            pi_info = site_profile.get('staff_and_experience', {}).get('principal_investigator', {})
            pi_name = pi_info.get('name', 'Unknown')
            pi_specialty = pi_info.get('specialty', 'Unknown')
            pi_years = pi_info.get('years_experience', 'Unknown')

            coordinator_count = site_profile.get('staff_and_experience', {}).get('study_coordinators', {}).get('count',
                               site_profile.get('staff_and_experience', {}).get('coordinators', {}).get('count', 'Unknown'))

            # Build context for AI
            prompt = f"""You are a clinical trial feasibility expert. Analyze this site-protocol match and provide insights.

PROTOCOL REQUIREMENTS:
- Phase: {phase}
- Indication: {indication}
- Enrollment Target: {enrollment_target}
- Duration: {duration_weeks} weeks
- Required Equipment: {', '.join(equipment) if equipment else 'Not specified'}

SITE CAPABILITIES:
- Historical Studies: {historical_studies} completed in last 5 years
- Patient Population: {patient_population}
- PI: {pi_name} ({pi_specialty}, {pi_years} years experience)
- Study Coordinators: {coordinator_count}

RULE-BASED SCORE: {rule_based_result.get('total_score', 0)}/100 ({rule_based_result.get('grade', 'Unknown')})

FLAGS IDENTIFIED:
{chr(10).join(['- ' + f for f in rule_based_result.get('flags', [])]) or '- None'}

GAPS IDENTIFIED:
{chr(10).join(['- ' + g for g in rule_based_result.get('gaps', [])]) or '- None'}

Based on this analysis, provide:
1. EXECUTIVE SUMMARY (2-3 sentences on overall fit)
2. KEY STRENGTHS (3 bullet points)
3. POTENTIAL RISKS (2-3 bullet points)
4. RECOMMENDATIONS (2-3 actionable suggestions to improve feasibility)

Be specific and reference actual data points. Keep each section concise."""

            response = await asyncio.to_thread(
                client.create_completion,
                prompt=prompt,
                system_message="You are a clinical trial feasibility expert. Provide concise, data-driven insights.",
                max_tokens=800,
                temperature=0.3
            )

            # Response is a string
            return {
                "ai_generated": True,
                "assessment": response,
                "model": "gpt-4o"
            }

        except Exception as e:
            print(f"⚠️ AI assessment generation failed: {e}")
            # Don't fail the entire scoring - return empty assessment
            return {
                "ai_generated": False,
                "assessment": None,
                "error": str(e)
            }


# Convenience function
async def calculate_feasibility_score(
    protocol_requirements: Dict,
    site_profile: Dict,
    pi_name: Optional[str] = None,
    site_name: Optional[str] = None
) -> Dict:
    """Convenience function to calculate feasibility and return as dict"""
    scorer = FeasibilityScorer()
    result = await scorer.calculate_feasibility(
        protocol_requirements, site_profile, pi_name, site_name
    )
    return result.to_dict()
