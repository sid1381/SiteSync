"""
Smart Question Mapper
Maps extracted survey questions to site profile data intelligently
"""

import re
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
import json

@dataclass
class QuestionMapping:
    question_id: str
    question_text: str
    mapped_field: str
    mapped_value: Any
    confidence_score: float
    source: str
    reasoning: str

class SmartQuestionMapper:
    """
    Intelligently maps survey questions to site profile data using fuzzy matching
    and semantic understanding
    """

    def __init__(self):
        # Define comprehensive mapping patterns for UAB and other survey question types
        self.field_mappings = {
            # Basic Site Information
            'site_info_patterns': {
                'patterns': [
                    r'(name.*research.*site|site.*name|institution.*name)',
                    r'(principal.*investigator|pi.*name|investigator.*name)',
                    r'(address|location|facility)',
                    r'(contact.*information|phone|email)',
                ],
                'site_fields': ['name', 'pi_name', 'institution', 'address', 'contact_info']
            },

            # Staff and Personnel (Enhanced)
            'staff_patterns': {
                'patterns': [
                    r'(research.*coordinators?.*fte|coordinators?.*available)',
                    r'(how many.*coordinators?|number.*coordinators?)',
                    r'(research.*staff|personnel|investigators?)',
                    r'(adequate.*staff|sufficient.*staff)',
                    r'(weekend.*coverage|evening.*availability|24.*hour)',
                    r'(staffing.*levels|staff.*capacity)',
                ],
                'site_fields': ['coordinators_fte', 'weekend_coverage', 'specialist_access', 'staff_availability']
            },

            # Patient Population (Enhanced)
            'population_patterns': {
                'patterns': [
                    r'(population.*age.*range|age.*range.*recruit)',
                    r'(patient.*age.*min|patient.*age.*max|age.*criteria)',
                    r'(access.*participant.*population|access.*patients)',
                    r'(annual.*patient.*volume|yearly.*volume|patient.*database)',
                    r'(patients.*enroll.*month|enrollment.*capacity|recruit.*rate)',
                    r'(suitable.*patients|eligible.*patients|target.*population)',
                ],
                'site_fields': ['patient_age_range_min', 'patient_age_range_max', 'annual_patient_volume',
                              'enrollment_capacity_per_month', 'recruitment_sources', 'patient_database_size']
            },

            # Equipment and Capabilities (Enhanced)
            'equipment_patterns': {
                'patterns': [
                    r'(special.*equipment.*required|specialized.*equipment)',
                    r'(imaging.*equipment|mri|ct.*scan|ultrasound|x.?ray)',
                    r'(laboratory.*equipment|lab.*capabilities|centrifuge)',
                    r'(necessary.*imaging|equipped.*imaging)',
                    r'(pk.*samples?|pharmacokinetic|blood.*samples?)',
                    r'(sample.*storage|freezer|refrigerat|storage.*capabilities)',
                    r'(washout.*period|washout.*management|drug.*washout)',
                ],
                'site_fields': ['special_equipment', 'imaging_equipment', 'laboratory_capabilities',
                              'pk_sampling_capable', 'sample_storage', 'washout_capability']
            },

            # Experience and Therapeutic Areas (Enhanced)
            'experience_patterns': {
                'patterns': [
                    r'(experience.*therapeutic.*area|therapeutic.*experience)',
                    r'(experience.*sponsor|worked.*sponsor|previous.*sponsor)',
                    r'(phase.*experience|clinical.*trials?.*experience)',
                    r'(indication.*experience|disease.*experience)',
                    r'(completed.*studies|previous.*studies|trial.*history)',
                ],
                'site_fields': ['therapeutic_areas', 'previous_sponsors', 'phase_experience',
                              'indication_experience', 'trial_completion_history']
            },

            # Study Operations (New)
            'operations_patterns': {
                'patterns': [
                    r'(study.*duration|duration.*study|length.*study)',
                    r'(budget.*cover|proposed.*budget|financial.*capacity)',
                    r'(time.*requirements|study.*time|visit.*schedule)',
                    r'(regulatory.*experience|irb.*experience|ethics)',
                    r'(data.*management|edc.*experience|electronic.*data)',
                    r'(recruitment.*strategy|patient.*recruitment)',
                ],
                'site_fields': ['budget_management_experience', 'regulatory_experience',
                              'edc_systems', 'recruitment_strategies', 'visit_capacity']
            },

            # Specific Clinical Capabilities (New)
            'clinical_patterns': {
                'patterns': [
                    r'(inclusion.*criteria|exclusion.*criteria|patient.*criteria)',
                    r'(concerns.*criteria|challenges.*criteria)',
                    r'(protocol.*compliance|ensure.*compliance)',
                    r'(adverse.*events|safety.*monitoring|aes?)',
                    r'(concomitant.*medications|drug.*interactions)',
                    r'(follow.?up.*visits|retention.*patients|patient.*retention)',
                ],
                'site_fields': ['protocol_compliance_experience', 'safety_monitoring',
                              'patient_retention_rate', 'concomitant_med_management']
            }
        }

    def map_questions_to_site_profile(
        self,
        questions: List[Dict],
        site_profile: Dict
    ) -> List[QuestionMapping]:
        """
        Map survey questions to site profile data with confidence scoring
        """
        mappings = []

        for question in questions:
            if question.get('is_objective', False):
                mapping = self._find_best_mapping(question, site_profile)
                if mapping:
                    mappings.append(mapping)

        return mappings

    def _find_best_mapping(self, question: Dict, site_profile: Dict) -> Optional[QuestionMapping]:
        """
        Find the best mapping for a single question
        """
        question_text = question.get('text', '').lower()
        question_id = question.get('id', '')

        best_mapping = None
        best_confidence = 0.0

        # First, try simple keyword-based mapping (more reliable)
        simple_mapping = self._simple_keyword_mapping(question_text, site_profile)
        if simple_mapping:
            return QuestionMapping(
                question_id=question_id,
                question_text=question_text,
                mapped_field=simple_mapping['field'],
                mapped_value=simple_mapping['value'],
                confidence_score=simple_mapping['confidence'],
                source='site_profile',
                reasoning=simple_mapping['reasoning']
            )

        # Then try special mappings for complex questions
        special_mapping = self._handle_special_mappings(question_text, site_profile)
        if special_mapping:
            return QuestionMapping(
                question_id=question_id,
                question_text=question_text,
                mapped_field=special_mapping['field'],
                mapped_value=special_mapping['value'],
                confidence_score=special_mapping['confidence'],
                source='site_profile',
                reasoning=special_mapping['reasoning']
            )

        # Then try each category of patterns
        for category, config in self.field_mappings.items():
            for pattern in config['patterns']:
                if re.search(pattern, question_text, re.IGNORECASE):
                    # Found a pattern match, now find the best site field
                    for field_path in config['site_fields']:
                        mapping = self._create_mapping_simple(
                            question_id, question_text, field_path, site_profile, pattern
                        )
                        if mapping and mapping.confidence_score > best_confidence:
                            best_mapping = mapping
                            best_confidence = mapping.confidence_score

        # If no pattern match, try fuzzy matching with field names
        if not best_mapping:
            best_mapping = self._fuzzy_match_fields(question_id, question_text, site_profile)

        return best_mapping

    def _create_mapping_simple(
        self,
        question_id: str,
        question_text: str,
        field_path: str,
        site_profile: Dict,
        pattern: str
    ) -> Optional[QuestionMapping]:
        """
        Create a simple question mapping for a specific field (no special cases)
        """
        # Navigate to the field value in nested site profile
        value = self._get_nested_value(site_profile, field_path)

        if value is None:
            return None

        # Calculate confidence based on pattern match strength and value availability
        confidence = self._calculate_confidence(question_text, field_path, pattern, value)

        # Format the value appropriately
        formatted_value = self._format_value_for_question(value, question_text)

        return QuestionMapping(
            question_id=question_id,
            question_text=question_text,
            mapped_field=field_path,
            mapped_value=formatted_value,
            confidence_score=confidence,
            source='site_profile',
            reasoning=f"Pattern '{pattern}' matched field '{field_path}'"
        )

    def _handle_special_mappings(self, question_text: str, site_profile: Dict) -> Optional[Dict]:
        """
        Handle special question types that need custom logic
        """
        q_lower = question_text.lower()

        # WHO questions - return names, not numbers or booleans
        if q_lower.startswith('who '):
            # "Who is the PI?"
            if re.search(r'who.*is.*(pi|principal.*investigator)', q_lower):
                pi_name = self._get_nested_value(site_profile, 'pi_name')
                if pi_name:
                    return {
                        'field': 'pi_name',
                        'value': pi_name,
                        'confidence': 0.95,
                        'reasoning': 'Direct mapping to PI name'
                    }
                else:
                    return {
                        'field': 'pi_name',
                        'value': 'Unknown',
                        'confidence': 0.7,
                        'reasoning': 'PI name not available in site profile'
                    }

            # "Who is the sponsor?"
            if re.search(r'who.*is.*(sponsor|study.*sponsor)', q_lower):
                # Check if sponsor is in protocol data
                sponsor = self._get_nested_value(site_profile, 'sponsor_name')
                if sponsor:
                    return {
                        'field': 'sponsor_name',
                        'value': sponsor,
                        'confidence': 0.9,
                        'reasoning': 'Direct mapping to sponsor name'
                    }
                else:
                    return {
                        'field': 'sponsor_name',
                        'value': 'Unknown',
                        'confidence': 0.6,
                        'reasoning': 'Sponsor information not available'
                    }

            # "Who completed this form?" - This is form metadata, should be filtered
            # But if it gets through, return Unknown
            if re.search(r'who.*(completed|filled|submitted)', q_lower):
                return {
                    'field': 'form_completion',
                    'value': 'Unknown',
                    'confidence': 0.3,
                    'reasoning': 'Form metadata question - should be filtered'
                }

        # Age range questions
        if re.search(r'(age.*range|population.*age)', q_lower):
            min_age = self._get_nested_value(site_profile, 'patient_age_range_min')
            max_age = self._get_nested_value(site_profile, 'patient_age_range_max')

            if min_age is not None and max_age is not None:
                return {
                    'field': 'patient_age_range',
                    'value': f"{min_age}-{max_age} years",
                    'confidence': 0.9,
                    'reasoning': 'Combined min/max age ranges from site profile'
                }
            elif min_age is not None:
                return {
                    'field': 'patient_age_range_min',
                    'value': f"{min_age}+ years",
                    'confidence': 0.8,
                    'reasoning': 'Minimum age available in site profile'
                }

        # Duration questions (should come from protocol if available)
        if re.search(r'(duration.*study|study.*duration|length.*study)', q_lower):
            duration = self._get_nested_value(site_profile, 'study_duration_weeks')
            if duration:
                return {
                    'field': 'study_duration',
                    'value': f"{duration} weeks",
                    'confidence': 0.85,
                    'reasoning': 'Study duration from protocol data'
                }

        # PK sampling questions
        if re.search(r'(pk.*samples?|pharmacokinetic|blood.*draws?)', q_lower):
            pk_capable = self._get_nested_value(site_profile, 'laboratory_capabilities')
            if isinstance(pk_capable, list) and any('pk' in str(item).lower() for item in pk_capable):
                return {
                    'field': 'pk_sampling_capable',
                    'value': 'Yes - PK sampling capabilities available',
                    'confidence': 0.9,
                    'reasoning': 'PK capabilities found in laboratory equipment'
                }
            elif isinstance(pk_capable, dict) and pk_capable.get('pk_sampling'):
                return {
                    'field': 'pk_sampling_capable',
                    'value': 'Yes - PK sampling available',
                    'confidence': 0.9,
                    'reasoning': 'PK sampling explicitly listed in capabilities'
                }

        # Washout period questions
        if re.search(r'(washout.*period|washout.*management|drug.*washout)', q_lower):
            washout = self._get_nested_value(site_profile, 'washout_capability')
            if washout:
                return {
                    'field': 'washout_capability',
                    'value': 'Yes - Washout management experience available',
                    'confidence': 0.85,
                    'reasoning': 'Washout capabilities confirmed in site profile'
                }

        # Staff adequacy questions
        if re.search(r'(adequate.*staff|sufficient.*staff)', q_lower):
            coordinators = self._get_nested_value(site_profile, 'coordinators_fte')
            if coordinators and coordinators >= 1.0:
                return {
                    'field': 'coordinators_fte',
                    'value': f'Yes - {coordinators} FTE coordinators available',
                    'confidence': 0.9,
                    'reasoning': 'Adequate staffing based on FTE count'
                }

        # Budget coverage questions
        if re.search(r'(budget.*cover|proposed.*budget)', q_lower):
            budget_exp = self._get_nested_value(site_profile, 'budget_management_experience')
            if budget_exp:
                return {
                    'field': 'budget_management_experience',
                    'value': 'Yes - Experience with budget management',
                    'confidence': 0.8,
                    'reasoning': 'Budget management experience available'
                }

        # GCP certification questions
        if re.search(r'(gcp.*cert|good.*clinical.*practice|certification)', q_lower):
            training_available = self._get_nested_value(site_profile, 'staff_resources.available_for_training')
            phase_exp = self._get_nested_value(site_profile, 'experience_history.phase_experience')
            if training_available and phase_exp:
                return {
                    'field': 'gcp_training_capability',
                    'value': 'Yes - GCP training capability and multi-phase experience',
                    'confidence': 0.85,
                    'reasoning': 'Training capability and extensive clinical trial experience'
                }

        # Protocol compliance questions
        if re.search(r'(protocol.*compliance|ensure.*compliance|regulatory.*compliance)', q_lower):
            edc_exp = self._get_nested_value(site_profile, 'operational_metrics.edc_experience')
            phase_exp = self._get_nested_value(site_profile, 'experience_history.phase_experience')
            if edc_exp and phase_exp:
                phases = ', '.join(phase_exp) if isinstance(phase_exp, list) else str(phase_exp)
                return {
                    'field': 'protocol_compliance_capability',
                    'value': f'Yes - EDC experience and {phases} trial experience',
                    'confidence': 0.9,
                    'reasoning': 'EDC systems experience and multi-phase clinical trial background'
                }

        # Pharmacy questions
        if re.search(r'(research.*pharmacy|dedicated.*pharmacy|pharmacy.*available)', q_lower):
            equipment = self._get_nested_value(site_profile, 'procedures_equipment.special_equipment')
            # Check if any equipment suggests pharmacy capability
            if equipment and any('pharma' in str(item).lower() or 'drug' in str(item).lower() for item in equipment):
                return {
                    'field': 'pharmacy_capability',
                    'value': 'Yes - Pharmacy capabilities available',
                    'confidence': 0.8,
                    'reasoning': 'Pharmacy-related equipment found'
                }
            else:
                # Assume research sites have basic pharmacy capability
                return {
                    'field': 'pharmacy_capability',
                    'value': 'Likely - Standard research site pharmacy protocols',
                    'confidence': 0.6,
                    'reasoning': 'Standard research site assumption for pharmacy capability'
                }

        # Patient access questions (fix the wrong mapping)
        if re.search(r'(access.*patient.*population|access.*required.*patient)', q_lower):
            annual_volume = self._get_nested_value(site_profile, 'population_capabilities.annual_patient_volume')
            recruitment_sources = self._get_nested_value(site_profile, 'population_capabilities.recruitment_sources')
            if annual_volume and annual_volume > 1000:
                sources = ', '.join(recruitment_sources) if recruitment_sources else 'multiple sources'
                return {
                    'field': 'patient_access_capability',
                    'value': f'Yes - {annual_volume:,} patients/year via {sources}',
                    'confidence': 0.9,
                    'reasoning': 'High annual patient volume and multiple recruitment sources'
                }

        # Data management questions
        if re.search(r'(data.*management|electronic.*data|edc)', q_lower):
            edc_exp = self._get_nested_value(site_profile, 'operational_metrics.edc_experience')
            if edc_exp:
                return {
                    'field': 'data_management_capability',
                    'value': 'Yes - EDC experience available',
                    'confidence': 0.9,
                    'reasoning': 'Electronic data capture experience confirmed'
                }

        return None

    def _simple_keyword_mapping(self, question_text: str, site_profile: Dict) -> Optional[Dict]:
        """
        Simple, reliable keyword-based mapping that matches question meaning to appropriate data types
        """
        q_lower = question_text.lower()

        # AGE-specific questions (highest priority - must be specific)
        if any(phrase in q_lower for phrase in ['population age', 'age range', 'age criteria', 'participant age']):
            # Look for age range data
            min_age = self._get_nested_value(site_profile, 'population_capabilities.patient_age_range_min')
            max_age = self._get_nested_value(site_profile, 'population_capabilities.patient_age_range_max')
            if min_age and max_age:
                return {
                    'field': 'patient_age_range',
                    'value': f"{min_age}-{max_age} years",
                    'confidence': 0.9,
                    'reasoning': 'Mapped to patient age range'
                }
            # Fallback to common clinical age ranges
            return {
                'field': 'patient_age_range',
                'value': "18-75 years (standard adult range)",
                'confidence': 0.6,
                'reasoning': 'Standard adult clinical trial age range'
            }

        # ENROLLMENT NUMBER questions (specific numeric questions)
        if any(phrase in q_lower for phrase in ['number of participants', 'participants expected to enroll', 'enrollment target', 'how many participants']):
            # Return enrollment capacity, not patient volume
            enrollment_capacity = self._get_nested_value(site_profile, 'population_capabilities.enrollment_capacity_per_month')
            if enrollment_capacity and enrollment_capacity > 0:
                return {
                    'field': 'enrollment_capacity',
                    'value': f"{enrollment_capacity} patients per month",
                    'confidence': 0.8,
                    'reasoning': 'Mapped to enrollment capacity'
                }
            # Fallback to estimated enrollment based on volume
            volume = self._get_nested_value(site_profile, 'population_capabilities.annual_patient_volume')
            if volume and volume > 0:
                estimated_enrollment = min(100, volume // 50)  # Conservative estimate
                return {
                    'field': 'estimated_enrollment',
                    'value': f"~{estimated_enrollment} patients (estimated)",
                    'confidence': 0.6,
                    'reasoning': 'Estimated from annual patient volume'
                }

        # EQUIPMENT questions (only for equipment-specific terms)
        if any(phrase in q_lower for phrase in ['special equipment', 'equipment required', 'imaging equipment', 'mri', 'ct scanner']):
            equipment = self._get_nested_value(site_profile, 'procedures_equipment.special_equipment')
            if equipment and isinstance(equipment, list) and len(equipment) > 0:
                if len(equipment) > 3:
                    value = f"{', '.join(equipment[:3])}, and {len(equipment)-3} more"
                else:
                    value = ', '.join(equipment)
                return {
                    'field': 'special_equipment',
                    'value': value,
                    'confidence': 0.8,
                    'reasoning': 'Mapped to special equipment list'
                }

        # RESEARCH COORDINATORS (specific to coordinator roles)
        if any(phrase in q_lower for phrase in ['research coordinator', 'coordinators available', 'coordinator fte']):
            coordinators_fte = self._get_nested_value(site_profile, 'staff_resources.coordinators_fte')
            if coordinators_fte and coordinators_fte > 0:
                return {
                    'field': 'coordinators_fte',
                    'value': f"{coordinators_fte} FTE",
                    'confidence': 0.9,
                    'reasoning': 'Mapped to research coordinator FTE'
                }

        # GENERAL STAFF questions (broader staff questions)
        if any(phrase in q_lower for phrase in ['adequate staff', 'research staff', 'personnel', 'staff support']):
            total_staff = self._get_nested_value(site_profile, 'staff_resources.total_research_staff')
            if total_staff and total_staff > 0:
                return {
                    'field': 'total_research_staff',
                    'value': f"{total_staff} research staff",
                    'confidence': 0.8,
                    'reasoning': 'Mapped to total research staff count'
                }

        # POPULATION ACCESS questions (patient availability, not specific numbers)
        if any(phrase in q_lower for phrase in ['access to participant population', 'access to population', 'patient population available']):
            volume = self._get_nested_value(site_profile, 'population_capabilities.annual_patient_volume')
            if volume and volume > 0:
                return {
                    'field': 'annual_patient_volume',
                    'value': f"Yes - {volume:,} patients/year available",
                    'confidence': 0.9,
                    'reasoning': 'Mapped to annual patient volume for access question'
                }

        # GENERAL POPULATION questions (catch remaining population questions)
        if any(word in q_lower for word in ['population', 'participant']):
            volume = self._get_nested_value(site_profile, 'population_capabilities.annual_patient_volume')
            if volume and volume > 0:
                return {
                    'field': 'annual_patient_volume',
                    'value': f"{volume:,} patients/year",
                    'confidence': 0.7,
                    'reasoning': 'General population question mapped to patient volume'
                }

        # LABORATORY capabilities
        if any(phrase in q_lower for phrase in ['laboratory capabilities', 'lab capabilities', 'pk sampling', 'blood sampling']):
            lab_caps = self._get_nested_value(site_profile, 'laboratory_capabilities')
            if lab_caps and isinstance(lab_caps, dict):
                if lab_caps.get('pk_sampling'):
                    return {
                        'field': 'pk_sampling',
                        'value': 'Yes - PK sampling available',
                        'confidence': 0.9,
                        'reasoning': 'Site has PK sampling capabilities'
                    }
                elif any(lab_caps.values()):
                    return {
                        'field': 'laboratory_capabilities',
                        'value': 'Yes - laboratory capabilities available',
                        'confidence': 0.7,
                        'reasoning': 'Site has general laboratory capabilities'
                    }

        # EXPERIENCE questions
        if any(phrase in q_lower for phrase in ['experience with sponsor', 'previous sponsors', 'sponsor experience']):
            sponsors = self._get_nested_value(site_profile, 'experience_history.previous_sponsors')
            if sponsors and isinstance(sponsors, list) and len(sponsors) > 0:
                return {
                    'field': 'previous_sponsors',
                    'value': f"Yes - worked with {len(sponsors)} sponsors",
                    'confidence': 0.8,
                    'reasoning': f'Site has experience with {len(sponsors)} previous sponsors'
                }

        # THERAPEUTIC AREAS
        if any(phrase in q_lower for phrase in ['therapeutic areas', 'disease areas', 'therapeutic expertise']):
            areas = self._get_nested_value(site_profile, 'experience_history.therapeutic_areas')
            if areas and isinstance(areas, list) and len(areas) > 0:
                if len(areas) > 3:
                    value = f"Yes - {', '.join(areas[:3])}, and {len(areas)-3} more areas"
                else:
                    value = f"Yes - {', '.join(areas)}"
                return {
                    'field': 'therapeutic_areas',
                    'value': value,
                    'confidence': 0.8,
                    'reasoning': 'Mapped to therapeutic area experience'
                }

        return None

    def _get_nested_value(self, data: Dict, field_path: str) -> Any:
        """
        Get value from nested dictionary using dot notation or direct field access
        """
        # Try direct field access first
        if field_path in data:
            return data[field_path]

        # Try nested access for structured profile
        path_parts = field_path.split('.')
        current = data

        for part in path_parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Try common profile structure patterns
                profile_sections = [
                    'basic_info', 'population_capabilities', 'procedures_equipment',
                    'staff_resources', 'operational_metrics', 'experience_history'
                ]

                for section in profile_sections:
                    if section in data and part in data[section]:
                        return data[section][part]

                return None

        return current

    def _calculate_confidence(self, question_text: str, field_path: str, pattern: str, value: Any) -> float:
        """
        Calculate confidence score for a mapping
        """
        base_confidence = 0.7

        # Boost confidence for exact keyword matches
        exact_matches = [
            ('staff', 'staff'),
            ('equipment', 'equipment'),
            ('patient', 'patient'),
            ('volume', 'volume'),
            ('experience', 'experience'),
            ('sponsor', 'sponsor'),
        ]

        for q_keyword, f_keyword in exact_matches:
            if q_keyword in question_text and f_keyword in field_path:
                base_confidence += 0.1

        # Boost confidence if value is substantial/meaningful
        if isinstance(value, (int, float)) and value > 0:
            base_confidence += 0.1
        elif isinstance(value, list) and len(value) > 0:
            base_confidence += 0.1
        elif isinstance(value, str) and len(value) > 5:
            base_confidence += 0.1
        elif isinstance(value, bool) and value:
            base_confidence += 0.1

        # Reduce confidence for very generic matches
        if any(generic in pattern for generic in ['.*', '.+', '.?']):
            base_confidence -= 0.1

        return min(0.95, max(0.5, base_confidence))

    def _format_value_for_question(self, value: Any, question_text: str) -> str:
        """
        Format site profile value appropriately for the question context
        """
        if value is None:
            return "Information not available"

        # Boolean questions
        if isinstance(value, bool):
            return "Yes" if value else "No"

        # Numeric questions
        if isinstance(value, (int, float)):
            if 'volume' in question_text.lower() or 'patients' in question_text.lower():
                return f"{value:,} patients/year"
            elif 'staff' in question_text.lower() or 'fte' in question_text.lower():
                return f"{value} FTE" if isinstance(value, float) else f"{value} staff members"
            else:
                return str(value)

        # List values
        if isinstance(value, list):
            if len(value) == 0:
                return "None available"
            elif len(value) <= 3:
                return ", ".join(str(v) for v in value)
            else:
                return f"{', '.join(str(v) for v in value[:3])}, and {len(value) - 3} more"

        # String values
        return str(value)

    def _fuzzy_match_fields(self, question_id: str, question_text: str, site_profile: Dict) -> Optional[QuestionMapping]:
        """
        Use fuzzy string matching as fallback for mapping
        """
        best_match = None
        best_score = 0.0

        # Extract key words from question
        question_words = re.findall(r'\b\w+\b', question_text.lower())
        question_words = [w for w in question_words if len(w) > 3]  # Filter short words

        # Check all profile fields
        for field_path, value in self._flatten_profile(site_profile).items():
            if value is None:
                continue

            # Calculate similarity between question words and field name
            field_words = re.findall(r'\b\w+\b', field_path.lower())

            similarity = 0.0
            for q_word in question_words:
                for f_word in field_words:
                    word_similarity = SequenceMatcher(None, q_word, f_word).ratio()
                    similarity = max(similarity, word_similarity)

            if similarity > best_score and similarity > 0.6:  # Minimum threshold
                best_score = similarity
                best_match = QuestionMapping(
                    question_id=question_id,
                    question_text=question_text,
                    mapped_field=field_path,
                    mapped_value=self._format_value_for_question(value, question_text),
                    confidence_score=similarity * 0.8,  # Reduce confidence for fuzzy matches
                    source='site_profile',
                    reasoning=f"Fuzzy match with similarity {similarity:.2f}"
                )

        return best_match

    def _flatten_profile(self, profile: Dict, prefix: str = '') -> Dict[str, Any]:
        """
        Flatten nested profile structure for easier searching
        """
        flat = {}

        for key, value in profile.items():
            new_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flat.update(self._flatten_profile(value, new_key))
            else:
                flat[new_key] = value

        return flat

    def generate_autofill_responses(
        self,
        mappings: List[QuestionMapping],
        all_questions: List[Dict],
        site_profile: Dict = None
    ) -> List[Dict]:
        """
        Generate autofilled responses for mapped questions
        """
        responses = []

        # Create mapping lookup
        mapping_lookup = {m.question_id: m for m in mappings}

        for question in all_questions:
            question_id = question.get('id', '')

            if question_id in mapping_lookup:
                mapping = mapping_lookup[question_id]
                response = {
                    **question,
                    'response': mapping.mapped_value,
                    'source': mapping.source,
                    'confidence': mapping.confidence_score,
                    'manually_edited': False,
                    'reasoning': mapping.reasoning
                }
            else:
                # No complex mapping found - try simple keyword mapping as fallback
                response = dict(question)  # Copy question data

                # Try the same simple mapping logic used in autofill engine
                simple_mapping = self._simple_keyword_mapping(question.get('text', ''), site_profile or {})
                if simple_mapping:
                    response.update({
                        'response': simple_mapping['value'],
                        'source': 'site_profile_fallback',
                        'confidence': simple_mapping['confidence'],
                        'manually_edited': False,
                        'reasoning': simple_mapping['reasoning']
                    })
                else:
                    # No mapping found at all - mark as manual required
                    response.update({
                        'response': '',
                        'source': 'manual_required',
                        'confidence': 0.0,
                        'manually_edited': False,
                        'reasoning': 'No suitable site profile data found'
                    })

            responses.append(response)

        return responses

    def get_mapping_statistics(self, mappings: List[QuestionMapping]) -> Dict[str, Any]:
        """
        Generate statistics about the mapping results
        """
        if not mappings:
            return {
                "total_mappings": 0,
                "average_confidence": 0.0,
                "high_confidence_count": 0,
                "medium_confidence_count": 0,
                "low_confidence_count": 0
            }

        confidences = [m.confidence_score for m in mappings]
        avg_confidence = sum(confidences) / len(confidences)

        high_conf = sum(1 for c in confidences if c >= 0.8)
        medium_conf = sum(1 for c in confidences if 0.6 <= c < 0.8)
        low_conf = sum(1 for c in confidences if c < 0.6)

        return {
            "total_mappings": len(mappings),
            "average_confidence": round(avg_confidence, 3),
            "high_confidence_count": high_conf,
            "medium_confidence_count": medium_conf,
            "low_confidence_count": low_conf,
            "confidence_distribution": {
                "high (≥80%)": high_conf,
                "medium (60-79%)": medium_conf,
                "low (<60%)": low_conf
            }
        }