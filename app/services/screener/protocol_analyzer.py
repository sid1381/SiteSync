"""
Protocol Analyzer for SiteSync Screener.

Comprehensive protocol extraction aligned with SPIRIT 2013, ICH E6, and ICH M11 standards.
Extracts STRUCTURED FIELDS (not vague summaries) for sponsor/consultant feasibility decisions.

Uses CHUNKED EXTRACTION pipeline to handle long protocols (50-100+ pages).
This addresses the "lost in the middle" problem where LLMs miss facts scattered
across long documents. By extracting from smaller chunks and merging, we capture
35+/40 fields vs 8/40 with naive single-pass approaches.
"""

import re
import logging
from typing import Dict, Any, Optional, List

from app.services.protocol_requirement_extractor import ProtocolRequirementExtractor
from app.services.openai_client import get_openai_client, UnifiedOpenAIClient
from app.services.screener.data_sources.base import ProtocolCriteria
from app.services.screener.protocol_extractor import ScreenerProtocolExtractor

logger = logging.getLogger(__name__)

# Comprehensive extraction prompt for GPT-4o
SCREENER_EXTRACTION_PROMPT = """You are an expert clinical trial protocol analyst. Extract ALL of the following fields from this protocol document. Be SPECIFIC and DETAILED - do not summarize vaguely. Every field should contain the actual values from the protocol.

Extract as JSON:

{
  "study_title": "Full descriptive title of the study",
  "protocol_number": "Protocol identifier/number (e.g., CTJ301UC201)",
  "sponsor": "Sponsor company name",
  "phase": "Phase I/II/III/IV (use Roman numerals)",
  "therapeutic_area": "e.g., Gastroenterology, Oncology, Neurology, Cardiology",

  "design_type": "Full design description (e.g., randomized, double-blind, placebo-controlled, parallel-group, multicenter)",
  "arm_count": "number of treatment arms as integer",
  "arms_description": ["Arm 1 with dose details", "Arm 2 with dose details", "Placebo if applicable"],
  "allocation_ratio": "e.g., 1:1:1 or 2:1",
  "blinding": "Double-blind / Open-label / Single-blind",
  "control_type": "Placebo-controlled / Active-controlled / No control",

  "drug_name": "Investigational product name (generic or code name)",
  "drug_class": "Type of drug (e.g., monoclonal antibody, small molecule, biologic, gene therapy)",
  "dose_and_route": "All dose levels and route of administration (e.g., 300mg or 600mg IV, 10mg PO daily)",
  "dosing_frequency": "How often drug is administered (e.g., Q2W, once daily, twice daily)",
  "administration_duration": "Duration of each administration if applicable (e.g., 60-min infusion, 30-min injection)",

  "indication": "Primary disease/condition being studied",
  "indication_detail": "Specific severity/stage requirements (e.g., moderate-to-severe active UC with Mayo score ≥6)",
  "age_range": "Min-Max age as string (e.g., 18-75 years)",
  "age_min": "Minimum age as integer",
  "age_max": "Maximum age as integer",
  "sex_eligibility": "All / Male only / Female only",
  "enrollment_target": "Total target enrollment as integer",
  "patients_per_site": "Estimated patients per site as integer if mentioned",
  "target_countries": ["List of target countries if mentioned"],

  "inclusion_criteria": [
    "Specific criterion 1 - be detailed",
    "Specific criterion 2 - include numeric thresholds",
    "Specific criterion 3 - include diagnostic requirements",
    "..."
  ],
  "exclusion_criteria": [
    "Specific criterion 1 - be detailed",
    "Specific criterion 2 - include specific conditions",
    "..."
  ],

  "screening_period": "Duration of screening (e.g., Up to 4 weeks, 28 days)",
  "treatment_duration": "Duration of active treatment (e.g., 12 weeks, 52 weeks)",
  "follow_up_duration": "Duration of follow-up after treatment (e.g., 4 weeks safety follow-up)",
  "total_duration": "Total per-patient duration (e.g., ~20 weeks)",
  "total_visits": "Total number of study visits as integer",
  "visit_frequency": "How often visits occur (e.g., Every 2 weeks during treatment, weekly for first month)",

  "primary_endpoint": "Exact primary endpoint definition with timepoint (e.g., Clinical and endoscopic remission at Week 12)",
  "secondary_endpoints": ["Endpoint 1 with timepoint", "Endpoint 2", "..."],
  "primary_assessment": "Scale/instrument used (e.g., Mayo Score, RECIST 1.1, EORTC QLQ-C30)",

  "required_equipment": [
    "List ALL equipment/capabilities sites need",
    "Include: imaging equipment (MRI, CT, PET, ultrasound)",
    "Include: endoscopy equipment if applicable",
    "Include: infusion pumps, ECG machines",
    "Include: any specialized monitoring equipment"
  ],
  "required_staff": [
    "PI specialty requirement (e.g., Board-certified gastroenterologist)",
    "Sub-investigator requirements",
    "Certified study coordinator",
    "Specialized nurses (e.g., infusion nurse, oncology nurse)",
    "Pharmacist for investigational drug handling",
    "Any specialized technicians"
  ],
  "procedures": [
    "List EVERY procedure patients undergo",
    "Blood draws with specifics (hematology, chemistry, PK sampling)",
    "Imaging scans (specify type and frequency)",
    "Endoscopy/colonoscopy if applicable",
    "Biopsies if applicable",
    "ECG assessments",
    "Vital signs assessments",
    "Physical examinations",
    "Patient questionnaires/PROs"
  ],

  "requires_endoscopy": true/false,
  "requires_infusion": true/false,
  "requires_imaging": ["MRI", "CT", "PET", "ultrasound"] or [],
  "requires_biopsy": true/false,
  "storage_requirements": ["-20°C", "-80°C", "ambient"] as applicable,
  "sample_processing": ["centrifuge", "PK processing", "biomarker processing"],
  "lab_requirements": ["hematology", "chemistry", "urinalysis", "coagulation", "specific biomarkers"],
  "ecg_required": true/false,

  "dsmb_required": true/false,
  "safety_monitoring": "Description of safety oversight (e.g., Independent DSMB reviews after every 30 patients)"
}

CRITICAL EXTRACTION RULES:
1. For inclusion/exclusion criteria: List EACH criterion SEPARATELY. Do NOT combine them into one vague statement. Include ALL numeric thresholds (e.g., "Mayo score ≥6", "BMI 18-40 kg/m²").

2. For equipment: Think about what the SITE needs to run this trial successfully. Include ALL of:
   - Imaging equipment (MRI, CT, PET, ultrasound, X-ray, DXA)
   - Endoscopy/colonoscopy equipment
   - Infusion capability (pumps, chairs, monitoring)
   - ECG machines
   - Specimen processing equipment
   - Storage facilities (specify temperatures)

3. For staff: Include ALL roles needed:
   - PI with specialty requirement
   - Sub-investigators
   - Study coordinators (specify certification if mentioned)
   - Research nurses
   - Pharmacist
   - Lab technicians
   - Any specialized technicians

4. For procedures: List EVERY procedure a patient undergoes:
   - Blood draws (specify types: hematology, chemistry, PK, biomarkers)
   - Imaging (specify modality and frequency)
   - Endoscopy/colonoscopy
   - Biopsies (specify type)
   - ECG
   - Vital signs
   - Physical examinations
   - Patient questionnaires/PROs (specify which ones)

5. If information is NOT found in the protocol, use null for numbers, empty string "" for text, or empty array [] for lists. Do NOT make up values.

6. Be SPECIFIC. "Blood draws" is not enough - say "Blood draws for hematology, chemistry, PK sampling at Weeks 0, 2, 4, 8, 12".

7. For boolean fields (requires_endoscopy, requires_infusion, etc.), analyze the protocol procedures to determine if these capabilities are needed.

Return ONLY valid JSON."""


class ScreenerProtocolAnalyzer:
    """
    Analyzes protocol PDF and produces structured search criteria.

    Uses CHUNKED EXTRACTION pipeline for comprehensive field extraction:
    - Parses PDF into pages
    - Creates smart chunks (by section headings or fixed size)
    - Extracts fields from each chunk via GPT-4o
    - Merges best values across chunks
    - Gap-fills missing critical fields with targeted re-extraction

    This approach captures 35+/40 fields vs 8/40 with naive single-pass.
    """

    def __init__(self):
        # Primary extractor: new chunked pipeline for comprehensive extraction
        self.chunked_extractor = ScreenerProtocolExtractor()
        # Fallback extractor: original simple extractor
        self.basic_extractor = ProtocolRequirementExtractor()
        try:
            self.openai = get_openai_client()
        except Exception as e:
            logger.warning(f"OpenAI client not available: {e}")
            self.openai = None

    async def analyze_protocol(self, pdf_bytes: bytes) -> ProtocolCriteria:
        """
        Extract comprehensive protocol requirements as ProtocolCriteria.

        Uses chunked extraction pipeline:
        1. Parse PDF to text with page numbers
        2. Create smart chunks (by section headings)
        3. Extract fields from each chunk via GPT-4o
        4. Merge best values across chunks
        5. Gap-fill missing required fields
        6. Convert to ProtocolCriteria

        Args:
            pdf_bytes: Raw bytes of the protocol PDF

        Returns:
            ProtocolCriteria object with comprehensive fields for feasibility
        """
        logger.info("Starting CHUNKED protocol extraction for Screener")

        try:
            # Use the new chunked extraction pipeline
            extraction_result = await self.chunked_extractor.extract_from_pdf(pdf_bytes)

            # Convert ExtractionResult to ProtocolCriteria
            criteria = self._extraction_result_to_criteria(extraction_result)

            logger.info(
                f"Chunked extraction complete: indication='{criteria.indication}', "
                f"phase='{criteria.phase}', therapeutic_area='{criteria.therapeutic_area}', "
                f"confidence={criteria.extraction_confidence:.0%}, "
                f"pages={extraction_result.total_pages}, chunks={extraction_result.chunks_processed}"
            )

            return criteria

        except Exception as e:
            logger.error(f"Chunked extraction failed: {e}, falling back to basic extraction")
            return await self._fallback_extraction(pdf_bytes)

    def _extraction_result_to_criteria(self, result) -> ProtocolCriteria:
        """Convert ExtractionResult from chunked extractor to ProtocolCriteria."""
        return ProtocolCriteria(
            # Study Identity
            study_title=result.study_title,
            protocol_number=result.protocol_number,
            sponsor=result.sponsor,
            phase=result.phase,
            therapeutic_area=result.therapeutic_area,

            # Study Design
            design_type=result.design_type,
            arm_count=result.arm_count,
            arms_description=result.arms_description,
            allocation_ratio=result.allocation_ratio,
            blinding=result.blinding,
            control_type=result.control_type,

            # Investigational Product
            drug_name=result.drug_name,
            drug_class=result.drug_class,
            dose_and_route=result.dose_and_route,
            dosing_frequency=result.dosing_frequency,
            administration_duration=result.administration_duration,

            # Patient Population
            indication=result.indication,
            indication_detail=result.indication_detail,
            age_range=result.age_range,
            age_min=result.age_min,
            age_max=result.age_max,
            sex_eligibility=result.sex_eligibility,
            enrollment_target=result.enrollment_target,
            patients_per_site=result.patients_per_site,
            target_countries=result.target_countries,

            # Eligibility
            inclusion_criteria=result.inclusion_criteria,
            exclusion_criteria=result.exclusion_criteria,

            # Timeline
            screening_period=result.screening_period,
            treatment_duration=result.treatment_duration,
            follow_up_duration=result.follow_up_duration,
            total_duration=result.total_duration,
            duration=result.duration,
            duration_weeks=result.duration_weeks,
            total_visits=result.total_visits,
            visit_count=result.visit_count,
            visit_frequency=result.visit_frequency,

            # Endpoints
            primary_endpoint=result.primary_endpoint,
            secondary_endpoints=result.secondary_endpoints,
            primary_assessment=result.primary_assessment,

            # Site Requirements
            required_equipment=result.required_equipment,
            required_staff=result.required_staff,
            procedures=result.procedures,

            # Site Capability Flags
            requires_endoscopy=result.requires_endoscopy,
            requires_infusion=result.requires_infusion,
            requires_imaging=result.requires_imaging,
            requires_biopsy=result.requires_biopsy,
            storage_requirements=result.storage_requirements,
            sample_processing=result.sample_processing,
            lab_requirements=result.lab_requirements,
            ecg_required=result.ecg_required,

            # Safety
            dsmb_required=result.dsmb_required,
            safety_monitoring=result.safety_monitoring,

            # Metadata
            extraction_confidence=result.extraction_confidence / 100.0,  # Convert to 0-1
            extraction_warnings=result.extraction_warnings,
            raw_extraction=result.raw_extraction,
        )

    async def _fallback_extraction(self, pdf_bytes: bytes) -> ProtocolCriteria:
        """Fallback to basic extraction if chunked extraction fails."""
        logger.info("Using fallback basic extraction")

        extraction_result = self.basic_extractor.extract_requirements_from_pdf(pdf_bytes)

        if not extraction_result.get("success"):
            logger.error(f"Fallback extraction also failed: {extraction_result.get('error')}")
            return ProtocolCriteria(
                indication="",
                phase="",
                extraction_confidence=0.0,
                extraction_warnings=["Protocol extraction failed - manual entry required"],
                raw_extraction=extraction_result,
            )

        raw_requirements = extraction_result.get("requirements", {})
        raw_text = extraction_result.get("raw_text", "")
        logger.info(f"Fallback extraction complete: {list(raw_requirements.keys())}")

        # Try comprehensive extraction if OpenAI is available
        if self.openai:
            logger.info("Running comprehensive GPT-4o extraction on fallback...")
            criteria = await self._comprehensive_extraction(raw_text, raw_requirements)
        else:
            criteria = self._map_to_criteria(raw_requirements)
            criteria.extraction_warnings.append("AI extraction unavailable - limited data extracted")

        return criteria

    async def _comprehensive_extraction(
        self,
        raw_text: str,
        basic_extraction: Dict[str, Any]
    ) -> ProtocolCriteria:
        """
        Run comprehensive GPT-4o extraction for all SPIRIT/ICH M11 fields.

        Args:
            raw_text: Full protocol text
            basic_extraction: Results from basic extractor

        Returns:
            Fully populated ProtocolCriteria
        """
        # Prepare protocol text (limit to ~6000 tokens worth)
        protocol_text = raw_text[:20000] if raw_text else str(basic_extraction)[:10000]

        prompt = f"""{SCREENER_EXTRACTION_PROMPT}

PROTOCOL TEXT:
{protocol_text}

Extract all fields as JSON. Be comprehensive and specific."""

        try:
            response = self.openai.create_json_completion(
                prompt=prompt,
                system_message=(
                    "You are an expert clinical trial protocol analyst with deep knowledge of "
                    "SPIRIT 2013, ICH E6, and ICH M11 standards. Extract comprehensive, structured "
                    "data from protocols for site feasibility assessment. Be specific and detailed."
                ),
                temperature=0.1,
                max_tokens=4000,
            )

            if response:
                logger.info(f"GPT-4o extraction returned {len(response)} fields")
                return self._map_comprehensive_response(response, basic_extraction)
            else:
                logger.warning("GPT-4o returned empty response, falling back to basic")
                criteria = self._map_to_criteria(basic_extraction)
                criteria.extraction_warnings.append("AI extraction returned empty - using basic extraction")
                return criteria

        except Exception as e:
            logger.error(f"Comprehensive extraction failed: {e}")
            criteria = self._map_to_criteria(basic_extraction)
            criteria.extraction_warnings.append(f"AI extraction failed: {str(e)}")
            return criteria

    def _map_comprehensive_response(
        self,
        ai_response: Dict[str, Any],
        basic_extraction: Dict[str, Any]
    ) -> ProtocolCriteria:
        """Map GPT-4o comprehensive response to ProtocolCriteria."""

        def get_str(key: str, default: str = "") -> str:
            val = ai_response.get(key)
            return str(val) if val else default

        def get_int(key: str) -> Optional[int]:
            val = ai_response.get(key)
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def get_bool(key: str, default: bool = False) -> bool:
            val = ai_response.get(key)
            if val is None:
                return default
            return bool(val)

        def get_list(key: str) -> List[str]:
            val = ai_response.get(key)
            if not val:
                return []
            if isinstance(val, list):
                return [str(item) for item in val if item]
            return []

        # Calculate extraction confidence based on completeness
        critical_fields = [
            ai_response.get("indication"),
            ai_response.get("phase"),
            ai_response.get("design_type"),
            ai_response.get("drug_name"),
            ai_response.get("enrollment_target"),
            ai_response.get("primary_endpoint"),
        ]
        filled_critical = sum(1 for f in critical_fields if f)
        confidence = filled_critical / len(critical_fields)

        warnings = []
        if not ai_response.get("indication"):
            warnings.append("Primary indication not clearly identified")
        if not ai_response.get("inclusion_criteria"):
            warnings.append("Inclusion criteria not extracted")
        if not ai_response.get("required_equipment"):
            warnings.append("Equipment requirements not extracted")

        return ProtocolCriteria(
            # Study Identity
            study_title=get_str("study_title"),
            protocol_number=get_str("protocol_number"),
            sponsor=get_str("sponsor"),
            phase=get_str("phase"),
            therapeutic_area=get_str("therapeutic_area"),

            # Study Design
            design_type=get_str("design_type"),
            arm_count=get_int("arm_count"),
            arms_description=get_list("arms_description"),
            allocation_ratio=get_str("allocation_ratio"),
            blinding=get_str("blinding"),
            control_type=get_str("control_type"),

            # Investigational Product
            drug_name=get_str("drug_name"),
            drug_class=get_str("drug_class"),
            dose_and_route=get_str("dose_and_route"),
            dosing_frequency=get_str("dosing_frequency"),
            administration_duration=get_str("administration_duration"),

            # Patient Population
            indication=get_str("indication"),
            indication_detail=get_str("indication_detail"),
            age_range=get_str("age_range"),
            age_min=get_int("age_min"),
            age_max=get_int("age_max"),
            sex_eligibility=get_str("sex_eligibility"),
            enrollment_target=get_int("enrollment_target"),
            patients_per_site=get_int("patients_per_site"),
            target_countries=get_list("target_countries"),

            # Eligibility
            inclusion_criteria=get_list("inclusion_criteria"),
            exclusion_criteria=get_list("exclusion_criteria"),

            # Timeline
            screening_period=get_str("screening_period"),
            treatment_duration=get_str("treatment_duration"),
            follow_up_duration=get_str("follow_up_duration"),
            total_duration=get_str("total_duration"),
            duration=get_str("total_duration"),  # Legacy alias
            duration_weeks=get_int("duration_weeks"),
            total_visits=get_int("total_visits"),
            visit_count=get_int("total_visits"),  # Legacy alias
            visit_frequency=get_str("visit_frequency"),

            # Endpoints
            primary_endpoint=get_str("primary_endpoint"),
            secondary_endpoints=get_list("secondary_endpoints"),
            primary_assessment=get_str("primary_assessment"),

            # Site Requirements
            required_equipment=get_list("required_equipment"),
            required_staff=get_list("required_staff"),
            procedures=get_list("procedures"),

            # Site Capability Flags
            requires_endoscopy=get_bool("requires_endoscopy"),
            requires_infusion=get_bool("requires_infusion"),
            requires_imaging=get_list("requires_imaging"),
            requires_biopsy=get_bool("requires_biopsy"),
            storage_requirements=get_list("storage_requirements"),
            sample_processing=get_list("sample_processing"),
            lab_requirements=get_list("lab_requirements"),
            ecg_required=get_bool("ecg_required"),

            # Safety
            dsmb_required=get_bool("dsmb_required"),
            safety_monitoring=get_str("safety_monitoring"),

            # Metadata
            extraction_confidence=confidence,
            extraction_warnings=warnings,
            raw_extraction=basic_extraction,
        )

    def _map_to_criteria(self, raw: Dict[str, Any]) -> ProtocolCriteria:
        """Map raw extraction output to ProtocolCriteria."""
        # Study identification
        study_id = raw.get("study_identification", {})
        phase = study_id.get("phase", "")
        sponsor = study_id.get("sponsor_name", "") or study_id.get("cro_name", "")
        therapeutic_area = study_id.get("therapeutic_area", "")
        study_title = study_id.get("protocol_number", "")

        # Timeline
        timeline = raw.get("study_timeline", {})
        duration_weeks = timeline.get("total_duration_weeks")
        enrollment_target = timeline.get("enrollment_target")
        visit_count = timeline.get("estimated_visit_count")

        # Convert duration to string if present
        duration = ""
        if duration_weeks:
            if duration_weeks >= 52:
                years = duration_weeks / 52
                duration = f"{years:.1f} years" if years != int(years) else f"{int(years)} years"
            else:
                duration = f"{duration_weeks} weeks"

        # Patient population
        population = raw.get("patient_population", {})
        indication = self._extract_indication(raw)
        age_min = population.get("age_min")
        age_max = population.get("age_max")
        inclusion_criteria = population.get("key_inclusion_criteria", [])
        exclusion_criteria = population.get("key_exclusion_criteria", [])

        # Staff requirements
        staff_requirements = raw.get("staff_requirements", [])
        required_staff = []
        for staff in staff_requirements:
            if isinstance(staff, dict):
                role = staff.get("role", "")
                spec = staff.get("specialization", "")
                if role and spec:
                    required_staff.append(f"{role} ({spec})")
                elif role:
                    required_staff.append(role)
            elif isinstance(staff, str):
                required_staff.append(staff)

        # Equipment requirements
        equipment_list = raw.get("equipment_required", [])
        required_equipment = []
        for equip in equipment_list:
            if isinstance(equip, dict):
                name = equip.get("name", "")
                specs = equip.get("specifications", "")
                if name and specs:
                    required_equipment.append(f"{name} ({specs})")
                elif name:
                    required_equipment.append(name)
            elif isinstance(equip, str):
                required_equipment.append(equip)

        # Procedures
        procedures_list = raw.get("procedures", [])
        procedures = []
        for proc in procedures_list:
            if isinstance(proc, dict):
                name = proc.get("name", "")
                freq = proc.get("frequency", "")
                if name and freq:
                    procedures.append(f"{name} ({freq})")
                elif name:
                    procedures.append(name)
            elif isinstance(proc, str):
                procedures.append(proc)

        return ProtocolCriteria(
            indication=indication,
            therapeutic_area=therapeutic_area,
            phase=phase,
            sponsor=sponsor,
            enrollment_target=enrollment_target,
            duration=duration,
            duration_weeks=duration_weeks,
            inclusion_criteria=inclusion_criteria,
            exclusion_criteria=exclusion_criteria,
            required_equipment=required_equipment,
            required_staff=required_staff,
            procedures=procedures,
            visit_count=visit_count,
            study_title=study_title,
            age_min=age_min,
            age_max=age_max,
            raw_extraction=raw,
        )

    def _extract_indication(self, raw: Dict[str, Any]) -> str:
        """
        Extract primary indication from extraction output.

        Tries multiple fields to find the most specific indication.
        """
        population = raw.get("patient_population", {})
        study_id = raw.get("study_identification", {})

        # Try fields in order of specificity
        candidates = [
            population.get("primary_indication", ""),
            population.get("condition", ""),
            population.get("disease", ""),
            study_id.get("therapeutic_area", ""),
        ]

        for candidate in candidates:
            if candidate and len(candidate) >= 3:
                return candidate

        return ""

    async def _refine_with_ai(
        self,
        criteria: ProtocolCriteria,
        raw: Dict[str, Any]
    ) -> ProtocolCriteria:
        """
        Use GPT-4o to extract better search terms from raw extraction.

        Called when the initial extraction doesn't yield a clear indication.
        """
        if not self.openai:
            return criteria

        # Build context from raw extraction
        raw_str = str(raw)[:4000]  # Limit context size

        prompt = f"""Given this clinical trial protocol extraction, identify:

1. The PRIMARY disease indication - be specific (e.g., "NASH with liver fibrosis F2-F3" not just "liver disease")
2. The therapeutic area (e.g., "Hepatology", "Oncology", "Cardiology")
3. MeSH-compatible search terms that would find similar trials on ClinicalTrials.gov

Protocol extraction data:
{raw_str}

Return JSON with this structure:
{{
    "indication": "specific disease/condition name",
    "therapeutic_area": "medical specialty",
    "search_terms": ["term1", "term2", "term3"],
    "confidence": "high|medium|low"
}}

Focus on extracting a search term that will find relevant trials on ClinicalTrials.gov.
Return ONLY valid JSON."""

        try:
            response = self.openai.create_json_completion(
                prompt=prompt,
                system_message=(
                    "You are a clinical trial protocol analyst. "
                    "Extract specific, searchable disease indications from protocol data. "
                    "Return only valid JSON."
                ),
                temperature=0.1,
                max_tokens=500,
            )

            if response:
                # Update criteria with AI-refined values
                ai_indication = response.get("indication", "")
                ai_therapeutic = response.get("therapeutic_area", "")

                if ai_indication and len(ai_indication) > len(criteria.indication):
                    logger.info(f"AI refined indication: '{ai_indication}'")
                    criteria.indication = ai_indication

                if ai_therapeutic and not criteria.therapeutic_area:
                    criteria.therapeutic_area = ai_therapeutic

        except Exception as e:
            logger.error(f"AI refinement failed: {e}")

        return criteria

    def create_manual_criteria(
        self,
        indication: str,
        phase: str = "",
        therapeutic_area: str = "",
        enrollment_target: Optional[int] = None,
        **kwargs
    ) -> ProtocolCriteria:
        """
        Create ProtocolCriteria manually without PDF extraction.

        Useful for quick searches or testing.

        Args:
            indication: Primary disease/condition
            phase: Study phase (e.g., "Phase II")
            therapeutic_area: Medical specialty
            enrollment_target: Target enrollment number
            **kwargs: Additional ProtocolCriteria fields

        Returns:
            ProtocolCriteria object
        """
        return ProtocolCriteria(
            indication=indication,
            phase=phase,
            therapeutic_area=therapeutic_area,
            enrollment_target=enrollment_target,
            **kwargs
        )
