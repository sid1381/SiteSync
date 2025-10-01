"""
AI-Powered Question Mapper
Uses OpenAI to intelligently map survey questions to site profile data
"""

import os
import json
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from app.services.openai_client import get_openai_client

@dataclass
class AIQuestionMapping:
    question_id: str
    question_text: str
    mapped_field: str
    mapped_value: Any
    confidence_score: float
    source: str
    reasoning: str

class AIQuestionMapper:
    """
    Uses AI to intelligently understand survey questions and map them to
    the most semantically appropriate site profile fields
    """

    def __init__(self):
        self.openai_client = get_openai_client()

    def map_questions_to_site_profile(self, questions: List[Dict], site_profile: Dict) -> List[AIQuestionMapping]:
        """
        Use AI to intelligently map each question to the most appropriate site profile field
        """
        mappings = []

        # Create a comprehensive site profile summary for the AI
        site_summary = self._create_site_profile_summary(site_profile)

        for question in questions:
            try:
                mapping = self._map_single_question_with_ai(question, site_summary, site_profile)
                if mapping:
                    mappings.append(mapping)
            except Exception as e:
                print(f"Error mapping question '{question.get('text', '')}': {e}")
                # Fallback to unmapped
                mappings.append(AIQuestionMapping(
                    question_id=question.get('id', ''),
                    question_text=question.get('text', ''),
                    mapped_field='unmapped',
                    mapped_value=None,
                    confidence_score=0.0,
                    source='mapping_error',
                    reasoning=f"Error during mapping: {str(e)}"
                ))

        return mappings

    def _create_site_profile_summary(self, site_profile: Dict) -> str:
        """
        Create a comprehensive summary of site profile data from JSONB structure
        """
        summary_parts = []

        # Basic site info
        if site_profile.get('name'):
            summary_parts.append(f"Site Name: {site_profile['name']}")

        # Population Capabilities
        pop_caps = site_profile.get('population_capabilities', {})
        if pop_caps.get('annual_patient_volume'):
            summary_parts.append(f"Annual Patient Volume: {pop_caps['annual_patient_volume']:,}")
        if pop_caps.get('age_groups_treated'):
            summary_parts.append(f"Age Groups: {', '.join(pop_caps['age_groups_treated'])}")
        if pop_caps.get('common_health_conditions'):
            conditions = pop_caps['common_health_conditions'][:5]  # First 5
            summary_parts.append(f"Common Conditions: {', '.join(conditions)}")

        # Staff and Experience
        staff = site_profile.get('staff_and_experience', {})
        if staff.get('coordinators', {}).get('count'):
            coord_count = staff['coordinators']['count']
            summary_parts.append(f"Research Coordinators: {coord_count}")
        if staff.get('investigators', {}).get('count'):
            inv_count = staff['investigators']['count']
            specialties = staff['investigators'].get('specialties', [])
            summary_parts.append(f"Investigators: {inv_count} ({', '.join(specialties[:3])})")

        # Facilities and Equipment
        facilities = site_profile.get('facilities_and_equipment', {})
        if facilities.get('imaging'):
            imaging = facilities['imaging'][:5]  # First 5
            summary_parts.append(f"Imaging Equipment: {', '.join(imaging)}")
        if facilities.get('lab_capabilities', {}).get('onsite_clinical_lab'):
            summary_parts.append("Lab: CLIA-certified onsite clinical lab")
        if facilities.get('lab_capabilities', {}).get('freezer_-80C'):
            summary_parts.append("PK Storage: -80C freezer available")

        # Operational Capabilities
        ops = site_profile.get('operational_capabilities', {})
        if ops.get('inpatient_support'):
            summary_parts.append("Inpatient: Hospital units available")
        if ops.get('outpatient_clinic'):
            summary_parts.append("Outpatient: Dedicated research clinic")
        if ops.get('departments_involved'):
            depts = ops['departments_involved'][:3]
            summary_parts.append(f"Departments: {', '.join(depts)}")

        # Historical Performance
        history = site_profile.get('historical_performance', {})
        if history.get('studies_conducted_last_5_years'):
            study_count = history['studies_conducted_last_5_years']
            summary_parts.append(f"Experience: {study_count} studies in 5 years")
        if history.get('enrollment_success_rate'):
            success_rate = history['enrollment_success_rate']
            summary_parts.append(f"Enrollment Success: {success_rate}")

        # Compliance and Training
        compliance = site_profile.get('compliance_and_training', {})
        if compliance.get('GCP_training'):
            summary_parts.append("Training: All staff GCP-certified")
        if compliance.get('audit_history'):
            summary_parts.append("Audits: Clean FDA and sponsor audit history")

        return "\n".join(summary_parts) if summary_parts else "Limited site profile data available"

    def _format_protocol_requirements(self, requirements: Dict) -> str:
        """Format protocol requirements for AI comparison"""
        if not requirements:
            return "No specific protocol requirements available - assess general site capabilities"

        summary = []

        # Equipment requirements
        equipment = requirements.get('equipment_required', [])
        if equipment:
            summary.append("EQUIPMENT REQUIRED:")
            for item in equipment:
                criticality = item.get('criticality', 'optional').upper()
                summary.append(f"  [{criticality}] {item.get('name')} - {item.get('purpose', '')}")

        # Staff requirements
        staff = requirements.get('staff_requirements', [])
        if staff:
            summary.append("\nSTAFF REQUIRED:")
            for item in staff:
                criticality = item.get('criticality', 'optional').upper()
                role = item.get('role')
                spec = item.get('specialization', '')
                fte = item.get('fte', 'N/A')
                summary.append(f"  [{criticality}] {role} ({fte} FTE) with {spec}")

        # Patient criteria
        patient = requirements.get('patient_criteria', {})
        if patient:
            summary.append("\nPATIENT POPULATION REQUIRED:")
            summary.append(f"  - Age: {patient.get('age_min', 'N/A')}-{patient.get('age_max', 'N/A')} years")
            summary.append(f"  - Target Enrollment: {patient.get('target_enrollment', 'N/A')} patients")
            summary.append(f"  - Primary Indication: {patient.get('primary_indication', 'N/A')}")
            if patient.get('key_inclusion'):
                summary.append(f"  - Key Inclusion: {', '.join(patient['key_inclusion'][:3])}")

        # Procedures
        procedures = requirements.get('procedures', [])
        if procedures:
            summary.append("\nPROCEDURES REQUIRED:")
            for proc in procedures[:5]:  # Limit to 5
                criticality = proc.get('criticality', 'optional').upper()
                summary.append(f"  [{criticality}] {proc.get('name')} - {proc.get('frequency', '')}")

        # Critical flags
        flags = requirements.get('critical_flags', [])
        if flags:
            summary.append("\nCRITICAL DISQUALIFIERS:")
            for flag in flags:
                summary.append(f"  ⚠️ {flag}")

        return "\n".join(summary)

    def _map_single_question_with_ai(self, question: Dict, site_summary: str, site_profile: Dict) -> Optional[AIQuestionMapping]:
        """
        Use AI to validate if site meets protocol requirements for this question
        """
        question_text = question.get('text', '')
        question_id = question.get('id', '')

        # Get protocol requirements if available
        protocol_requirements = site_profile.get('protocol_requirements', {})
        equipment_required = protocol_requirements.get('equipment_required', [])
        staff_requirements = protocol_requirements.get('staff_requirements', [])
        patient_criteria = protocol_requirements.get('patient_criteria', {})
        procedures = protocol_requirements.get('procedures', [])

        requirements_summary = self._format_protocol_requirements(protocol_requirements)

        prompt = f"""You are a FEASIBILITY ASSESSOR checking if this site can run THIS SPECIFIC PROTOCOL.

CRITICAL: You are NOT just mapping data. You are VALIDATING if the site meets protocol requirements.

QUESTION: "{question_text}"

PROTOCOL REQUIREMENTS:
{requirements_summary}

SITE CAPABILITIES:
{site_summary}

YOUR TASK: VALIDATE if the site can meet protocol requirements. You are a FEASIBILITY ASSESSOR, not a data retriever.

REQUIREMENT VALIDATION LOGIC:
1. **Identify what the protocol specifically needs** for this question
2. **Compare protocol requirements to site capabilities**
3. **Answer YES only if ALL requirements are met**
4. **Answer NO with specific explanation if ANY requirement is missing**
5. **Be decisive** - Clear Yes/No, not "maybe" or "generally yes"

VALIDATION EXAMPLES:

Example 1 - Staff Question:
Q: "Does the site have adequate staff to conduct this study?"
Protocol Needs: PI with hepatology experience (0.3 FTE), FibroScan trained coordinator
Site Has: 3 PIs (Cardiology, Oncology, Endocrinology), 5 coordinators (GCP certified)
CORRECT Answer: "No - Site lacks PI with hepatology experience and FibroScan trained personnel"
WRONG Answer: "Yes - 3 PIs and 5 coordinators available" ❌

Example 2 - Equipment Question:
Q: "Is specialized equipment required for this study available?"
Protocol Needs: [CRITICAL] FibroScan device, [CRITICAL] MRI with PDFF capability
Site Has: MRI (1.5T standard), CT Scanner, Ultrasound
CORRECT Answer: "No - Missing FibroScan device and MRI lacks PDFF capability required by protocol"
WRONG Answer: "Yes - MRI and imaging equipment available" ❌

Example 3 - Population Question:
Q: "Do you have access to the required patient population?"
Protocol Needs: NASH patients with F2-F3 fibrosis, 8-12 patients over 12 months
Site Has: 450 NASH patients annually, established screening program
CORRECT Answer: "Yes - 450 NASH patients/year available, can easily meet 8-12 patient requirement"
WRONG Answer: "450 patients available" (not answering the YES/NO question) ❌

Response format - return ONLY valid JSON:
{{
    "mapped_field": "requirement category being validated (e.g., 'staff_requirements', 'equipment_required')",
    "mapped_value": "DECISIVE answer: 'Yes - [specific reason]' OR 'No - [specific gap identified]'",
    "confidence_score": 0.0-1.0 (high if clear match/mismatch, lower if uncertain),
    "reasoning": "Requirement validation logic: what protocol needs vs what site has",
    "source": "requirement_validation"
}}

REQUIREMENT VALIDATION PATTERNS:

STAFF VALIDATION:
- "Adequate staff?" → Compare protocol's specific staff needs (PI specialty, coordinator training, FTE) to site's actual staff
  Example: Protocol needs "PI with hepatology" → Check if ANY site PI has hepatology specialty
- "PI qualified?" → Verify PI specialty matches protocol's therapeutic area
- "Coordinator experience?" → Check if coordinators have protocol-specific training (GCP, device-specific, etc.)

EQUIPMENT VALIDATION:
- "Equipment available?" → Check if EVERY piece of critical equipment in protocol is available at site
  Example: Protocol needs "FibroScan" → Answer "No" if site only has standard imaging
- "Special procedures possible?" → Validate site can perform protocol-specific procedures
- "Lab capabilities sufficient?" → Ensure lab certifications match protocol requirements

POPULATION VALIDATION:
- "Access to population?" → Verify site has protocol's SPECIFIC patient type AND volume
  Example: Protocol needs "NASH F2-F3" → Check if site has NASH patients with fibrosis staging capability
- "Enrollment feasible?" → Compare protocol's target enrollment to site's actual patient volume
- "Age criteria met?" → Verify site's patient age range covers protocol's requirements

EXPERIENCE VALIDATION:
- "Prior experience?" → Check if site has run studies in protocol's EXACT therapeutic area
  Example: Protocol is NASH Phase II → Check for prior NASH or hepatology experience (not just general GI)
- "Phase experience?" → Verify site has conducted studies at protocol's phase level

CRITICAL REQUIREMENT VALIDATION RULES:

1. **ALWAYS compare protocol to site** - Never just list what site has
   ❌ WRONG: "Site has 3 PIs and 5 coordinators"
   ✅ RIGHT: "No - Site lacks PI with required hepatology specialty"

2. **Be DECISIVE with Yes/No questions** - Include specific validation reason
   ❌ WRONG: "Yes" or "No" (no explanation)
   ✅ RIGHT: "Yes - Site has FibroScan and all required imaging" OR "No - Missing MRI with PDFF capability"

3. **WHO questions** → Names or "Unknown", never numbers
   ✅ "Principal Investigator Name" or "Unknown"
   ❌ "Yes" or "5"

4. **Match SPECIFIC protocol requirements**, not general capabilities
   Example: Protocol needs "NASH patients with F2-F3 fibrosis"
   ❌ WRONG: "Yes - 450 NASH patients available"
   ✅ RIGHT: "Yes - 450 NASH patients with FibroScan for fibrosis staging" OR "No - No fibrosis staging capability"

5. **ALL critical requirements must be met for "Yes"** - ONE missing requirement = "No"
   Example: Protocol needs [CRITICAL] FibroScan + [CRITICAL] Hepatology PI
   Site has: FibroScan but no hepatology PI
   ✅ RIGHT: "No - Missing PI with hepatology specialization (critical requirement)"

6. **Provide actionable gap analysis in "No" answers**
   ❌ WRONG: "No - inadequate"
   ✅ RIGHT: "No - Missing FibroScan device and hepatology-trained staff"

EXAMPLES OF CORRECT SEMANTIC MATCHING:
Q: "Who is the PI?" → A: "Principal Investigator Name" or "Unknown" (not "Yes" or numbers)
Q: "Who is the sponsor?" → A: "Sponsor name to be determined" or "Unknown" (not "Yes" or booleans)
Q: "Do you have imaging capability?" → A: "Yes" (not "MRI 1.5T, CT 64-slice")
Q: "What imaging equipment is available?" → A: "MRI (1.5T), CT (64-slice), Ultrasound, DEXA"
Q: "How many research coordinators?" → A: "5" (not "5 coordinators with avg 6 years experience")
Q: "Adequate staff to conduct study?" → A: "Yes" (not "5 coordinators, 3 investigators")
"""

        try:
            # Use unified client with automatic API detection and fallback
            result = self.openai_client.create_json_completion(
                prompt=prompt,
                system_message="You are a CLINICAL TRIAL FEASIBILITY ASSESSOR. Your job is to VALIDATE if the site can run THIS SPECIFIC PROTOCOL by comparing protocol requirements to site capabilities. Be DECISIVE - answer Yes only if ALL requirements are met, No if ANY are missing. Provide specific gap analysis. Return only valid JSON.",
                temperature=0.1,
                max_tokens=500
            )

            return AIQuestionMapping(
                question_id=question_id,
                question_text=question_text,
                mapped_field=result.get('mapped_field', 'unmapped'),
                mapped_value=result.get('mapped_value', ''),
                confidence_score=float(result.get('confidence_score', 0.0)),
                source=result.get('source', 'ai_mapping'),
                reasoning=result.get('reasoning', 'AI mapping completed')
            )

        except Exception as e:
            print(f"AI mapping failed for question '{question_text}': {e}")
            # Return low-confidence unmapped result
            return AIQuestionMapping(
                question_id=question_id,
                question_text=question_text,
                mapped_field='unmapped',
                mapped_value='',
                confidence_score=0.1,
                source='ai_fallback',
                reasoning=f"AI mapping failed: {str(e)}"
            )

    def generate_autofill_responses(self, mappings: List[AIQuestionMapping], questions: List[Dict], site_profile: Dict) -> List[Dict]:
        """
        Generate autofilled responses based on AI mappings
        """
        responses = []

        for i, question in enumerate(questions):
            question_id = question.get('id', f'q_{i+1}')
            is_objective = question.get('is_objective', True)

            # Subjective questions ALWAYS require manual input, regardless of mapping
            if not is_objective:
                response = {
                    'id': question_id,
                    'text': question.get('text', ''),
                    'type': question.get('type', 'text'),
                    'is_objective': False,
                    'response': '',
                    'source': 'manual_required',
                    'confidence': 0.0,
                    'manually_edited': False,
                    'reasoning': 'Subjective question requires manual input'
                }
                responses.append(response)
                continue

            # Find the corresponding mapping for objective questions
            mapping = next((m for m in mappings if m.question_id == question_id), None)

            if mapping and mapping.confidence_score > 0.3 and mapping.mapped_value:
                response = {
                    'id': question_id,
                    'text': question.get('text', ''),
                    'type': question.get('type', 'text'),
                    'is_objective': True,
                    'response': str(mapping.mapped_value),
                    'source': 'ai_mapping',
                    'confidence': mapping.confidence_score,
                    'manually_edited': False,
                    'reasoning': mapping.reasoning
                }
            else:
                # Low confidence or unmapped objective question - requires manual input
                response = {
                    'id': question_id,
                    'text': question.get('text', ''),
                    'type': question.get('type', 'text'),
                    'is_objective': True,
                    'response': '',
                    'source': 'manual_required',
                    'confidence': 0.0,
                    'manually_edited': False,
                    'reasoning': mapping.reasoning if mapping else 'No mapping found'
                }

            responses.append(response)

        return responses

    def get_mapping_statistics(self, mappings: List[AIQuestionMapping]) -> Dict[str, Any]:
        """
        Generate statistics about the AI mapping quality
        """
        total_mappings = len(mappings)
        if total_mappings == 0:
            return {"total_mappings": 0, "average_confidence": 0.0}

        high_confidence = sum(1 for m in mappings if m.confidence_score >= 0.8)
        medium_confidence = sum(1 for m in mappings if 0.6 <= m.confidence_score < 0.8)
        low_confidence = sum(1 for m in mappings if m.confidence_score < 0.6)

        avg_confidence = sum(m.confidence_score for m in mappings) / total_mappings

        return {
            "total_mappings": total_mappings,
            "average_confidence": round(avg_confidence, 3),
            "high_confidence_count": high_confidence,
            "medium_confidence_count": medium_confidence,
            "low_confidence_count": low_confidence,
            "confidence_distribution": {
                "high (≥80%)": high_confidence,
                "medium (60-79%)": medium_confidence,
                "low (<60%)": low_confidence
            }
        }