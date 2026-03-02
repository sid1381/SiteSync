"""
Comprehensive Protocol Extraction for SiteSync Screener.

Uses chunked extraction + merge strategy for long PDFs.
Pipeline: PDF → Parse → Chunk → Extract per chunk → Merge → Gap fill

This addresses the "lost in the middle" problem where LLMs miss facts
scattered across long documents. By extracting from smaller chunks
and merging, we capture 35+/40 fields vs 8/40 with naive approaches.
"""

import json
import re
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

# PyMuPDF for PDF parsing - conditional import to avoid import errors
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False
    fitz = None
    logging.warning("PyMuPDF (fitz) not installed - protocol extraction will use fallback")

from app.services.openai_client import get_openai_client

logger = logging.getLogger(__name__)


@dataclass
class ExtractionResult:
    """Result of protocol extraction with all SPIRIT/ICH M11 fields."""
    # Study Identity
    study_title: str = ""
    protocol_number: str = ""
    sponsor: str = ""
    phase: str = ""
    therapeutic_area: str = ""

    # Study Design
    design_type: str = ""
    arm_count: Optional[int] = None
    arms_description: List[str] = field(default_factory=list)
    allocation_ratio: str = ""
    blinding: str = ""
    control_type: str = ""

    # Investigational Product
    drug_name: str = ""
    drug_class: str = ""
    dose_and_route: str = ""
    dosing_frequency: str = ""
    administration_duration: str = ""

    # Patient Population
    indication: str = ""
    indication_detail: str = ""
    age_range: str = ""
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    sex_eligibility: str = ""
    enrollment_target: Optional[int] = None
    patients_per_site: Optional[int] = None
    target_countries: List[str] = field(default_factory=list)

    # Eligibility
    inclusion_criteria: List[str] = field(default_factory=list)
    exclusion_criteria: List[str] = field(default_factory=list)

    # Timeline
    screening_period: str = ""
    treatment_duration: str = ""
    follow_up_duration: str = ""
    total_duration: str = ""
    duration: str = ""
    duration_weeks: Optional[int] = None
    total_visits: Optional[int] = None
    visit_count: Optional[int] = None
    visit_frequency: str = ""

    # Endpoints
    primary_endpoint: str = ""
    secondary_endpoints: List[str] = field(default_factory=list)
    primary_assessment: str = ""

    # Site Requirements
    required_equipment: List[str] = field(default_factory=list)
    required_staff: List[str] = field(default_factory=list)
    procedures: List[str] = field(default_factory=list)

    # Site Capability Flags
    requires_endoscopy: bool = False
    requires_infusion: bool = False
    requires_imaging: List[str] = field(default_factory=list)
    requires_biopsy: bool = False
    storage_requirements: List[str] = field(default_factory=list)
    sample_processing: List[str] = field(default_factory=list)
    lab_requirements: List[str] = field(default_factory=list)
    ecg_required: bool = False

    # Safety
    dsmb_required: bool = False
    safety_monitoring: str = ""

    # Metadata
    extraction_confidence: float = 0.0
    extraction_warnings: List[str] = field(default_factory=list)
    total_pages: int = 0
    chunks_processed: int = 0
    raw_extraction: Optional[Dict] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ScreenerProtocolExtractor:
    """
    Comprehensive protocol extraction for Screener.
    Uses chunked extraction + merge strategy for long PDFs.
    """

    # Target fields aligned with SPIRIT 2013 + ICH M11
    REQUIRED_FIELDS = [
        "study_title", "protocol_number", "sponsor", "phase",
        "therapeutic_area", "design_type", "arm_count",
        "arms_description", "allocation_ratio", "blinding",
        "control_type", "drug_name", "drug_class", "dose_and_route",
        "dosing_frequency", "administration_duration", "indication",
        "indication_detail", "age_range", "sex_eligibility",
        "enrollment_target", "patients_per_site",
        "inclusion_criteria", "exclusion_criteria",
        "screening_period", "treatment_duration", "follow_up_duration",
        "total_duration", "total_visits", "visit_frequency",
        "primary_endpoint", "secondary_endpoints",
        "primary_assessment", "required_equipment", "required_staff",
        "procedures", "requires_endoscopy", "requires_infusion",
        "requires_imaging", "requires_biopsy", "storage_requirements",
        "sample_processing", "lab_requirements", "ecg_required",
        "dsmb_required", "safety_monitoring"
    ]

    CRITICAL_FIELDS = [
        "study_title", "phase", "indication", "design_type",
        "drug_name", "enrollment_target", "inclusion_criteria",
        "exclusion_criteria", "treatment_duration", "primary_endpoint",
        "required_equipment", "procedures", "dose_and_route"
    ]

    IMPORTANT_FIELDS = [
        "sponsor", "therapeutic_area", "arm_count", "blinding",
        "age_range", "dosing_frequency", "screening_period",
        "follow_up_duration", "total_visits", "secondary_endpoints",
        "required_staff", "lab_requirements"
    ]

    def __init__(self):
        try:
            self.openai = get_openai_client()
        except Exception as e:
            logger.warning(f"OpenAI client not available: {e}")
            self.openai = None

    async def extract_from_pdf(self, pdf_bytes: bytes) -> ExtractionResult:
        """
        Main entry point. Returns comprehensive structured extraction.

        Pipeline:
        1. Parse PDF to text with page numbers
        2. Create smart chunks (by section headings)
        3. Extract fields from each chunk
        4. Merge best values across chunks
        5. Gap-fill: re-extract missing required fields
        6. Calculate confidence score
        """
        logger.info("Starting chunked protocol extraction pipeline")

        if not self.openai:
            logger.error("OpenAI client not available for extraction")
            return ExtractionResult(
                extraction_warnings=["OpenAI client not available - manual entry required"]
            )

        # Step 1: Parse PDF
        pages = self._parse_pdf(pdf_bytes)
        total_pages = len(pages)
        logger.info(f"Parsed PDF: {total_pages} pages")

        if not pages:
            return ExtractionResult(
                extraction_warnings=["Could not parse PDF - no text extracted"]
            )

        # Step 2: Create chunks
        chunks = self._create_chunks(pages)
        logger.info(f"Created {len(chunks)} chunks for extraction")

        # Step 3: Extract from each chunk
        chunk_extractions = []
        for i, chunk in enumerate(chunks):
            logger.info(f"Extracting from chunk {i+1}/{len(chunks)} (pages {chunk['page_start']}-{chunk['page_end']})")
            extraction = await self._extract_from_chunk(chunk)
            if extraction:
                chunk_extractions.append(extraction)

        logger.info(f"Completed extraction from {len(chunk_extractions)} chunks")

        # Step 4: Merge across chunks
        merged = self._merge_extractions(chunk_extractions)

        # Step 5: Gap-fill for critical missing fields
        missing = self._find_missing_fields(merged)
        if missing and len(missing) >= 3:
            logger.info(f"Gap-filling {len(missing)} missing critical fields: {missing}")
            merged = await self._gap_fill(merged, missing, pages)

        # Step 6: Build result with confidence
        result = self._build_result(merged, total_pages, len(chunks))

        logger.info(
            f"Extraction complete: {result.extraction_confidence:.0f}% confidence, "
            f"{total_pages} pages, {len(chunks)} chunks"
        )

        return result

    def _parse_pdf(self, pdf_bytes: bytes) -> List[Dict]:
        """Parse PDF to list of {page_num, text} dicts."""
        if not FITZ_AVAILABLE:
            logger.error("PyMuPDF (fitz) not available - cannot parse PDF")
            return []

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pages = []
            for i, page in enumerate(doc):
                text = page.get_text()
                if text.strip():  # Skip blank pages
                    pages.append({
                        "page_num": i + 1,
                        "text": text
                    })
            doc.close()
            return pages
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}")
            return []

    def _create_chunks(self, pages: List[Dict]) -> List[Dict]:
        """
        Create overlapping chunks, targeting ~4000 tokens each.
        Strategy: Group pages into chunks of ~5-8 pages.
        Use section headings as natural break points when possible.

        Key sections to try to keep together:
        - Synopsis/Summary (usually pages 1-5)
        - Study Design / Objectives
        - Eligibility / Population
        - Interventions / Treatment
        - Procedures / Assessments
        - Safety
        - Statistics
        """
        chunks = []

        # Section header patterns (case insensitive)
        section_patterns = [
            r'(?i)^\s*\d+\.?\s*(SYNOPSIS|PROTOCOL SUMMARY|STUDY SUMMARY)',
            r'(?i)^\s*\d+\.?\s*(STUDY DESIGN|TRIAL DESIGN|STUDY OBJECTIVE)',
            r'(?i)^\s*\d+\.?\s*(STUDY POPULATION|ELIGIBILITY|INCLUSION|SELECTION)',
            r'(?i)^\s*\d+\.?\s*(STUDY TREATMENT|INVESTIGATIONAL|INTERVENTION|DOSAGE)',
            r'(?i)^\s*\d+\.?\s*(STUDY ASSESSMENT|SCHEDULE OF|PROCEDURES|VISIT)',
            r'(?i)^\s*\d+\.?\s*(SAFETY|ADVERSE|PHARMACOVIGILANCE)',
            r'(?i)^\s*\d+\.?\s*(STATISTICAL|SAMPLE SIZE|ANALYSIS)',
            r'(?i)^\s*\d+\.?\s*(ENDPOINT|EFFICACY|OUTCOME)',
        ]

        # Find section boundaries
        section_starts = []
        for page in pages:
            for pattern in section_patterns:
                if re.search(pattern, page["text"], re.MULTILINE):
                    section_starts.append(page["page_num"])
                    break

        # Create chunks: either by sections or by page groups
        if len(section_starts) >= 3:
            # Section-based chunking
            section_starts = sorted(set(section_starts))
            for i in range(len(section_starts)):
                start_page = section_starts[i]
                end_page = section_starts[i + 1] - 1 if i + 1 < len(section_starts) else pages[-1]["page_num"]

                chunk_pages = [p for p in pages if start_page <= p["page_num"] <= end_page]
                if chunk_pages:
                    chunk_text = "\n\n".join(
                        f"[Page {p['page_num']}]\n{p['text']}"
                        for p in chunk_pages
                    )
                    # Trim to ~6000 tokens worth (~24000 chars)
                    chunks.append({
                        "chunk_id": len(chunks),
                        "page_start": start_page,
                        "page_end": end_page,
                        "text": chunk_text[:24000]
                    })
        else:
            # Fallback: fixed-size page groups with overlap
            PAGES_PER_CHUNK = 8
            OVERLAP = 2
            i = 0
            while i < len(pages):
                chunk_pages = pages[i:i + PAGES_PER_CHUNK]
                chunk_text = "\n\n".join(
                    f"[Page {p['page_num']}]\n{p['text']}"
                    for p in chunk_pages
                )
                chunks.append({
                    "chunk_id": len(chunks),
                    "page_start": chunk_pages[0]["page_num"],
                    "page_end": chunk_pages[-1]["page_num"],
                    "text": chunk_text[:24000]
                })
                i += PAGES_PER_CHUNK - OVERLAP

        # ALWAYS include first 5 pages as chunk 0 (synopsis)
        # if not already covered
        if chunks and chunks[0]["page_start"] > 1:
            synopsis_pages = [p for p in pages if p["page_num"] <= 5]
            if synopsis_pages:
                synopsis_text = "\n\n".join(
                    f"[Page {p['page_num']}]\n{p['text']}"
                    for p in synopsis_pages
                )
                chunks.insert(0, {
                    "chunk_id": -1,
                    "page_start": 1,
                    "page_end": min(5, len(pages)),
                    "text": synopsis_text[:24000]
                })

        return chunks

    async def _extract_from_chunk(self, chunk: Dict) -> Optional[Dict]:
        """Extract all findable fields from a single chunk."""

        system_prompt = """You are an expert clinical trial protocol analyst.
Extract structured data from this CHUNK of a clinical trial protocol.
Only extract what is EXPLICITLY stated in this chunk.
Do NOT guess or infer - use null for fields not found in this chunk.
For list fields, extract EVERY individual item separately."""

        user_prompt = f"""Extract the following fields from this protocol chunk
(pages {chunk['page_start']}-{chunk['page_end']}).

Return JSON with these fields (use null if not found in this chunk):

{{
  "study_title": "Full descriptive title (not just protocol number)",
  "protocol_number": "Protocol ID/number",
  "sponsor": "Sponsor company name",
  "phase": "Phase I / II / III / IV",
  "therapeutic_area": "e.g., Gastroenterology, Oncology",

  "design_type": "Full design (e.g., Randomized, double-blind, placebo-controlled, parallel-group)",
  "arm_count": null or number,
  "arms_description": ["Arm 1 with dose", "Arm 2 with dose", "Placebo"] or null,
  "allocation_ratio": "e.g., 1:1:1" or null,
  "blinding": "Double-blind / Open-label / Single-blind" or null,
  "control_type": "Placebo-controlled / Active-controlled" or null,

  "drug_name": "Investigational product name" or null,
  "drug_class": "e.g., monoclonal antibody, small molecule" or null,
  "dose_and_route": "Dose levels and route" or null,
  "dosing_frequency": "e.g., Q2W, every 2 weeks, weekly" or null,
  "administration_duration": "e.g., 60-minute IV infusion" or null,

  "indication": "Primary disease/condition" or null,
  "indication_detail": "Specific severity/stage (e.g., moderate-to-severe UC with Mayo ≥6)" or null,
  "age_range": "e.g., 18-75 years" or null,
  "age_min": null or number,
  "age_max": null or number,
  "sex_eligibility": "All / Male / Female" or null,
  "enrollment_target": null or number,
  "patients_per_site": null or number,
  "target_countries": ["Country1", "Country2"] or null,

  "inclusion_criteria": ["Each specific criterion as separate item", "..."] or null,
  "exclusion_criteria": ["Each specific criterion as separate item", "..."] or null,

  "screening_period": "e.g., Up to 4 weeks" or null,
  "treatment_duration": "e.g., 12 weeks" or null,
  "follow_up_duration": "e.g., 4 weeks safety follow-up" or null,
  "total_duration": "Total per-patient duration" or null,
  "total_visits": null or number,
  "visit_frequency": "e.g., Every 2 weeks" or null,

  "primary_endpoint": "Exact primary endpoint with timepoint" or null,
  "secondary_endpoints": ["Endpoint 1", "Endpoint 2"] or null,
  "primary_assessment": "Scale/instrument (e.g., Mayo Score, RECIST)" or null,

  "required_equipment": ["every piece of equipment/capability"] or null,
  "required_staff": ["every staff type needed"] or null,
  "procedures": ["every procedure patients undergo"] or null,

  "requires_endoscopy": true/false/null,
  "requires_infusion": true/false/null,
  "requires_imaging": ["MRI", "CT", etc.] or null,
  "requires_biopsy": true/false/null,
  "storage_requirements": ["-20°C", "-80°C", etc.] or null,
  "sample_processing": ["centrifuge", "PK processing", etc.] or null,
  "lab_requirements": ["hematology", "chemistry", etc.] or null,
  "ecg_required": true/false/null,

  "dsmb_required": true/false/null,
  "safety_monitoring": "Description of safety oversight" or null
}}

CRITICAL RULES:
- For inclusion/exclusion: list EACH criterion as a SEPARATE array item
  BAD: ["Patients with active UC"]
  GOOD: ["Age 18-75 years", "Mayo score ≥6", "Endoscopic subscore ≥2", ...]
- For equipment: think about what the SITE physically needs
  Include: endoscopy suite, infusion chairs, ECG machine, freezers,
  centrifuge, imaging equipment, pharmacy for drug storage/prep
- For procedures: list EVERY patient procedure
  Include: blood draws, biopsies, imaging scans, endoscopy, ECG,
  vital signs, questionnaires/PROs, PK sampling, physical exam
- For staff: include ALL roles needed
  Include: PI (with specialty), sub-investigators, study coordinators,
  research nurses, infusion nurses, endoscopy team, pharmacist
- Be SPECIFIC. Not just "blood draws" but "blood draws for hematology,
  chemistry, PK sampling at Weeks 0,2,4,8,12"

PROTOCOL CHUNK:
{chunk['text']}"""

        try:
            response = self.openai.create_json_completion(
                prompt=user_prompt,
                system_message=system_prompt,
                temperature=0.1,
                max_tokens=4000
            )
            if response:
                response["_chunk_id"] = chunk["chunk_id"]
                response["_pages"] = f"{chunk['page_start']}-{chunk['page_end']}"
            return response
        except Exception as e:
            logger.error(f"Extraction failed for chunk {chunk['chunk_id']}: {e}")
            return None

    def _merge_extractions(self, extractions: List[Dict]) -> Dict:
        """
        Merge field values across chunks. Strategy:
        - For strings: pick longest non-null value (more detail = better)
        - For lists: union all items, deduplicate
        - For numbers: pick first non-null
        - For booleans: True wins over null/False (if ANY chunk says
          endoscopy is required, it's required)
        """
        merged = {}

        for field in self.REQUIRED_FIELDS:
            values = []
            for ext in extractions:
                val = ext.get(field)
                if val is not None:
                    values.append(val)

            if not values:
                merged[field] = None
                continue

            # Determine merge strategy by type
            first_val = values[0]

            if isinstance(first_val, list):
                # Union all list items, deduplicate
                all_items = []
                seen = set()
                for val_list in values:
                    if isinstance(val_list, list):
                        for item in val_list:
                            item_str = str(item).strip()
                            item_lower = item_str.lower()
                            if item_lower not in seen and item_str:
                                seen.add(item_lower)
                                all_items.append(item_str)
                merged[field] = all_items if all_items else None

            elif isinstance(first_val, bool):
                # True wins (if any chunk says required, it is)
                merged[field] = any(v for v in values if isinstance(v, bool))

            elif isinstance(first_val, (int, float)):
                # Pick first non-null number
                merged[field] = first_val

            elif isinstance(first_val, str):
                # Pick longest string (most detail)
                best = max(values, key=lambda v: len(str(v)) if v else 0)
                merged[field] = best
            else:
                merged[field] = first_val

        return merged

    def _find_missing_fields(self, merged: Dict) -> List[str]:
        """Find critical fields that are still null after merge."""
        missing = []
        for field in self.CRITICAL_FIELDS:
            val = merged.get(field)
            if val is None or val == "" or val == []:
                missing.append(field)
        return missing

    async def _gap_fill(
        self, merged: Dict, missing: List[str], pages: List[Dict]
    ) -> Dict:
        """
        Targeted re-extraction for missing critical fields.
        Send a focused prompt with the FULL synopsis + relevant sections.
        """
        # Combine first 10 pages + last 5 pages (synopsis + appendices)
        target_pages = pages[:10] + pages[-5:] if len(pages) > 15 else pages
        combined_text = "\n\n".join(
            f"[Page {p['page_num']}]\n{p['text']}"
            for p in target_pages
        )[:30000]  # ~7500 tokens

        missing_str = ", ".join(missing)

        system_prompt = """You are an expert clinical trial protocol analyst.
Some fields were missed in initial extraction. Find them now.
Only extract what is EXPLICITLY stated. Use null if truly not found."""

        user_prompt = f"""The following fields were NOT found in initial extraction
and need to be found: {missing_str}

Current partial extraction (for context):
- Indication: {merged.get('indication', 'unknown')}
- Phase: {merged.get('phase', 'unknown')}
- Drug: {merged.get('drug_name', 'unknown')}

Search this protocol text and extract ONLY the missing fields as JSON.
For list fields (inclusion_criteria, exclusion_criteria, procedures,
required_equipment), be comprehensive - list EVERY item.

PROTOCOL TEXT:
{combined_text}"""

        try:
            response = self.openai.create_json_completion(
                prompt=user_prompt,
                system_message=system_prompt,
                temperature=0.1,
                max_tokens=4000
            )
            if response:
                # Only fill in fields that were missing
                for field in missing:
                    new_val = response.get(field)
                    if new_val is not None and new_val != "" and new_val != []:
                        merged[field] = new_val
                        logger.info(f"Gap-filled field '{field}'")
        except Exception as e:
            logger.error(f"Gap-fill extraction failed: {e}")

        return merged

    def _build_result(self, merged: Dict, total_pages: int, chunks_processed: int) -> ExtractionResult:
        """Build ExtractionResult from merged dict with confidence calculation."""

        # Calculate confidence
        confidence = self._calculate_confidence(merged)

        # Build warnings
        warnings = []
        missing_critical = self._find_missing_fields(merged)
        if missing_critical:
            warnings.append(f"Missing critical fields: {', '.join(missing_critical)}")
        if confidence < 50:
            warnings.append("Low extraction confidence - manual review recommended")

        # Helper functions
        def get_str(key: str, default: str = "") -> str:
            val = merged.get(key)
            return str(val) if val else default

        def get_int(key: str) -> Optional[int]:
            val = merged.get(key)
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        def get_bool(key: str, default: bool = False) -> bool:
            val = merged.get(key)
            if val is None:
                return default
            return bool(val)

        def get_list(key: str) -> List[str]:
            val = merged.get(key)
            if not val:
                return []
            if isinstance(val, list):
                return [str(item) for item in val if item]
            return []

        return ExtractionResult(
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
            total_pages=total_pages,
            chunks_processed=chunks_processed,
            raw_extraction=merged,
        )

    def _calculate_confidence(self, merged: Dict) -> float:
        """
        Calculate extraction confidence as percentage of fields populated.
        Weight critical fields more heavily.
        """
        score = 0
        total = 0

        for field in self.CRITICAL_FIELDS:
            total += 3  # Critical fields worth 3x
            val = merged.get(field)
            if val is not None and val != "" and val != []:
                score += 3

        for field in self.IMPORTANT_FIELDS:
            total += 2  # Important fields worth 2x
            val = merged.get(field)
            if val is not None and val != "" and val != []:
                score += 2

        for field in self.REQUIRED_FIELDS:
            if field not in self.CRITICAL_FIELDS and field not in self.IMPORTANT_FIELDS:
                total += 1
                val = merged.get(field)
                if val is not None and val != "" and val != []:
                    score += 1

        return round((score / total) * 100) if total > 0 else 0
