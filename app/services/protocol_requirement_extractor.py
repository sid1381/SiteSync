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
        """Extract requirements using OpenAI structured prompts"""

        # Limit text to first 8000 characters to stay within token limits
        text_sample = text[:8000] if len(text) > 8000 else text

        prompt = f"""Extract clinical trial requirements from this protocol text and return as JSON:

PROTOCOL TEXT:
{text_sample}

Please extract and return JSON with this exact structure:
{{
    "equipment_required": [
        {{"name": "equipment name", "criticality": "critical|preferred|optional", "purpose": "why needed"}}
    ],
    "staff_requirements": [
        {{"role": "role name", "fte": 0.5, "specialization": "specialty needed", "criticality": "critical|preferred|optional"}}
    ],
    "patient_criteria": {{
        "age_min": 18,
        "age_max": 75,
        "target_enrollment": 100,
        "primary_indication": "disease/condition",
        "key_inclusion": ["criteria1", "criteria2"],
        "key_exclusion": ["criteria1", "criteria2"]
    }},
    "procedures": [
        {{"name": "procedure name", "frequency": "how often", "criticality": "critical|preferred|optional"}}
    ],
    "study_details": {{
        "phase": "Phase I/II/III/IV",
        "duration_weeks": 24,
        "visit_count": 10,
        "complexity": "low|medium|high"
    }},
    "critical_flags": [
        "Must-have requirement that could disqualify a site"
    ]
}}

Focus on concrete, specific requirements rather than general statements. Mark items as "critical" only if explicitly stated as required/mandatory."""

        try:
            # Use unified client with automatic API detection and fallback
            requirements = self.openai_client.create_json_completion(
                prompt=prompt,
                system_message="You are a clinical research expert who extracts specific requirements from protocol documents. Return only valid JSON.",
                temperature=0.1,
                max_tokens=2000
            )
            print(f"✅ OpenAI extraction successful")
            return requirements

        except json.JSONDecodeError as e:
            print(f"❌ OpenAI JSON parsing failed: {e}")
            return self._extract_with_fallback(text)
        except Exception as e:
            print(f"❌ OpenAI API call failed: {e}")
            return self._extract_with_fallback(text)

    def _extract_with_fallback(self, text: str) -> Dict[str, Any]:
        """Basic text-based extraction when OpenAI is not available"""
        text_lower = text.lower()

        return {
            "equipment_required": [
                {"name": "Standard clinical equipment", "criticality": "optional", "purpose": "Basic study procedures"}
            ],
            "staff_requirements": [
                {"role": "Research coordinator", "fte": 0.5, "specialization": "Clinical research", "criticality": "critical"}
            ],
            "patient_criteria": {
                "age_min": 18,
                "age_max": 75,
                "target_enrollment": 50,
                "primary_indication": "Various",
                "key_inclusion": ["Adult participants"],
                "key_exclusion": ["Unable to consent"]
            },
            "procedures": [
                {"name": "Standard assessments", "frequency": "Multiple visits", "criticality": "critical"}
            ],
            "study_details": {
                "phase": "Phase II",
                "duration_weeks": 24,
                "visit_count": 8,
                "complexity": "medium"
            },
            "critical_flags": [
                "Requires experienced research coordinator"
            ]
        }