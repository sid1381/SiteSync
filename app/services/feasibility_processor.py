from typing import Dict, List, Any, Optional
from sqlalchemy.orm import Session
from app import models
from app.services.document_processor import ProtocolDocumentProcessor
from app.services.scoring import load_site_truth_map
from app.services.llm_provider import generate

class FeasibilityProcessor:
    """Main service for processing protocols and generating auto-filled surveys"""

    def __init__(self):
        self.doc_processor = ProtocolDocumentProcessor()

        # UAB form question mapping
        self.uab_questions = {
            "protocol_basics": [
                "protocol_title", "protocol_number", "phase", "sponsor",
                "drug_administration", "population_age", "expected_enrollment"
            ],
            "population_assessment": [
                "participant_health_status", "access_to_population",
                "enrollment_realistic", "inclusion_exclusion_restrictive"
            ],
            "procedures": [
                "procedures_complex", "pk_samples", "pk_intensive",
                "special_equipment", "washout_period"
            ],
            "site_capabilities": [
                "workload_manageable", "adequate_staff", "extended_hours",
                "additional_specialists", "budget_covers"
            ],
            "manual_required": [
                "time_recruitment", "time_visits", "time_monitoring", "time_queries"
            ]
        }

    def process_protocol_for_feasibility(self,
                                       db: Session,
                                       protocol_pdf_bytes: bytes,
                                       site_id: int) -> Dict[str, Any]:
        """Main processing pipeline: PDF -> extracted data -> auto-filled form"""

        # 1. Extract protocol data
        protocol_data = self.doc_processor.extract_protocol_data(protocol_pdf_bytes)

        if "error" in protocol_data:
            return {"error": protocol_data["error"]}

        # 2. Get site profile
        site = db.get(models.Site, site_id)
        if not site:
            return {"error": "Site not found"}

        # 3. Create protocol record in database
        protocol_record = self._create_protocol_record(db, protocol_data)

        # 4. Generate auto-filled responses
        filled_form = self._generate_feasibility_responses(
            protocol_data, site, db, site_id
        )

        # 5. Calculate completion stats
        stats = self._calculate_completion_stats(filled_form)

        return {
            "protocol": {
                "id": protocol_record.id,
                "data": protocol_data
            },
            "filled_form": filled_form,
            "completion_stats": stats,
            "site_info": {
                "id": site_id,
                "name": site.name
            }
        }

    def _create_protocol_record(self, db: Session, protocol_data: Dict) -> models.Protocol:
        """Create Protocol record from extracted data"""

        protocol = models.Protocol(
            name=protocol_data.get("protocol_title", "Unknown Protocol"),
            sponsor=protocol_data.get("sponsor", ""),
            disease=protocol_data.get("indication", ""),
            phase=protocol_data.get("phase", ""),
            nct_id=protocol_data.get("protocol_number", ""),
            notes=f"Auto-extracted with {protocol_data.get('extraction_confidence', 'unknown')} confidence"
        )

        db.add(protocol)
        db.commit()
        db.refresh(protocol)

        # Create requirements from extracted data
        self._create_protocol_requirements(db, protocol.id, protocol_data)

        return protocol

    def _create_protocol_requirements(self, db: Session, protocol_id: int, data: Dict):
        """Convert extracted data to ProtocolRequirement records"""

        requirements = []

        # Equipment requirements
        if data.get("equipment_required"):
            for equipment in data["equipment_required"]:
                req = models.ProtocolRequirement(
                    protocol_id=protocol_id,
                    key="equipment",
                    op="in",
                    value=equipment,
                    weight=5,
                    type="objective",
                    source_question="Is special equipment required for the study?"
                )
                requirements.append(req)

        # Age requirements
        if data.get("population_age"):
            req = models.ProtocolRequirement(
                protocol_id=protocol_id,
                key="patient_age_range",
                op="==",
                value=data["population_age"],
                weight=3,
                type="objective",
                source_question="What is the population age?"
            )
            requirements.append(req)

        # Enrollment expectations
        if data.get("expected_enrollment"):
            try:
                enrollment = int(data["expected_enrollment"])
                req = models.ProtocolRequirement(
                    protocol_id=protocol_id,
                    key="annual_eligible_patients",
                    op=">=",
                    value=str(int(enrollment * 1.5)),  # 1.5x buffer
                    weight=4,
                    type="objective",
                    source_question="Do we have access to the participant population?"
                )
                requirements.append(req)
            except (ValueError, TypeError):
                pass

        db.add_all(requirements)
        db.commit()

    def _generate_feasibility_responses(self,
                                      protocol_data: Dict,
                                      site: models.Site,
                                      db: Session,
                                      site_id: int) -> Dict[str, Any]:
        """Generate auto-filled responses for feasibility questions"""

        responses = {}
        site_truth_map = load_site_truth_map(db, site_id)

        # Protocol basics (high confidence, auto-lock)
        basic_fields = {
            "protocol_title": protocol_data.get("protocol_title", ""),
            "protocol_number": protocol_data.get("protocol_number", ""),
            "phase": protocol_data.get("phase", ""),
            "sponsor": protocol_data.get("sponsor", ""),
            "drug_administration": protocol_data.get("drug_administration", ""),
            "population_age": protocol_data.get("population_age", ""),
            "expected_enrollment": protocol_data.get("expected_enrollment", "")
        }

        for key, value in basic_fields.items():
            if value and value != "unclear":
                responses[key] = {
                    "answer": value,
                    "confidence": "high",
                    "locked": True,
                    "evidence": "Extracted from protocol document",
                    "source": "protocol_extraction"
                }

        # Site capability assessments
        responses.update(self._assess_site_capabilities(protocol_data, site_truth_map, db, site_id))

        # AI-powered assessments
        responses.update(self._ai_powered_assessments(protocol_data))

        # Manual questions (provide helpful prompts)
        responses.update(self._manual_question_prompts(protocol_data))

        return responses

    def _assess_site_capabilities(self, protocol_data: Dict, site_truth_map: Dict,
                                db: Session, site_id: int) -> Dict[str, Any]:
        """Assess site capabilities using rule-based matching"""

        responses = {}

        # Access to population - therapeutic area matching
        indication = protocol_data.get("indication", "").lower()
        site_indications = site_truth_map.get("indications", "").lower()

        if indication and site_indications:
            has_match = any(word in site_indications for word in indication.split())
            responses["access_to_population"] = {
                "answer": "Yes" if has_match else "No",
                "confidence": "medium",
                "locked": False,
                "evidence": f"Site specializes in: {site_truth_map.get('indications', 'N/A')}",
                "rationale": f"Protocol indication '{indication}' {'matches' if has_match else 'does not clearly match'} site experience"
            }

        # Equipment availability
        required_equipment = protocol_data.get("equipment_required", [])
        if required_equipment and isinstance(required_equipment, list):
            site_equipment = db.query(models.SiteEquipment).filter(
                models.SiteEquipment.site_id == site_id
            ).all()

            site_equipment_names = [eq.label.lower() for eq in site_equipment]
            missing_equipment = []

            for req_eq in required_equipment:
                if not any(req_eq.lower() in site_eq for site_eq in site_equipment_names):
                    missing_equipment.append(req_eq)

            if missing_equipment:
                responses["special_equipment"] = {
                    "answer": f"No - Missing: {', '.join(missing_equipment)}",
                    "confidence": "high",
                    "locked": True,
                    "evidence": f"Site equipment inventory checked",
                    "rationale": f"Required equipment not found: {', '.join(missing_equipment)}"
                }
            else:
                responses["special_equipment"] = {
                    "answer": "Yes",
                    "confidence": "high",
                    "locked": True,
                    "evidence": "All required equipment available",
                    "rationale": "Site equipment inventory confirms availability"
                }

        # Experience with sponsor
        sponsor = protocol_data.get("sponsor", "")
        if sponsor:
            site_history = db.query(models.SiteHistory).filter(
                models.SiteHistory.site_id == site_id
            ).all()

            has_sponsor_experience = any(
                sponsor.lower() in (h.indication or "").lower()
                for h in site_history
            )

            responses["experience_with_sponsor"] = {
                "answer": "Yes" if has_sponsor_experience else "No",
                "confidence": "medium",
                "locked": False,
                "evidence": f"Based on site history review",
                "rationale": f"{'Found' if has_sponsor_experience else 'No'} previous experience with this sponsor"
            }

        return responses

    def _ai_powered_assessments(self, protocol_data: Dict) -> Dict[str, Any]:
        """Use AI for questions requiring interpretation"""

        responses = {}

        # Assess if inclusion/exclusion criteria are restrictive
        inclusion = protocol_data.get("inclusion_criteria", [])
        exclusion = protocol_data.get("exclusion_criteria", [])

        if inclusion or exclusion:
            prompt = f"""
            Assess if these eligibility criteria are restrictive for patient recruitment:

            INCLUSION: {inclusion}
            EXCLUSION: {exclusion}

            Answer "Yes" if restrictive, "No" if reasonable. Provide brief rationale.
            """

            try:
                messages = [
                    {"role": "system", "content": "You are a clinical research expert."},
                    {"role": "user", "content": prompt}
                ]

                ai_response = generate(messages, temperature=0.3, max_tokens=1500)  # High limit for gpt-5-mini reasoning
                is_restrictive = "yes" in ai_response.lower()

                responses["inclusion_exclusion_restrictive"] = {
                    "answer": "Yes" if is_restrictive else "No",
                    "confidence": "medium",
                    "locked": False,
                    "evidence": "AI analysis of eligibility criteria",
                    "rationale": ai_response[:200]
                }

            except Exception:
                responses["inclusion_exclusion_restrictive"] = {
                    "answer": "",
                    "confidence": "low",
                    "locked": False,
                    "evidence": "Unable to assess automatically",
                    "rationale": "Requires manual review"
                }

        return responses

    def _manual_question_prompts(self, protocol_data: Dict) -> Dict[str, Any]:
        """Generate helpful prompts for manual-only questions"""

        return {
            "time_recruitment": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site coordinator input required",
                "prompt": f"Estimate hours for {protocol_data.get('expected_enrollment', 'X')} patients",
                "helper_text": "Consider your typical recruitment rate and methods"
            },
            "time_visits": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site coordinator input required",
                "prompt": f"Visit schedule: {protocol_data.get('visit_frequency', 'See protocol')}",
                "helper_text": "Estimate total hours for all study visits"
            },
            "workload_manageable": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site assessment required",
                "prompt": "Consider current study load and staff capacity",
                "helper_text": "Review current active studies and available staff time"
            },
            "time_monitoring": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site coordinator input required",
                "prompt": "Estimate monitoring visit coordination time",
                "helper_text": "Consider CRA visit frequency and preparation time"
            },
            "time_queries": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site coordinator input required",
                "prompt": "Estimate query resolution time based on protocol complexity",
                "helper_text": "Consider data collection complexity and typical query volume"
            }
        }

    def _calculate_completion_stats(self, filled_form: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate completion statistics for the form"""

        total_questions = len(self.uab_questions["protocol_basics"]) + \
                         len(self.uab_questions["population_assessment"]) + \
                         len(self.uab_questions["procedures"]) + \
                         len(self.uab_questions["site_capabilities"]) + \
                         len(self.uab_questions["manual_required"])

        auto_filled = len([q for q in filled_form.values() if q.get("answer")])
        high_confidence = len([q for q in filled_form.values() if q.get("confidence") == "high"])
        locked_answers = len([q for q in filled_form.values() if q.get("locked")])
        manual_required = len([q for q in filled_form.values() if q.get("confidence") == "manual"])

        time_saved = min(45, auto_filled * 2.5)  # Conservative estimate

        return {
            "total_questions": total_questions,
            "auto_filled": auto_filled,
            "high_confidence": high_confidence,
            "locked_answers": locked_answers,
            "manual_required": manual_required,
            "completion_percentage": round((auto_filled / max(total_questions, 1)) * 100),
            "estimated_time_saved_minutes": round(time_saved),
            "review_needed": [
                key for key, data in filled_form.items()
                if data.get("confidence") in ["medium", "low"]
            ]
        }