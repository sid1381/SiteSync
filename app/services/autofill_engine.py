from typing import Dict, List, Any
from sqlalchemy.orm import Session
import json
from app import models
from app.services.universal_survey_parser import UniversalSurveyParser, ExtractedQuestion
from app.services.ai_question_mapper import AIQuestionMapper, AIQuestionMapping

class AutofillEngine:
    def __init__(self):
        self.survey_parser = UniversalSurveyParser()
        self.question_mapper = AIQuestionMapper()

    async def process_survey_document_universal(
        self,
        file_content: bytes,
        filename: str,
        site_profile: Dict
    ) -> Dict[str, Any]:
        """
        Universal AI-powered survey processing that works with ANY survey format
        """
        try:
            # 1. Extract questions from document using AI
            extracted_questions = await self.survey_parser.extract_questions_from_document(
                file_content, filename
            )

            # 2. Convert to compatible format
            questions_list = [
                {
                    'id': q.id,
                    'text': q.text,
                    'type': q.type.value,
                    'is_objective': q.is_objective,
                    'confidence': q.confidence_score,
                    'context': q.context
                }
                for q in extracted_questions
            ]

            # 3. Map questions to site profile data
            mappings = self.question_mapper.map_questions_to_site_profile(
                questions_list, site_profile
            )

            # 4. Generate autofilled responses
            responses = self.question_mapper.generate_autofill_responses(
                mappings, questions_list, site_profile
            )

            # AI mapping should be comprehensive - no need for keyword fallback
            autofilled_count = sum(1 for r in responses if r.get('source') != 'manual_required' and r.get('response'))
            print(f"AI mapping completed: {autofilled_count}/{len(questions_list)} responses generated")

            # 5. Calculate statistics
            categorization = self.survey_parser.get_categorization_summary(extracted_questions)
            mapping_stats = self.question_mapper.get_mapping_statistics(mappings)

            # 6. Generate completion percentage and score
            total_questions = len(questions_list)
            autofilled_count = sum(1 for r in responses if r.get('source') != 'manual_required' and r.get('response'))
            completion_percentage = (autofilled_count / total_questions * 100) if total_questions > 0 else 0

            # Use comprehensive feasibility scoring
            from app.services.comprehensive_feasibility_scorer import ComprehensiveFeasibilityScorer
            scorer = ComprehensiveFeasibilityScorer()
            feasibility_result = scorer.calculate_feasibility_score(site_profile)
            feasibility_score = feasibility_result.score

            return {
                "success": True,
                "questions_extracted": total_questions,
                "questions": questions_list,
                "responses": responses,
                "autofilled_count": autofilled_count,
                "completion_percentage": completion_percentage,
                "feasibility_score": feasibility_score,
                "categorization": categorization,
                "mapping_statistics": mapping_stats,
                "flags": self._generate_universal_flags(responses, site_profile),
                "next_step": "Upload protocol document to enhance autofill accuracy" if autofilled_count < total_questions else "Review and submit survey"
            }

        except Exception as e:
            print(f"Universal survey processing error: {e}")
            # Robust fallback to simple processing with site profile data
            return await self._fallback_processing(file_content, filename, site_profile)

    async def process_extracted_questions(
        self,
        extracted_questions: List[Dict],
        site_profile: Dict,
        protocol_requirements: Dict = None
    ) -> Dict[str, Any]:
        """
        Process already-extracted questions and generate autofilled responses
        This is for when questions are already extracted and we just need mapping

        Args:
            extracted_questions: List of extracted question objects
            site_profile: Site capabilities and profile data
            protocol_requirements: Optional protocol requirements extracted from protocol PDF
        """
        try:
            if not extracted_questions:
                return {
                    "success": False,
                    "error": "No questions provided",
                    "completion_percentage": 0
                }

            # Add protocol requirements to site_profile for AI mapper
            if protocol_requirements:
                site_profile_with_protocol = {**site_profile, "protocol_requirements": protocol_requirements}
            else:
                site_profile_with_protocol = site_profile

            # Map questions to site profile data using enhanced mapper
            mappings = self.question_mapper.map_questions_to_site_profile(
                extracted_questions, site_profile_with_protocol
            )

            # Generate autofilled responses with enhanced mapping (including protocol data)
            responses = self.question_mapper.generate_autofill_responses(
                mappings, extracted_questions, site_profile_with_protocol
            )

            # Calculate completion statistics
            total_questions = len(extracted_questions)
            autofilled_count = sum(1 for r in responses if r.get('source') != 'manual_required' and r.get('response'))
            completion_percentage = (autofilled_count / total_questions * 100) if total_questions > 0 else 0

            # Calculate feasibility score using comprehensive scorer
            from app.services.comprehensive_feasibility_scorer import ComprehensiveFeasibilityScorer
            scorer = ComprehensiveFeasibilityScorer()
            feasibility_result = scorer.calculate_feasibility_score(site_profile)
            feasibility_score = feasibility_result.score

            return {
                "success": True,
                "questions_extracted": total_questions,
                "questions": extracted_questions,
                "responses": responses,
                "autofilled_count": autofilled_count,
                "completion_percentage": completion_percentage,
                "feasibility_score": feasibility_score,
                "flags": ["Enhanced mapping applied to extracted questions"],
                "next_step": "Review and submit survey"
            }

        except Exception as e:
            print(f"Error processing extracted questions: {e}")
            return {
                "success": False,
                "error": str(e),
                "completion_percentage": 0
            }

    async def _fallback_processing(self, file_content: bytes, filename: str, site_profile: Dict) -> Dict[str, Any]:
        """
        Fallback processing when AI services fail - use site profile data to generate meaningful responses
        """
        try:
            # Generate predefined questions based on common survey patterns
            fallback_questions = self._generate_fallback_questions()

            # Map questions to site profile data using deterministic logic
            responses = self._generate_fallback_responses(fallback_questions, site_profile)

            # Calculate completion and scores
            total_questions = len(fallback_questions)
            autofilled_count = sum(1 for r in responses if r.get('response') and r.get('source') != 'manual_required')
            completion_percentage = (autofilled_count / total_questions * 100) if total_questions > 0 else 0

            return {
                "success": True,
                "questions_extracted": total_questions,
                "questions": fallback_questions,
                "responses": responses,
                "autofilled_count": autofilled_count,
                "completion_percentage": completion_percentage,
                "feasibility_score": 75,  # Conservative score for fallback
                "categorization": {
                    "objective_questions": sum(1 for q in fallback_questions if q.get('is_objective')),
                    "subjective_questions": sum(1 for q in fallback_questions if not q.get('is_objective'))
                },
                "mapping_statistics": {"fallback_mode": True, "mapped_questions": autofilled_count},
                "flags": ["Processed in fallback mode - limited AI features"],
                "next_step": "Upload protocol document to enhance autofill accuracy"
            }

        except Exception as e:
            print(f"Fallback processing also failed: {e}")
            return {
                "success": False,
                "error": f"All processing methods failed: {str(e)}",
                "questions_extracted": 0,
                "autofilled_count": 0,
                "completion_percentage": 0
            }

    def _generate_fallback_questions(self) -> List[Dict]:
        """Generate common survey questions when AI extraction fails"""
        return [
            {
                "id": "q_1",
                "text": "How many research coordinators are available?",
                "type": "number",
                "is_objective": True,
                "confidence": 0.9,
                "context": "Staff requirements"
            },
            {
                "id": "q_2",
                "text": "Do you have experience with Phase II clinical trials?",
                "type": "boolean",
                "is_objective": True,
                "confidence": 0.9,
                "context": "Experience assessment"
            },
            {
                "id": "q_3",
                "text": "What is your annual patient volume?",
                "type": "number",
                "is_objective": True,
                "confidence": 0.9,
                "context": "Patient population"
            },
            {
                "id": "q_4",
                "text": "Do you have specialized laboratory capabilities?",
                "type": "boolean",
                "is_objective": True,
                "confidence": 0.9,
                "context": "Laboratory capabilities"
            },
            {
                "id": "q_5",
                "text": "Is specialized imaging equipment available?",
                "type": "boolean",
                "is_objective": True,
                "confidence": 0.9,
                "context": "Equipment availability"
            },
            {
                "id": "q_6",
                "text": "What challenges do you anticipate with patient recruitment?",
                "type": "text",
                "is_objective": False,
                "confidence": 0.7,
                "context": "Subjective assessment"
            }
        ]

    def _generate_fallback_responses(self, questions: List[Dict], site_profile: Dict) -> List[Dict]:
        """Generate responses using site profile data without AI"""
        responses = []

        for question in questions:
            q_text = question.get('text', '').lower()
            response = dict(question)  # Copy question data

            # Coordinator questions
            if 'coordinator' in q_text:
                staff_resources = site_profile.get('staff_resources') or {}
                coordinators_fte = staff_resources.get('coordinators_fte') or 0
                if coordinators_fte and coordinators_fte > 0:
                    response.update({
                        'response': str(coordinators_fte),
                        'source': 'site_profile',
                        'confidence': 0.9,
                        'manually_edited': False
                    })
                else:
                    response.update({
                        'response': '',
                        'source': 'manual_required',
                        'confidence': 0.0,
                        'manually_edited': False
                    })

            # Experience questions
            elif 'experience' in q_text and 'phase' in q_text:
                experience = site_profile.get('experience_history', {})
                sponsors = experience.get('previous_sponsors', [])
                if len(sponsors) >= 2:
                    response.update({
                        'response': 'Yes',
                        'source': 'site_profile',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                else:
                    response.update({
                        'response': 'Limited experience',
                        'source': 'site_profile',
                        'confidence': 0.6,
                        'manually_edited': False
                    })

            # Patient volume questions
            elif 'patient volume' in q_text or 'annual' in q_text:
                population_capabilities = site_profile.get('population_capabilities') or {}
                volume = population_capabilities.get('annual_patient_volume') or 0
                if volume and volume > 0:
                    response.update({
                        'response': str(volume),
                        'source': 'site_profile',
                        'confidence': 0.9,
                        'manually_edited': False
                    })
                else:
                    response.update({
                        'response': '',
                        'source': 'manual_required',
                        'confidence': 0.0,
                        'manually_edited': False
                    })

            # Laboratory questions
            elif 'laboratory' in q_text or 'lab' in q_text:
                lab_caps = site_profile.get('laboratory_capabilities', {})
                if isinstance(lab_caps, dict) and any(lab_caps.values()):
                    response.update({
                        'response': 'Yes',
                        'source': 'site_profile',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                else:
                    response.update({
                        'response': 'Basic capabilities',
                        'source': 'site_profile',
                        'confidence': 0.5,
                        'manually_edited': False
                    })

            # Equipment questions
            elif 'equipment' in q_text or 'imaging' in q_text:
                procedures_equipment = site_profile.get('procedures_equipment') or {}
                equipment = procedures_equipment.get('special_equipment') or []
                if equipment and len(equipment) > 2:
                    response.update({
                        'response': 'Yes',
                        'source': 'site_profile',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                else:
                    response.update({
                        'response': 'Standard equipment available',
                        'source': 'site_profile',
                        'confidence': 0.6,
                        'manually_edited': False
                    })

            # Subjective questions
            elif not question.get('is_objective', True):
                response.update({
                    'response': '',
                    'source': 'manual_required',
                    'confidence': 0.0,
                    'manually_edited': False
                })

            # Default for unmatched questions
            else:
                response.update({
                    'response': '',
                    'source': 'manual_required',
                    'confidence': 0.0,
                    'manually_edited': False
                })

            responses.append(response)

        return responses

    def _enhance_responses_with_fallback(self, responses: List[Dict], site_profile: Dict) -> List[Dict]:
        """
        Enhance responses using the same logic as fallback processing for questions that weren't autofilled
        """
        enhanced_responses = []

        for response in responses:
            # If already autofilled with good confidence, keep it
            if response.get('source') != 'manual_required' and response.get('response') and response.get('confidence', 0) > 0.5:
                enhanced_responses.append(response)
                continue

            # Apply fallback mapping logic
            q_text = response.get('text', '').lower()
            enhanced_response = dict(response)  # Copy existing response

            # Coordinator questions
            if 'coordinator' in q_text:
                staff_resources = site_profile.get('staff_resources') or {}
                coordinators_fte = staff_resources.get('coordinators_fte') or 0
                if coordinators_fte and coordinators_fte > 0:
                    enhanced_response.update({
                        'response': str(coordinators_fte),
                        'source': 'site_profile_fallback',
                        'confidence': 0.8,
                        'manually_edited': False
                    })

            # Experience questions
            elif ('experience' in q_text and ('phase' in q_text or 'trial' in q_text)) or 'previous' in q_text:
                experience = site_profile.get('experience_history', {})
                sponsors = experience.get('previous_sponsors', [])
                if len(sponsors) >= 2:
                    enhanced_response.update({
                        'response': 'Yes - extensive experience',
                        'source': 'site_profile_fallback',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                elif len(sponsors) >= 1:
                    enhanced_response.update({
                        'response': 'Some experience',
                        'source': 'site_profile_fallback',
                        'confidence': 0.6,
                        'manually_edited': False
                    })

            # Patient volume questions
            elif any(word in q_text for word in ['patient', 'volume', 'annual', 'enrollment']):
                population_capabilities = site_profile.get('population_capabilities') or {}
                volume = population_capabilities.get('annual_patient_volume') or 0
                if volume and volume > 0:
                    enhanced_response.update({
                        'response': str(volume),
                        'source': 'site_profile_fallback',
                        'confidence': 0.8,
                        'manually_edited': False
                    })

            # Laboratory/PK questions
            elif any(word in q_text for word in ['laboratory', 'lab', 'pk', 'pharmacokinetic', 'blood', 'sample']):
                lab_caps = site_profile.get('laboratory_capabilities', {})
                if isinstance(lab_caps, dict) and lab_caps.get('pk_sampling'):
                    enhanced_response.update({
                        'response': 'Yes',
                        'source': 'site_profile_fallback',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                elif isinstance(lab_caps, dict) and any(lab_caps.values()):
                    enhanced_response.update({
                        'response': 'Basic capabilities available',
                        'source': 'site_profile_fallback',
                        'confidence': 0.6,
                        'manually_edited': False
                    })

            # Equipment questions
            elif any(word in q_text for word in ['equipment', 'imaging', 'mri', 'ct', 'scanner']):
                procedures_equipment = site_profile.get('procedures_equipment') or {}
                equipment = procedures_equipment.get('special_equipment') or []
                if equipment and len(equipment) > 2:
                    enhanced_response.update({
                        'response': 'Yes - full equipment available',
                        'source': 'site_profile_fallback',
                        'confidence': 0.8,
                        'manually_edited': False
                    })
                elif equipment:
                    enhanced_response.update({
                        'response': 'Standard equipment available',
                        'source': 'site_profile_fallback',
                        'confidence': 0.6,
                        'manually_edited': False
                    })

            # Therapeutic area questions
            elif any(word in q_text for word in ['therapeutic', 'disease', 'indication', 'oncology', 'cardiology']):
                experience_history = site_profile.get('experience_history') or {}
                areas = experience_history.get('therapeutic_areas') or []
                if areas and len(areas) > 2:
                    enhanced_response.update({
                        'response': f'Yes - experience in {", ".join(areas[:3])}',
                        'source': 'site_profile_fallback',
                        'confidence': 0.7,
                        'manually_edited': False
                    })

            enhanced_responses.append(enhanced_response)

        return enhanced_responses

    def _calculate_universal_feasibility_score(self, responses: List[Dict], site_profile: Dict) -> int:
        """
        Calculate feasibility score based on AI-generated responses
        """
        total_score = 0
        weight_sum = 0

        for response in responses:
            if not response.get('is_objective'):
                continue

            confidence = response.get('confidence', 0)
            response_value = response.get('response', '')

            # Score based on response quality and confidence
            if response_value and response_value not in ['Information not available', 'None available']:
                if confidence >= 0.8:
                    score = 95
                elif confidence >= 0.6:
                    score = 85
                else:
                    score = 75

                # Boost for positive responses
                if any(positive in str(response_value).lower() for positive in ['yes', 'available', 'certified', 'experienced']):
                    score += 5

                total_score += score * confidence
                weight_sum += confidence

        base_score = int(total_score / weight_sum) if weight_sum > 0 else 70

        # Adjust based on site profile completeness
        metadata = site_profile.get('metadata') or {}
        profile_completeness = (metadata.get('profile_completion_percentage') or 0) / 100
        adjusted_score = base_score * (0.7 + 0.3 * profile_completeness)

        return min(100, max(40, int(adjusted_score)))

    def _generate_universal_flags(self, responses: List[Dict], site_profile: Dict) -> List[str]:
        """
        Generate warning flags based on AI analysis
        """
        flags = []

        # Check for low confidence responses
        low_confidence_count = sum(1 for r in responses if r.get('confidence', 0) < 0.6 and r.get('is_objective'))
        if low_confidence_count > 0:
            flags.append(f"{low_confidence_count} questions have low confidence scores")

        # Check for missing data
        no_data_count = sum(1 for r in responses if r.get('source') == 'no_data_available')
        if no_data_count > 0:
            flags.append(f"{no_data_count} questions lack site profile data")

        # Check for capability concerns
        negative_responses = sum(1 for r in responses if 'no' in str(r.get('response', '')).lower() or 'not available' in str(r.get('response', '')).lower())
        if negative_responses > len(responses) * 0.3:  # More than 30% negative
            flags.append("Multiple capability gaps identified")

        # Profile completion warning
        metadata = site_profile.get('metadata') or {}
        profile_completion = metadata.get('profile_completion_percentage') or 0
        if profile_completion < 80:
            flags.append(f"Site profile only {profile_completion}% complete - improve for better autofill")

        return flags

    async def autofill_survey_responses(
        self,
        survey_questions: List[Dict],
        protocol_requirements: Dict,
        site_capabilities: Dict
    ) -> Dict[str, Any]:
        """
        Enhanced autofill using Site Profile + Protocol Requirements to answer Survey Questions

        Workflow:
        1. Survey questions define WHAT needs to be answered
        2. Protocol requirements define WHAT the study needs
        3. Site capabilities define WHAT the site can provide
        4. AI maps site capabilities + protocol needs to answer survey questions
        """

        responses = []
        autofilled_count = 0
        objective_count = 0
        subjective_count = 0

        for question in survey_questions:
            if question["is_objective"]:
                objective_count += 1
                # Try to autofill from site capabilities + protocol requirements
                response = self._intelligent_autofill(
                    question,
                    site_capabilities,
                    protocol_requirements
                )
                if response["response"] is not None:
                    autofilled_count += 1
                responses.append({**question, **response})
            else:
                subjective_count += 1
                # Mark as requiring manual input
                responses.append({
                    **question,
                    "response": "",
                    "source": "manual_required",
                    "confidence": 0,
                    "manually_edited": False
                })

        completion_percentage = (autofilled_count / len(survey_questions)) * 100 if survey_questions else 0

        # Calculate feasibility score based on matches
        feasibility_score = self._calculate_feasibility_score(responses, protocol_requirements, site_capabilities)

        return {
            "responses": responses,
            "autofilled_count": autofilled_count,
            "completion_percentage": completion_percentage,
            "feasibility_score": feasibility_score,
            "score_breakdown": {"overall": {"score": feasibility_score}},
            "flags": self._generate_flags(responses, protocol_requirements, site_capabilities),
            "categorization": {
                "objective": objective_count,
                "subjective": subjective_count,
                "autofilled": autofilled_count
            }
        }

    def autofill_survey(
        self,
        db: Session,
        survey_id: int,
        site_id: int,
        protocol_data: Dict,
        questions: List[Dict]
    ) -> Dict[str, Any]:
        """Intelligently autofill survey questions"""

        # Load site profile
        site = db.get(models.Site, site_id)
        site_profile = self._build_site_profile(db, site)

        # Process each question
        responses = []
        autofilled_count = 0
        objective_count = 0
        subjective_count = 0

        for question in questions:
            if question["is_objective"]:
                objective_count += 1
                # Try to autofill from site profile or protocol
                response = self._autofill_objective_question(
                    question,
                    site_profile,
                    protocol_data
                )
                if response["response"] is not None:
                    autofilled_count += 1
                    question.update(response)
            else:
                subjective_count += 1
                # Mark as requiring manual input
                question["response"] = None
                question["source"] = "manual_required"
                question["confidence"] = 0

            responses.append(question)

            # Save to database
            db_response = models.SurveyResponse(
                survey_id=survey_id,
                question_id=question["id"],
                question_text=question["text"],
                question_type=question["type"],
                is_objective=question["is_objective"],
                response_value=str(question["response"]) if question["response"] else None,
                response_source=question.get("source"),
                confidence_score=question.get("confidence", 0)
            )
            db.add(db_response)

        db.commit()

        completion_percentage = (autofilled_count / len(questions)) * 100 if questions else 0

        return {
            "responses": responses,
            "autofilled_count": autofilled_count,
            "completion_percentage": completion_percentage,
            "categorization": {
                "objective": objective_count,
                "subjective": subjective_count,
                "autofilled": autofilled_count
            }
        }

    def _build_site_profile(self, db: Session, site: models.Site) -> Dict:
        """Build comprehensive site profile for matching"""
        profile = {
            "basic": {
                "name": site.name,
                "address": site.address,
                "emr": site.emr
            },
            "equipment": [],
            "staff": [],
            "experience": [],
            "capabilities": []
        }

        # Load equipment
        equipment = db.query(models.SiteEquipment).filter_by(site_id=site.id).all()
        for eq in equipment:
            profile["equipment"].append({
                "type": eq.label,
                "model": eq.model,
                "modality": eq.modality,
                "count": eq.count,
                "specs": eq.specs
            })

        # Load staff
        staff = db.query(models.SiteStaff).filter_by(site_id=site.id).all()
        for s in staff:
            profile["staff"].append({
                "role": s.role,
                "fte": s.fte,
                "certifications": s.certifications,
                "experience_years": s.experience_years
            })

        # Load experience
        history = db.query(models.SiteHistory).filter_by(site_id=site.id).all()
        for h in history:
            profile["experience"].append({
                "indication": h.indication,
                "phase": h.phase,
                "enrollment_rate": h.enrollment_rate,
                "startup_days": h.startup_days,
                "completed": h.completed,
                "n_trials": h.n_trials
            })

        # Load capabilities
        capabilities = db.query(models.SitePatientCapability).filter_by(site_id=site.id).all()
        for c in capabilities:
            profile["capabilities"].append({
                "indication": c.indication_label,
                "age_min": c.age_min_years,
                "age_max": c.age_max_years,
                "sex": c.sex,
                "annual_patients": c.annual_eligible_patients
            })

        return profile

    def _autofill_objective_question(
        self,
        question: Dict,
        site_profile: Dict,
        protocol_data: Dict
    ) -> Dict:
        """Attempt to autofill an objective question"""

        question_text = question["text"].lower()
        response = None
        source = None
        confidence = 0

        # Equipment-related questions
        if any(word in question_text for word in ['equipment', 'device', 'machine']):
            response, confidence = self._match_equipment(question_text, site_profile["equipment"])
            source = "site_profile"

        # Staff-related questions
        elif any(word in question_text for word in ['staff', 'personnel', 'coordinator', 'investigator']):
            response, confidence = self._match_staff(question_text, site_profile["staff"])
            source = "site_profile"

        # Experience-related questions
        elif any(word in question_text for word in ['experience', 'previous', 'completed', 'enrolled']):
            response, confidence = self._match_experience(
                question_text,
                site_profile["experience"],
                protocol_data.get("study_identification", {})
            )
            source = "site_profile"

        # Patient population questions
        elif any(word in question_text for word in ['patient', 'population', 'participants', 'subjects']):
            response, confidence = self._match_population(
                question_text,
                site_profile["capabilities"],
                protocol_data.get("population", {})
            )
            source = "site_profile"

        # EMR/Systems questions
        elif any(word in question_text for word in ['emr', 'electronic', 'system', 'software']):
            response = site_profile["basic"]["emr"]
            confidence = 1.0
            source = "site_profile"

        # Protocol-specific questions
        elif any(word in question_text for word in ['phase', 'indication', 'sponsor']):
            response, confidence = self._extract_from_protocol(question_text, protocol_data)
            source = "protocol_extraction"

        return {
            "response": response,
            "source": source,
            "confidence": confidence
        }

    def _match_equipment(self, question: str, equipment: List[Dict]) -> tuple:
        """Match equipment questions with site equipment"""
        for eq in equipment:
            eq_terms = [eq["type"].lower(), eq.get("model", "").lower()]
            if any(term in question for term in eq_terms if term):
                # Format response based on question type
                if 'how many' in question:
                    return (eq.get("count", 1), 0.9)  # Count of matching equipment
                elif 'do you have' in question or 'available' in question:
                    return ("Yes", 1.0)
                else:
                    return (f"{eq['type']} - {eq.get('model', 'Available')}", 0.9)

        # No match found
        if 'do you have' in question:
            return ("No", 0.8)
        return (None, 0)

    def _match_staff(self, question: str, staff: List[Dict]) -> tuple:
        """Match staff questions with site personnel"""
        total_fte = sum(s.get("fte", 0) for s in staff)

        if 'how many' in question or 'number of' in question:
            if 'coordinator' in question:
                crc_count = len([s for s in staff if 'coordinator' in s["role"].lower()])
                return (crc_count, 0.9)
            elif 'investigator' in question:
                pi_count = len([s for s in staff if 'investigator' in s["role"].lower() or 'pi' in s["role"].lower()])
                return (pi_count, 0.9)
            else:
                return (len(staff), 0.8)

        elif 'fte' in question:
            return (total_fte, 0.9)

        elif 'adequate' in question or 'sufficient' in question:
            return ("Yes" if total_fte and total_fte > 1 else "No", 0.7)

        return (None, 0)

    def _match_experience(self, question: str, experience: List[Dict], protocol_info: Dict) -> tuple:
        """Match experience questions with site history"""
        protocol_indication = protocol_info.get("indication", "").lower() if protocol_info else ""
        protocol_phase = protocol_info.get("phase", "").lower() if protocol_info else ""

        # Find relevant experience
        relevant_exp = [
            e for e in experience
            if (protocol_indication and protocol_indication in e.get("indication", "").lower())
            or (protocol_phase and protocol_phase in e.get("phase", "").lower())
        ]

        if not relevant_exp:
            relevant_exp = experience  # Use all experience if no specific match

        if 'how many studies' in question:
            total_studies = sum(e.get("n_trials", 1) for e in relevant_exp)
            return (total_studies, 0.8)
        elif 'enrollment rate' in question:
            rates = [e.get("enrollment_rate", 0) for e in relevant_exp if e.get("enrollment_rate")]
            avg_rate = sum(rates) / len(rates) if rates else 0
            return (f"{avg_rate:.1f} patients/month", 0.7)
        elif 'experience' in question:
            return ("Yes" if relevant_exp else "No", 0.9)

        return (None, 0)

    def _match_population(self, question: str, capabilities: List[Dict], protocol_pop: Dict) -> tuple:
        """Match population questions with site capabilities"""
        protocol_indication = protocol_pop.get("indication", "").lower() if isinstance(protocol_pop, dict) else ""

        relevant_cap = [
            c for c in capabilities
            if protocol_indication in c.get("indication", "").lower()
        ]

        if not relevant_cap and capabilities:
            relevant_cap = capabilities[0:1]  # Use first capability as fallback

        if 'access' in question or 'available' in question:
            return ("Yes" if relevant_cap else "No", 0.8)
        elif 'how many' in question or 'volume' in question:
            if relevant_cap:
                total_volume = sum(c.get("annual_patients", 0) for c in relevant_cap)
                return (f"{total_volume} patients/year", 0.7)

        return (None, 0)

    def _extract_from_protocol(self, question: str, protocol_data: Dict) -> tuple:
        """Extract answers from protocol data"""
        if not protocol_data:
            return (None, 0)

        study_id = protocol_data.get("study_identification", {})

        if 'phase' in question:
            phase = study_id.get("phase")
            return (phase, 0.9) if phase else (None, 0)
        elif 'sponsor' in question:
            sponsor = study_id.get("sponsor")
            return (sponsor, 1.0) if sponsor else (None, 0)
        elif 'indication' in question:
            indication = study_id.get("indication")
            return (indication, 0.9) if indication else (None, 0)

        return (None, 0)

    def _intelligent_autofill(
        self,
        question: Dict,
        site_capabilities: Dict,
        protocol_requirements: Dict
    ) -> Dict:
        """Intelligently match site capabilities + protocol needs to answer survey questions"""

        question_text = question["text"].lower()
        response = None
        source = None
        confidence = 0

        # Population access questions
        if "access" in question_text and "population" in question_text:
            annual_volume = site_capabilities.get("annual_volume", 0) or 0
            therapeutic_areas = site_capabilities.get("therapeutic_areas", []) or []
            protocol_indication = protocol_requirements.get("study_identification", {}).get("indication", "") or ""

            if annual_volume and annual_volume > 1000 and therapeutic_areas and any(area.lower() in protocol_indication.lower() for area in therapeutic_areas):
                response = "Yes"
                confidence = 0.9
            else:
                response = "Limited access"
                confidence = 0.6
            source = "site_profile"

        # Patient enrollment rate questions
        elif "enroll per month" in question_text or "patients" in question_text and "month" in question_text:
            annual_volume = site_capabilities.get("annual_volume", 0)
            # Estimate monthly enrollment as ~5% of annual volume for specialized studies
            monthly_estimate = max(1, int(annual_volume * 0.05 / 12))
            response = f"{monthly_estimate}-{monthly_estimate + 2} patients"
            confidence = 0.7
            source = "site_profile"

        # Equipment questions
        elif "equipment" in question_text or "special" in question_text:
            site_equipment = site_capabilities.get("equipment", [])
            protocol_equipment = protocol_requirements.get("equipment_needed", [])

            missing_equipment = []
            for req_equipment in protocol_equipment:
                if not any(req_equipment.lower() in eq.lower() for eq in site_equipment):
                    missing_equipment.append(req_equipment)

            if missing_equipment:
                response = f"Missing: {', '.join(missing_equipment)}"
                confidence = 0.8
            else:
                response = "All required equipment available"
                confidence = 0.9
            source = "site_profile"

        # Staff adequacy questions
        elif "adequate staff" in question_text or "staff" in question_text:
            staff_fte = site_capabilities.get("staff_fte", 0)
            protocol_staff_req = protocol_requirements.get("staff_requirements", {})
            required_hours = protocol_staff_req.get("coordinator_time_hours_week", 10)

            if staff_fte >= (required_hours / 40):  # Convert to FTE requirement
                response = "Yes"
                confidence = 0.8
            else:
                response = "May need additional staff"
                confidence = 0.7
            source = "site_profile"

        # Sponsor/CRO experience questions
        elif "experience" in question_text and ("sponsor" in question_text or "cro" in question_text):
            previous_sponsors = site_capabilities.get("experience", [])
            protocol_sponsor = protocol_requirements.get("study_identification", {}).get("sponsor", "")

            if any(sponsor.lower() in protocol_sponsor.lower() for sponsor in previous_sponsors):
                response = "Yes"
                confidence = 0.9
            else:
                response = "No previous experience"
                confidence = 0.8
            source = "site_profile"

        # Budget questions (marked as subjective in our model, but could provide guidance)
        elif "budget" in question_text:
            # This is typically subjective, but we can provide a preliminary assessment
            response = "Requires detailed review"
            confidence = 0.3
            source = "preliminary_assessment"

        return {
            "response": response,
            "source": source,
            "confidence": confidence,
            "manually_edited": False
        }

    def _calculate_feasibility_score(
        self,
        responses: List[Dict],
        protocol_requirements: Dict,
        site_capabilities: Dict
    ) -> int:
        """Calculate overall feasibility score based on autofilled responses"""

        total_score = 0
        weight_sum = 0

        for response in responses:
            if response.get("is_objective") and response.get("response"):
                weight = 1.0
                score = 0

                if response["response"] in ["Yes", "All required equipment available"]:
                    score = 100
                elif "available" in str(response["response"]).lower():
                    score = 90
                elif response["response"] in ["No", "Missing:"]:
                    score = 30
                elif "limited" in str(response["response"]).lower():
                    score = 60
                elif "may need" in str(response["response"]).lower():
                    score = 70
                else:
                    score = 80  # Neutral/informational responses

                total_score += score * weight
                weight_sum += weight

        return int(total_score / weight_sum) if weight_sum > 0 else 85

    def _generate_flags(
        self,
        responses: List[Dict],
        protocol_requirements: Dict,
        site_capabilities: Dict
    ) -> List[str]:
        """Generate warning flags based on potential issues"""

        flags = []

        # Check for equipment gaps
        for response in responses:
            if response.get("response") and "Missing:" in str(response["response"]):
                flags.append("Equipment gaps identified")
                break

        # Check for staff concerns
        for response in responses:
            if response.get("response") and "may need additional" in str(response["response"]).lower():
                flags.append("Staffing concerns")
                break

        # Check for population access issues
        for response in responses:
            if response.get("response") and "limited access" in str(response["response"]).lower():
                flags.append("Limited patient population access")
                break

        # Check target enrollment vs capacity
        target_enrollment = protocol_requirements.get("study_identification", {}).get("target_enrollment", 0) or 0
        annual_volume = site_capabilities.get("annual_volume", 0) or 0

        if target_enrollment and annual_volume and target_enrollment > annual_volume * 0.1:  # More than 10% of annual volume
            flags.append("High enrollment target relative to site capacity")

        return flags