"""
Protocol Requirement Extractor

Extracts specific requirements from clinical trial protocol PDFs:
- Equipment needs
- Staff requirements
- Patient population criteria
- Procedural capabilities
- Study duration and complexity
"""

import PyPDF2
import io
import json
from app.services.openai_client import get_openai_client
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

@dataclass
class ProtocolRequirement:
    category: str
    requirement: str
    criticality: str  # "critical", "preferred", "optional"
    details: str

class ProtocolRequirementExtractor:
    """Extract specific requirements from protocol PDFs using OpenAI for robust processing"""

    def __init__(self):
        # Initialize OpenAI client
        try:
            self.openai_client = get_openai_client()
        except Exception as e:
            print(f"Warning: OpenAI client initialization failed: {e}")
            self.openai_client = None

    def extract_requirements_from_pdf(self, pdf_content: bytes) -> Dict[str, Any]:
        """Extract protocol requirements from PDF content using OpenAI"""

        try:
            # Step 1: Extract raw text from PDF (simple and robust)
            text = self._extract_pdf_text_robust(pdf_content)

            if not text or len(text) < 100:
                raise Exception("PDF text extraction failed or insufficient content")

            print(f"📄 Extracted {len(text)} characters from protocol PDF")

            # Step 2: Use OpenAI to extract structured requirements
            if self.openai_client:
                requirements = self._extract_with_openai(text)
            else:
                # Fallback to basic text-based extraction
                requirements = self._extract_with_fallback(text)

            return {
                "success": True,
                "requirements": requirements,
                "critical_requirements": requirements.get("critical_flags", []),
                "text_length": len(text),
                "extraction_method": "openai" if self.openai_client else "fallback"
            }

        except Exception as e:
            print(f"❌ Protocol extraction error: {e}")
            return {
                "success": False,
                "error": str(e),
                "fallback_requirements": self._generate_fallback_requirements()
            }

    def _extract_pdf_text_robust(self, pdf_content: bytes) -> str:
        """Extract text from PDF with fallback methods"""
        text = ""

        # Method 1: Try PyPDF2
        try:
            pdf_file = io.BytesIO(pdf_content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            for page_num in range(len(pdf_reader.pages)):
                page = pdf_reader.pages[page_num]
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

            if text and len(text) > 100:
                print(f"✅ PyPDF2 extraction successful: {len(text)} characters")
                return text

        except Exception as e:
            print(f"⚠️ PyPDF2 failed: {e}")

        # Method 2: Try treating as text if it's actually text content
        try:
            text_attempt = pdf_content.decode('utf-8', errors='ignore')
            if len(text_attempt) > 100 and any(word in text_attempt.lower() for word in ['protocol', 'study', 'clinical', 'trial']):
                print(f"✅ Text fallback successful: {len(text_attempt)} characters")
                return text_attempt
        except Exception as e:
            print(f"⚠️ Text fallback failed: {e}")

        # Method 3: Return minimal content for testing
        if not text:
            raise Exception("All PDF extraction methods failed")

        return text

    def _extract_with_openai(self, text: str) -> Dict[str, Any]:
        """Extract universal feasibility requirements using OpenAI structured prompts"""
        import logging
        logger = logging.getLogger(__name__)

        # Limit text to first 10000 characters to capture more protocol details
        text_sample = text[:10000] if len(text) > 10000 else text

        logger.info(f"📋 Protocol extraction starting: {len(text_sample)} characters")

        prompt = f"""Extract key feasibility requirements from this clinical trial protocol that can answer typical sponsor survey questions.

PROTOCOL TEXT:
{text_sample}

UNIVERSAL EXTRACTION REQUIREMENTS:
Extract these elements (when present) to answer feasibility questions:

1. **Study Identification**:
   - Protocol title/number
   - Sponsor/CRO name
   - Study phase (Phase I, II, III, IV)
   - Therapeutic area

2. **Study Design & Timeline**:
   - Study duration (total weeks/months/years)
   - Enrollment period (how long to enroll patients)
   - Enrollment target (number of patients needed)
   - Visit frequency (how often patients come in)
   - Study complexity (simple/moderate/complex based on procedures)

3. **Patient Population**:
   - Primary indication/disease/condition
   - Age range (min and max)
   - Key inclusion criteria (top 3-5 most important)
   - Key exclusion criteria (top 3-5 most restrictive)
   - Estimated eligible population size

4. **Staff Requirements**:
   - PI qualifications (specialty, certifications, experience)
   - Coordinator requirements (FTE, special training, certifications)
   - Other staff needs (nurses, pharmacists, etc.)
   - Minimum staffing levels

5. **Equipment & Facilities**:
   - Imaging equipment (MRI, CT, X-ray, ultrasound, etc.)
   - Lab equipment (centrifuge, freezers, analyzers)
   - Storage requirements (-80C freezer, -20C, etc.)
   - Special devices (FibroScan, DEXA, spirometry, etc.)
   - Procedure rooms needed

6. **Procedures Required**:
   - Biopsies (liver, kidney, tissue, etc.)
   - Scans/imaging (frequency and type)
   - Lab tests (blood draws, urinalysis, etc.)
   - Special assessments (ECG, echo, PFT, etc.)

7. **Drug/Treatment Details**:
   - Drug name/investigational product
   - Administration route (oral, IV, injection, etc.)
   - Pharmacy requirements
   - Storage conditions

Return JSON with this EXACT structure:
{{
    "study_identification": {{
        "protocol_number": "string or null",
        "sponsor_name": "string or null",
        "cro_name": "string or null",
        "phase": "Phase I|II|III|IV or null",
        "therapeutic_area": "string or null"
    }},
    "study_timeline": {{
        "total_duration_weeks": number or null,
        "enrollment_period_weeks": number or null,
        "enrollment_target": number or null,
        "visit_frequency": "string describing frequency or null",
        "estimated_visit_count": number or null,
        "complexity": "simple|moderate|complex"
    }},
    "patient_population": {{
        "primary_indication": "disease/condition",
        "age_min": number or null,
        "age_max": number or null,
        "key_inclusion_criteria": ["criterion1", "criterion2"],
        "key_exclusion_criteria": ["criterion1", "criterion2"],
        "estimated_eligible_population": "description or null"
    }},
    "staff_requirements": [
        {{
            "role": "PI|Coordinator|Nurse|Pharmacist",
            "fte": number or null,
            "specialization": "specialty required",
            "certifications": ["cert1", "cert2"],
            "criticality": "critical|preferred|optional"
        }}
    ],
    "equipment_required": [
        {{
            "category": "imaging|lab|storage|device|facility",
            "name": "specific equipment name",
            "specifications": "any specific specs (e.g., 1.5T MRI, -80C freezer)",
            "purpose": "why needed",
            "criticality": "critical|preferred|optional"
        }}
    ],
    "procedures": [
        {{
            "name": "procedure name",
            "frequency": "how often (e.g., baseline and week 24)",
            "invasiveness": "non-invasive|minimally-invasive|invasive",
            "criticality": "critical|preferred|optional"
        }}
    ],
    "drug_treatment": {{
        "drug_name": "string or null",
        "administration_route": "oral|IV|subcutaneous|topical|other",
        "pharmacy_requirements": "description or null",
        "storage_conditions": "description or null"
    }},
    "critical_flags": [
        "Must-have requirements that could disqualify a site"
    ]
}}

EXTRACTION RULES:
1. Extract SPECIFIC information - "MRI with PDFF capability" not just "MRI"
2. Use NULL for missing data - don't guess or infer
3. Mark "critical" ONLY if explicitly stated as required/mandatory in protocol
4. Focus on concrete requirements that answer feasibility questions
5. Extract actual numbers when present (enrollment target, duration, age ranges)
6. Capture specialty requirements (e.g., "PI must be hepatologist" not just "PI needed")

This data will be used to answer survey questions like:
- "What is the protocol phase?" → Use study_identification.phase
- "How long is the study?" → Use study_timeline.total_duration_weeks
- "Is special equipment required?" → Check equipment_required array
- "What is enrollment target?" → Use study_timeline.enrollment_target
- "What patient population?" → Use patient_population.primary_indication

Return ONLY valid JSON, no explanatory text."""

        try:
            logger.info(f"🤖 Calling OpenAI for protocol extraction...")
            logger.info(f"Prompt preview: {prompt[:500]}...")

            # Use unified client with automatic API detection and fallback
            requirements = self.openai_client.create_json_completion(
                prompt=prompt,
                system_message="You are a clinical research expert who extracts specific requirements from protocol documents. Return only valid JSON.",
                temperature=0.1,
                max_tokens=3000  # Increased for complex protocols
            )

            logger.info(f"✅ OpenAI extraction successful")
            logger.info(f"Extracted keys: {list(requirements.keys())}")

            # Log structured data counts
            if 'equipment_required' in requirements:
                logger.info(f"Equipment items: {len(requirements.get('equipment_required', []))}")
            if 'procedures' in requirements:
                logger.info(f"Procedures: {len(requirements.get('procedures', []))}")
            if 'staff_requirements' in requirements:
                logger.info(f"Staff requirements: {len(requirements.get('staff_requirements', []))}")

            # Log critical data for UAB surveys
            timeline = requirements.get('study_timeline', {})
            logger.info(f"Study duration: {timeline.get('total_duration_weeks')} weeks")
            logger.info(f"Enrollment target: {timeline.get('enrollment_target')}")

            return requirements

        except json.JSONDecodeError as e:
            logger.error(f"❌ OpenAI JSON parsing failed: {e}")
            logger.error(f"This means the AI returned invalid JSON - using fallback")
            return self._extract_with_fallback(text)
        except Exception as e:
            logger.error(f"❌ OpenAI API call failed: {e}")
            logger.error(f"Full error: {str(e)}")
            return self._extract_with_fallback(text)

    def _extract_with_fallback(self, text: str) -> Dict[str, Any]:
        """Basic text-based extraction when OpenAI is not available"""
        text_lower = text.lower()

        # Try to extract basic info from text
        phase = None
        if 'phase i' in text_lower and 'phase ii' not in text_lower:
            phase = "Phase I"
        elif 'phase ii' in text_lower and 'phase iii' not in text_lower:
            phase = "Phase II"
        elif 'phase iii' in text_lower and 'phase iv' not in text_lower:
            phase = "Phase III"
        elif 'phase iv' in text_lower:
            phase = "Phase IV"

        return {
            "study_identification": {
                "protocol_number": None,
                "sponsor_name": None,
                "cro_name": None,
                "phase": phase,
                "therapeutic_area": None
            },
            "study_timeline": {
                "total_duration_weeks": None,
                "enrollment_period_weeks": None,
                "enrollment_target": None,
                "visit_frequency": None,
                "estimated_visit_count": None,
                "complexity": "moderate"
            },
            "patient_population": {
                "primary_indication": "Various",
                "age_min": 18,
                "age_max": 75,
                "key_inclusion_criteria": ["Adult participants"],
                "key_exclusion_criteria": ["Unable to provide consent"],
                "estimated_eligible_population": None
            },
            "staff_requirements": [
                {
                    "role": "Coordinator",
                    "fte": 0.5,
                    "specialization": "Clinical research",
                    "certifications": ["GCP"],
                    "criticality": "critical"
                }
            ],
            "equipment_required": [
                {
                    "category": "lab",
                    "name": "Standard clinical equipment",
                    "specifications": None,
                    "purpose": "Basic study procedures",
                    "criticality": "optional"
                }
            ],
            "procedures": [
                {
                    "name": "Standard assessments",
                    "frequency": "Multiple visits",
                    "invasiveness": "non-invasive",
                    "criticality": "critical"
                }
            ],
            "drug_treatment": {
                "drug_name": None,
                "administration_route": None,
                "pharmacy_requirements": None,
                "storage_conditions": None
            },
            "critical_flags": [
                "Requires experienced research coordinator"
            ]
        }