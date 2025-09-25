import json
import PyPDF2
import io
import re
from typing import Dict, List, Any, Optional
from app.services.llm_provider import generate

class ProtocolDocumentProcessor:
    """Extract structured data from sponsor protocol PDFs"""

    def extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF with structure preservation"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                text_parts.append(f"\n--- PAGE {page_num + 1} ---\n{page_text}")
            return "\n".join(text_parts)
        except Exception as e:
            raise ValueError(f"Failed to extract PDF text: {e}")

    def extract_protocol_data(self, pdf_bytes: bytes) -> Dict[str, Any]:
        """Extract structured protocol data for feasibility assessment"""

        full_text = self.extract_text_from_pdf(pdf_bytes)
        text_sample = full_text[:8000]  # First 8000 chars for key info

        system_prompt = """You are a clinical research expert extracting protocol information for feasibility assessment.
        Be precise and only extract explicitly stated information. Return valid JSON."""

        user_prompt = f"""
        Extract protocol information from this clinical trial document:

        REQUIRED FIELDS:
        {{
            "protocol_title": "exact title",
            "protocol_number": "NCT ID or protocol number",
            "phase": "Phase I/II/III/IV/Device/Other",
            "sponsor": "sponsor/CRO name",
            "indication": "disease/condition being studied",
            "drug_administration": "PO/IV/SQ/IM/NA",
            "population_age": "age range from inclusion criteria",
            "expected_enrollment": "target enrollment number",
            "inclusion_criteria": ["list", "of", "key", "inclusion", "criteria"],
            "exclusion_criteria": ["list", "of", "key", "exclusion", "criteria"],
            "procedures": ["list", "of", "study", "procedures"],
            "equipment_required": ["required", "equipment", "list"],
            "pk_samples": "yes/no - PK sample collection",
            "pk_intensive": "yes/no - intensive PK sampling",
            "washout_period": "yes/no - washout required",
            "visit_frequency": "visit schedule description",
            "study_duration": "total study duration"
        }}

        DOCUMENT TEXT:
        {text_sample}

        Return only valid JSON. Use "unclear" for uncertain extractions.
        """

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]

            response = generate(messages, temperature=0.1, max_tokens=2000)
            extracted = json.loads(response)

            # Add confidence scoring
            extracted["extraction_confidence"] = self._calculate_confidence(extracted)
            return extracted

        except json.JSONDecodeError:
            return self._fallback_extraction(full_text)
        except Exception as e:
            return {"error": f"Extraction failed: {e}"}

    def _calculate_confidence(self, data: Dict[str, Any]) -> str:
        """Calculate extraction confidence level"""
        required_fields = ["protocol_title", "phase", "indication", "expected_enrollment"]
        successful_extractions = sum(1 for field in required_fields if data.get(field) and data[field] != "unclear")

        confidence_ratio = successful_extractions / len(required_fields)
        if confidence_ratio > 0.8:
            return "high"
        elif confidence_ratio > 0.5:
            return "medium"
        else:
            return "low"

    def _fallback_extraction(self, text: str) -> Dict[str, Any]:
        """Simple regex-based fallback extraction"""
        data = {"extraction_confidence": "low"}

        # Basic pattern matching
        nct_match = re.search(r'NCT\d{8}', text, re.IGNORECASE)
        if nct_match:
            data["protocol_number"] = nct_match.group()

        if "phase i" in text.lower():
            data["phase"] = "Phase I"
        elif "phase ii" in text.lower():
            data["phase"] = "Phase II"
        elif "phase iii" in text.lower():
            data["phase"] = "Phase III"
        elif "phase iv" in text.lower():
            data["phase"] = "Phase IV"

        return data