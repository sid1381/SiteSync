import json
from typing import Dict, Any
from app.services.llm_provider import LLMProvider
import PyPDF2
import io

class EnhancedProtocolExtractor:
    def __init__(self):
        self.llm = LLMProvider()

    def extract_comprehensive(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Extract comprehensive protocol information for survey autofilling"""

        # Extract text from PDF
        text = self._extract_pdf_text(pdf_bytes)

        # Use structured prompt for comprehensive extraction
        prompt = """
        Extract ALL relevant information from this clinical trial protocol that would be needed to complete a feasibility questionnaire. Be extremely thorough.

        Protocol text:
        {text}

        Extract the following information in JSON format:
        {{
            "study_identification": {{
                "protocol_title": "",
                "protocol_number": "",
                "nct_number": "",
                "phase": "",
                "sponsor": "",
                "cro": "",
                "indication": "",
                "study_type": ""
            }},
            "study_design": {{
                "duration": "",
                "number_of_visits": "",
                "visit_schedule": [],
                "randomization": "",
                "blinding": "",
                "control_type": "",
                "number_of_arms": "",
                "arm_descriptions": []
            }},
            "population": {{
                "target_enrollment": "",
                "age_range": {{
                    "min": "",
                    "max": ""
                }},
                "gender": "",
                "population_type": "",
                "key_inclusion_criteria": [],
                "key_exclusion_criteria": [],
                "washout_period": "",
                "concomitant_medications": {{
                    "allowed": [],
                    "prohibited": []
                }}
            }},
            "procedures": {{
                "screening_procedures": [],
                "treatment_procedures": [],
                "safety_assessments": [],
                "efficacy_assessments": [],
                "laboratory_tests": [],
                "imaging_requirements": [],
                "special_equipment": [],
                "pk_sampling": {{
                    "required": false,
                    "schedule": [],
                    "number_of_samples": ""
                }}
            }},
            "drug_administration": {{
                "route": "",
                "frequency": "",
                "duration": "",
                "dose_levels": [],
                "dose_escalation": false,
                "storage_requirements": "",
                "preparation_requirements": ""
            }},
            "regulatory": {{
                "gcp_compliant": true,
                "special_populations": [],
                "safety_reporting_requirements": "",
                "data_monitoring": ""
            }},
            "operational": {{
                "recruitment_period": "",
                "competitive_enrollment": false,
                "screen_failure_rate_assumption": "",
                "retention_requirements": "",
                "training_requirements": [],
                "certification_requirements": []
            }}
        }}

        Be thorough and extract actual values, not placeholders. If information is not found, use null.
        """

        response = self.llm.generate(
            messages=[
                {"role": "system", "content": "You are a clinical research expert extracting protocol information."},
                {"role": "user", "content": prompt.format(text=text[:15000])}  # Limit context
            ],
            temperature=0.1
        )

        try:
            extracted = json.loads(response)
            extracted["extraction_confidence"] = self._calculate_extraction_confidence(extracted)
            return extracted
        except json.JSONDecodeError:
            return self._fallback_extraction(text)

    def _calculate_extraction_confidence(self, data: Dict) -> float:
        """Calculate confidence based on completeness of extraction"""
        total_fields = 0
        filled_fields = 0

        def count_fields(obj, prefix=""):
            nonlocal total_fields, filled_fields
            if isinstance(obj, dict):
                for key, value in obj.items():
                    count_fields(value, f"{prefix}.{key}")
            elif isinstance(obj, list):
                total_fields += 1
                if len(obj) > 0:
                    filled_fields += 1
            else:
                total_fields += 1
                if obj is not None and obj != "" and obj != "null":
                    filled_fields += 1

        count_fields(data)
        return filled_fields / total_fields if total_fields > 0 else 0

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF"""
        pdf_file = io.BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)

        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text()

        return text

    def _fallback_extraction(self, text: str) -> Dict[str, Any]:
        """Fallback extraction using simpler methods"""
        # Simple keyword-based extraction as fallback
        fallback_data = {
            "study_identification": {
                "protocol_title": self._extract_title(text),
                "phase": self._extract_phase(text),
                "indication": self._extract_indication(text)
            },
            "extraction_confidence": 0.3
        }
        return fallback_data

    def _extract_title(self, text: str) -> str:
        """Extract protocol title using simple patterns"""
        lines = text.split('\n')
        for line in lines[:10]:  # Check first 10 lines
            if len(line.strip()) > 20 and 'protocol' not in line.lower():
                return line.strip()
        return None

    def _extract_phase(self, text: str) -> str:
        """Extract study phase using patterns"""
        import re
        phase_pattern = r'phase\s+(i{1,3}|1|2|3|4)'
        match = re.search(phase_pattern, text.lower())
        if match:
            return match.group(1).upper()
        return None

    def _extract_indication(self, text: str) -> str:
        """Extract indication using common medical terms"""
        medical_terms = [
            'cancer', 'diabetes', 'hypertension', 'alzheimer', 'depression',
            'arthritis', 'asthma', 'copd', 'heart failure', 'stroke'
        ]
        text_lower = text.lower()
        for term in medical_terms:
            if term in text_lower:
                return term.title()
        return None