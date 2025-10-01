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
        UPDATED to handle new comprehensive nested structure
        """
        summary_parts = []

        # Basic site info
        if site_profile.get('name'):
            summary_parts.append(f"Site Name: {site_profile['name']}")

        # Population Capabilities - NEW STRUCTURE
        pop_caps = site_profile.get('population_capabilities', {})
        if pop_caps.get('annual_patient_volume'):
            summary_parts.append(f"Annual Patient Volume: {pop_caps['annual_patient_volume']:,}")
        if pop_caps.get('age_groups_treated'):
            summary_parts.append(f"Age Groups: {', '.join(pop_caps['age_groups_treated'])}")

        # Therapeutic areas (new field)
        if pop_caps.get('therapeutic_areas'):
            areas = pop_caps['therapeutic_areas'][:5]
            summary_parts.append(f"Therapeutic Areas: {', '.join(areas)}")
        # Fallback to old common_health_conditions
        elif pop_caps.get('common_health_conditions'):
            conditions = pop_caps['common_health_conditions'][:5]
            summary_parts.append(f"Common Conditions: {', '.join(conditions)}")

        # Patient population by condition (new nested structure)
        patient_pop = pop_caps.get('patient_population', {})
        if patient_pop.get('available_patients_by_condition'):
            conditions = patient_pop['available_patients_by_condition']
            # Show NASH patient count if available
            if 'NASH (Non-alcoholic Steatohepatitis)' in conditions:
                nash_count = conditions['NASH (Non-alcoholic Steatohepatitis)']
                summary_parts.append(f"NASH Patients: {nash_count:,} annually")

        # Staff and Experience - NEW STRUCTURE
        staff = site_profile.get('staff_and_experience', {})

        # Principal Investigator (new structure)
        pi = staff.get('principal_investigator', {})
        if pi.get('name'):
            pi_name = pi['name']
            pi_specialty = pi.get('specialty', 'Unknown specialty')
            pi_years = pi.get('years_experience', 0)
            summary_parts.append(f"Principal Investigator: {pi_name} ({pi_specialty}, {pi_years} years)")

        # Sub-investigators (new structure)
        sub_invs = staff.get('sub_investigators', [])
        if sub_invs:
            specialties = [s.get('specialty', 'Unknown') for s in sub_invs]
            summary_parts.append(f"Sub-Investigators: {len(sub_invs)} ({', '.join(specialties[:3])})")

        # Fallback to old investigators structure
        if not pi.get('name') and staff.get('investigators', {}).get('count'):
            inv_count = staff['investigators']['count']
            specialties = staff['investigators'].get('specialties', [])
            summary_parts.append(f"Investigators: {inv_count} ({', '.join(specialties[:3])})")

        # Study coordinators (new structure)
        study_coords = staff.get('study_coordinators', {})
        if study_coords.get('count'):
            coord_count = study_coords['count']
            summary_parts.append(f"Research Coordinators: {coord_count}")
        # Fallback to old coordinators structure
        elif staff.get('coordinators', {}).get('count'):
            coord_count = staff['coordinators']['count']
            summary_parts.append(f"Research Coordinators: {coord_count}")

        # Facilities and Equipment - NEW STRUCTURE
        facilities = site_profile.get('facilities_and_equipment', {})

        # Imaging (new object structure with boolean values)
        imaging = facilities.get('imaging', {})
        if isinstance(imaging, dict):
            # Extract equipment where value is True
            available_imaging = [key for key, value in imaging.items() if value is True and key != 'notes']
            if available_imaging:
                summary_parts.append(f"Imaging Equipment: {', '.join(available_imaging[:5])}")
        elif isinstance(imaging, list):
            # Fallback to old array structure
            summary_parts.append(f"Imaging Equipment: {', '.join(imaging[:5])}")

        # Laboratory (new nested structure)
        laboratory = facilities.get('laboratory', {})
        if laboratory.get('on_site_lab'):
            lab_caps = laboratory.get('capabilities', [])
            if 'PK processing' in lab_caps:
                summary_parts.append("Lab: CLIA-certified with PK processing capability")
            else:
                summary_parts.append("Lab: CLIA-certified onsite clinical lab")
        # Fallback to old structure
        elif facilities.get('lab_capabilities', {}).get('onsite_clinical_lab'):
            summary_parts.append("Lab: CLIA-certified onsite clinical lab")

        # Freezer storage (new nested in pharmacy)
        pharmacy = facilities.get('pharmacy', {})
        if pharmacy.get('investigational_drug_storage', {}).get('freezer_minus80C'):
            summary_parts.append("PK Storage: -80C freezer available")
        # Fallback to old structure
        elif facilities.get('lab_capabilities', {}).get('freezer_-80C'):
            summary_parts.append("PK Storage: -80C freezer available")

        # Operational Capabilities
        ops = site_profile.get('operational_capabilities', {})
        if ops.get('inpatient_capability'):
            summary_parts.append("Inpatient: Hospital units available")
        elif ops.get('inpatient_support'):
            summary_parts.append("Inpatient: Hospital units available")

        if ops.get('outpatient_clinic'):
            summary_parts.append("Outpatient: Dedicated research clinic")

        if ops.get('recruitment_methods'):
            methods = ops['recruitment_methods']
            summary_parts.append(f"Recruitment: {', '.join(methods[:3])}")
        elif ops.get('departments_involved'):
            depts = ops['departments_involved'][:3]
            summary_parts.append(f"Departments: {', '.join(depts)}")

        # Historical Performance
        history = site_profile.get('historical_performance', {})
        if history.get('studies_completed_last_5_years'):
            study_count = history['studies_completed_last_5_years']
            summary_parts.append(f"Experience: {study_count} studies in 5 years")
        elif history.get('studies_conducted_last_5_years'):
            study_count = history['studies_conducted_last_5_years']
            summary_parts.append(f"Experience: {study_count} studies in 5 years")

        if history.get('enrollment_success_rate'):
            success_rate = history['enrollment_success_rate']
            summary_parts.append(f"Enrollment Success: {success_rate}")

        # Compliance and Training
        compliance = site_profile.get('compliance_and_training', {})
        if compliance.get('gcp_training'):
            summary_parts.append("Training: All staff GCP-certified")
        elif compliance.get('GCP_training'):
            summary_parts.append("Training: All staff GCP-certified")

        if compliance.get('audit_history'):
            summary_parts.append("Audits: Clean FDA and sponsor audit history")

        return "\n".join(summary_parts) if summary_parts else "Limited site profile data available"

    def _format_protocol_requirements(self, requirements: Dict) -> str:
        """Format universal protocol requirements for AI comparison"""
        if not requirements:
            return "No specific protocol requirements available - assess general site capabilities"

        summary = []

        # Study Identification
        study_id = requirements.get('study_identification', {})
        if study_id:
            summary.append("STUDY IDENTIFICATION:")
            if study_id.get('protocol_number'):
                summary.append(f"  - Protocol: {study_id['protocol_number']}")
            if study_id.get('sponsor_name'):
                summary.append(f"  - Sponsor: {study_id['sponsor_name']}")
            if study_id.get('cro_name'):
                summary.append(f"  - CRO: {study_id['cro_name']}")
            if study_id.get('phase'):
                summary.append(f"  - Phase: {study_id['phase']}")
            if study_id.get('therapeutic_area'):
                summary.append(f"  - Therapeutic Area: {study_id['therapeutic_area']}")

        # Study Timeline
        timeline = requirements.get('study_timeline', {})
        if timeline:
            summary.append("\nSTUDY TIMELINE:")
            if timeline.get('total_duration_weeks'):
                weeks = timeline['total_duration_weeks']
                summary.append(f"  - Total Duration: {weeks} weeks ({weeks/4:.1f} months)")
            if timeline.get('enrollment_period_weeks'):
                summary.append(f"  - Enrollment Period: {timeline['enrollment_period_weeks']} weeks")
            if timeline.get('enrollment_target'):
                summary.append(f"  - Enrollment Target: {timeline['enrollment_target']} patients")
            if timeline.get('visit_frequency'):
                summary.append(f"  - Visit Frequency: {timeline['visit_frequency']}")
            if timeline.get('estimated_visit_count'):
                summary.append(f"  - Estimated Visits: {timeline['estimated_visit_count']}")
            if timeline.get('complexity'):
                summary.append(f"  - Study Complexity: {timeline['complexity'].upper()}")

        # Patient Population
        patient = requirements.get('patient_population', {})
        if patient:
            summary.append("\nPATIENT POPULATION REQUIRED:")
            if patient.get('primary_indication'):
                summary.append(f"  - Primary Indication: {patient['primary_indication']}")
            if patient.get('age_min') or patient.get('age_max'):
                age_min = patient.get('age_min', 'N/A')
                age_max = patient.get('age_max', 'N/A')
                summary.append(f"  - Age Range: {age_min}-{age_max} years")
            if patient.get('key_inclusion_criteria'):
                summary.append(f"  - Key Inclusion: {', '.join(patient['key_inclusion_criteria'][:3])}")
            if patient.get('key_exclusion_criteria'):
                summary.append(f"  - Key Exclusion: {', '.join(patient['key_exclusion_criteria'][:3])}")
            if patient.get('estimated_eligible_population'):
                summary.append(f"  - Eligible Population: {patient['estimated_eligible_population']}")

        # Staff Requirements
        staff = requirements.get('staff_requirements', [])
        if staff:
            summary.append("\nSTAFF REQUIRED:")
            for item in staff:
                criticality = item.get('criticality', 'optional').upper()
                role = item.get('role', 'Staff')
                spec = item.get('specialization', '')
                fte = item.get('fte', 'N/A')
                certs = item.get('certifications', [])
                cert_str = f", Certs: {', '.join(certs)}" if certs else ""
                summary.append(f"  [{criticality}] {role} ({fte} FTE) - {spec}{cert_str}")

        # Equipment Requirements
        equipment = requirements.get('equipment_required', [])
        if equipment:
            summary.append("\nEQUIPMENT REQUIRED:")
            for item in equipment:
                criticality = item.get('criticality', 'optional').upper()
                category = item.get('category', '')
                name = item.get('name', '')
                specs = item.get('specifications', '')
                spec_str = f" ({specs})" if specs else ""
                purpose = item.get('purpose', '')
                summary.append(f"  [{criticality}] {name}{spec_str} - {purpose}")

        # Procedures
        procedures = requirements.get('procedures', [])
        if procedures:
            summary.append("\nPROCEDURES REQUIRED:")
            for proc in procedures[:5]:  # Limit to 5
                criticality = proc.get('criticality', 'optional').upper()
                name = proc.get('name', '')
                frequency = proc.get('frequency', '')
                invasiveness = proc.get('invasiveness', '')
                summary.append(f"  [{criticality}] {name} - {frequency} ({invasiveness})")

        # Drug/Treatment
        drug = requirements.get('drug_treatment', {})
        if drug and drug.get('drug_name'):
            summary.append("\nDRUG/TREATMENT:")
            summary.append(f"  - Drug: {drug.get('drug_name')}")
            if drug.get('administration_route'):
                summary.append(f"  - Route: {drug['administration_route']}")
            if drug.get('pharmacy_requirements'):
                summary.append(f"  - Pharmacy: {drug['pharmacy_requirements']}")
            if drug.get('storage_conditions'):
                summary.append(f"  - Storage: {drug['storage_conditions']}")

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
        text_lower = question_text.lower()

        # Get protocol requirements if available
        protocol_requirements = site_profile.get('protocol_requirements', {})

        # QUESTION TYPE DETECTION - Handle before AI call
        # Type 1: DIRECT VALUE QUESTIONS - Return protocol/site values directly
        import re

        # Pattern matching for "What is..." questions
        what_is_match = re.match(r'^what\s+is\s+(the\s+)?(.+)\??$', text_lower)
        if what_is_match:
            # Extract what they're asking about
            asking_about = what_is_match.group(2).strip()

            # PRIORITY 1: Check for SPECIFIC participant count questions FIRST (most specific)
            if 'number' in asking_about and 'participant' in asking_about:
                enrollment_target = protocol_requirements.get('study_timeline', {}).get('enrollment_target')
                if enrollment_target:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='enrollment_target',
                        mapped_value=f'{enrollment_target} patients',
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: enrollment target is {enrollment_target} patients'
                    )

            # PRIORITY 2: Check for health status questions (specific)
            if 'health status' in asking_about or 'participant health' in asking_about:
                indication = protocol_requirements.get('patient_population', {}).get('primary_indication')
                inclusion = protocol_requirements.get('patient_population', {}).get('key_inclusion_criteria', [])
                if indication:
                    # Build comprehensive health status from indication and key criteria
                    health_status = indication
                    if inclusion:
                        health_status += f" ({', '.join(inclusion[:2])})"
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='patient_health_status',
                        mapped_value=health_status,
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: patient health status is {health_status}'
                    )

            # Check protocol data for other questions
            if 'phase' in asking_about:
                phase = protocol_requirements.get('study_identification', {}).get('phase')
                if phase:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='protocol_phase',
                        mapped_value=phase,
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: phase is {phase}'
                    )

            if 'duration' in asking_about or 'long' in asking_about:
                weeks = protocol_requirements.get('study_timeline', {}).get('total_duration_weeks')
                if weeks:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='study_duration',
                        mapped_value=f'{weeks} weeks ({weeks/4:.1f} months)',
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: study duration is {weeks} weeks'
                    )

            # PRIORITY 3: Population AGE questions (general population info, not count)
            if ('population age' in asking_about or 'age range' in asking_about or
                ('population' in asking_about and 'number' not in asking_about)):
                indication = protocol_requirements.get('patient_population', {}).get('primary_indication')
                age_min = protocol_requirements.get('patient_population', {}).get('age_min')
                age_max = protocol_requirements.get('patient_population', {}).get('age_max')
                if indication or (age_min and age_max):
                    # If asking specifically about age, return just age
                    if 'age' in asking_about:
                        if age_min and age_max:
                            return AIQuestionMapping(
                                question_id=question_id,
                                question_text=question_text,
                                mapped_field='population_age',
                                mapped_value=f'{age_min}-{age_max} years',
                                confidence_score=0.95,
                                source='protocol_direct',
                                reasoning=f'Direct protocol data: population age range is {age_min}-{age_max} years'
                            )
                    # Otherwise return indication with age
                    elif indication:
                        age_str = f', ages {age_min}-{age_max}' if age_min and age_max else ''
                        return AIQuestionMapping(
                            question_id=question_id,
                            question_text=question_text,
                            mapped_field='patient_population',
                            mapped_value=f'{indication}{age_str}',
                            confidence_score=0.95,
                            source='protocol_direct',
                            reasoning=f'Direct protocol data: population is {indication}'
                        )

            if 'therapeutic area' in asking_about or 'indication' in asking_about:
                therapeutic_area = protocol_requirements.get('study_identification', {}).get('therapeutic_area')
                if therapeutic_area:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='therapeutic_area',
                        mapped_value=therapeutic_area,
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: therapeutic area is {therapeutic_area}'
                    )

            if 'sponsor' in asking_about:
                sponsor = protocol_requirements.get('study_identification', {}).get('sponsor_name')
                if sponsor:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='sponsor_name',
                        mapped_value=sponsor,
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: sponsor is {sponsor}'
                    )

        # Type 2: HOW MANY - Return numeric values
        how_many_match = re.match(r'^how\s+many\s+(.+)\??$', text_lower)
        if how_many_match:
            asking_about = how_many_match.group(1).strip()

            # Check for time/hour questions first
            if 'hour' in asking_about:
                return AIQuestionMapping(
                    question_id=question_id,
                    question_text=question_text,
                    mapped_field='time_estimation',
                    mapped_value='Unable to determine specific hours without detailed protocol analysis',
                    confidence_score=0.6,
                    source='time_estimation',
                    reasoning='Time estimation question - requires detailed protocol review to provide accurate hours'
                )

            if 'participant' in asking_about or 'patient' in asking_about or 'subject' in asking_about:
                enrollment_target = protocol_requirements.get('study_timeline', {}).get('enrollment_target')
                if enrollment_target:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='enrollment_target',
                        mapped_value=f'{enrollment_target} patients',
                        confidence_score=0.95,
                        source='protocol_direct',
                        reasoning=f'Direct protocol data: enrollment target is {enrollment_target} patients'
                    )

            if 'coordinator' in asking_about:
                coord_count = site_profile.get('staff_and_experience', {}).get('coordinators', {}).get('count')
                if coord_count:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='coordinator_count',
                        mapped_value=f'{coord_count} coordinators',
                        confidence_score=0.95,
                        source='site_direct',
                        reasoning=f'Direct site data: {coord_count} coordinators available'
                    )

            if 'investigator' in asking_about or 'pi' in asking_about:
                inv_count = site_profile.get('staff_and_experience', {}).get('investigators', {}).get('count')
                if inv_count:
                    return AIQuestionMapping(
                        question_id=question_id,
                        question_text=question_text,
                        mapped_field='investigator_count',
                        mapped_value=f'{inv_count} investigators',
                        confidence_score=0.95,
                        source='site_direct',
                        reasoning=f'Direct site data: {inv_count} investigators available'
                    )

        # Type 3: CAPABILITY/GAP ANALYSIS QUESTIONS - Pass to AI for validation
        # Questions starting with "Do", "Does", "Is", "Are", "Can" need gap analysis
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

QUESTION TYPE DETECTION:
1. **Numeric questions** (What is..., How many..., How long...) → Return the NUMBER or VALUE from protocol/site
   - "What is the phase?" → "Phase III" (not "Yes, site can conduct Phase III")
   - "How many coordinators?" → "5 coordinators" (not "Yes, adequate staff")

2. **Capability questions** (Is..., Does..., Can...) → Validate if site meets requirements
   - "Is equipment available?" → "Yes, site has FibroScan" OR "No, site lacks FibroScan"

REQUIREMENT VALIDATION LOGIC:
1. **Identify what type of question this is** (numeric vs capability)
2. **For numeric questions**: Return the specific value from protocol or site data
3. **For capability questions**: Compare protocol requirements to site capabilities
4. **Answer naturally and accurately**:
   - Numeric answer: "Phase III", "48 weeks", "30 patients", "5 coordinators"
   - Capability match: "Yes, [specific reason]"
   - Capability gap: "No, [specific gap]"
   - Uncertain: "Unable to determine [what's missing]"
   - Partial: "Partially - [what's available and what's missing]"

VALIDATION EXAMPLES:

Example 1 - Clear Gap (Staff):
Q: "Does the site have adequate staff to conduct this study?"
Protocol Needs: PI with hepatology experience (0.3 FTE), FibroScan trained coordinator
Site Has: 3 PIs (Cardiology, Oncology, Endocrinology), 5 coordinators (GCP certified)
CORRECT Answer: "No, site lacks PI with hepatology experience and FibroScan trained personnel"
WRONG Answer: "Yes - 3 PIs and 5 coordinators available" ❌

Example 2 - Partial Match (Equipment):
Q: "Is specialized equipment required for this study available?"
Protocol Needs: [CRITICAL] FibroScan device, [CRITICAL] MRI with PDFF capability
Site Has: MRI (1.5T standard), CT Scanner, Ultrasound
CORRECT Answer: "Partially - site has MRI but not with PDFF capability, and lacks FibroScan device"
WRONG Answer: "Yes - MRI and imaging equipment available" ❌

Example 3 - Clear Match (Population):
Q: "Do you have access to the required patient population?"
Protocol Needs: NASH patients with F2-F3 fibrosis, 8-12 patients over 12 months
Site Has: 450 NASH patients annually, established screening program
CORRECT Answer: "Yes, site has 450 NASH patients annually and can easily meet 8-12 patient requirement"
WRONG Answer: "450 patients available" (not a clear answer) ❌

Example 4 - Insufficient Information:
Q: "Can site support the required visit schedule?"
Protocol Needs: [Information not provided in protocol]
Site Has: Flexible scheduling, experienced coordinators
CORRECT Answer: "Unable to determine without protocol's specific visit schedule requirements"
WRONG Answer: "Yes - site has flexible scheduling" ❌

DIRECT PROTOCOL DATA MAPPING:
When survey questions ask about protocol details, use extracted protocol data:

Example 5 - Protocol Phase:
Q: "What is the protocol phase?"
Protocol: Phase III
CORRECT Answer: "Phase III"
WRONG Answer: "Yes, site can conduct Phase III trials" ❌

Example 6 - Study Duration:
Q: "What is the duration of the study?"
Protocol: 48 weeks total duration
CORRECT Answer: "48 weeks (12 months)"
WRONG Answer: "Site can support long studies" ❌

Example 7 - Enrollment Target:
Q: "How many patients need to be enrolled?"
Protocol: Enrollment target 30 patients
CORRECT Answer: "30 patients"
WRONG Answer: "Site has capacity for enrollment" ❌

Example 8 - Sponsor Name:
Q: "Who is the sponsor?"
Protocol: Sponsor - Novartis Pharmaceuticals
CORRECT Answer: "Novartis Pharmaceuticals"
WRONG Answer: "Site has worked with major sponsors" ❌

Response format - return ONLY valid JSON:
{{
    "mapped_field": "requirement category being validated (e.g., 'staff_requirements', 'equipment_required')",
    "mapped_value": "Natural answer: 'Yes, [reason]' OR 'No, [gap]' OR 'Partially - [details]' OR 'Unable to determine [what's needed]'",
    "confidence_score": 0.0-1.0 (high if clear match/mismatch, medium for partial, low for uncertain),
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
   ✅ RIGHT: "No, site lacks PI with required hepatology specialty"

2. **Answer naturally with appropriate format** - Don't force Yes/No when uncertain or partial
   ❌ WRONG: "Yes" or "No" (no explanation)
   ✅ RIGHT: "Yes, site has FibroScan and all required imaging"
   ✅ RIGHT: "Partially - site has MRI but lacks PDFF capability"
   ✅ RIGHT: "Unable to determine without protocol's specific visit schedule"

3. **WHO questions** → Names or "Unknown", never numbers
   ✅ "Principal Investigator Name" or "Unknown"
   ❌ "Yes" or "5"

4. **Match SPECIFIC protocol requirements**, not general capabilities
   Example: Protocol needs "NASH patients with F2-F3 fibrosis"
   ❌ WRONG: "Yes - 450 NASH patients available"
   ✅ RIGHT: "Yes, 450 NASH patients with FibroScan for fibrosis staging"
   ✅ RIGHT: "Partially - 450 NASH patients but no fibrosis staging capability"

5. **Use "Partially" for partial matches** - ONE missing requirement ≠ complete "No"
   Example: Protocol needs [CRITICAL] FibroScan + [CRITICAL] Hepatology PI
   Site has: FibroScan but no hepatology PI
   ✅ RIGHT: "Partially - site has FibroScan but lacks PI with hepatology specialization (critical gap)"
   ❌ WRONG: "No" (ignores what site DOES have)

6. **Provide actionable gap analysis in all answers**
   ❌ WRONG: "No - inadequate"
   ✅ RIGHT: "No, missing FibroScan device and hepatology-trained staff"
   ✅ RIGHT: "Partially - has FibroScan but lacks hepatology-trained staff"

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