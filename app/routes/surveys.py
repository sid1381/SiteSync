from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
import json
import logging
from pydantic import BaseModel
from app.db import get_session
from app import models
from app.schemas.survey import SurveyCreate
from app.services.feasibility_scorer import calculate_feasibility_score

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/surveys", tags=["surveys"])

@router.post("/create")
async def create_survey(
    survey_data: SurveyCreate,
    db: Session = Depends(get_session)
):
    """Create a new survey entry in the inbox"""
    try:
        logger.info(f"📝 Creating survey: {survey_data.study_name}")
        logger.info(f"📊 Survey data: site_id={survey_data.site_id}, sponsor={survey_data.sponsor_name}")

        # Verify site exists
        site = db.get(models.Site, survey_data.site_id)
        if not site:
            logger.error(f"❌ Site {survey_data.site_id} not found")
            raise HTTPException(status_code=404, detail=f"Site {survey_data.site_id} not found")

        logger.info(f"✓ Site found: {site.name}")

        survey = models.Survey(
            site_id=survey_data.site_id,
            sponsor_name=survey_data.sponsor_name,
            study_name=survey_data.study_name,
            study_type=survey_data.study_type,
            nct_number=survey_data.nct_number,
            due_date=survey_data.due_date,
            status="pending"
        )
        db.add(survey)
        db.commit()
        db.refresh(survey)

        logger.info(f"✅ Survey created successfully: ID={survey.id}")

        return {
            "success": True,
            "survey_id": survey.id,
            "message": f"Survey created for {survey_data.study_name}"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Survey creation failed: {str(e)}")
        logger.exception("Full exception details:")
        raise HTTPException(status_code=500, detail=f"Survey creation failed: {str(e)}")

@router.get("/inbox/{site_id}")
async def get_inbox(site_id: int, db: Session = Depends(get_session)):
    """Get all surveys for a site"""
    surveys = db.query(models.Survey).filter(
        models.Survey.site_id == site_id
    ).order_by(models.Survey.due_date.asc()).all()

    return {
        "surveys": [
            {
                "id": s.id,
                "sponsor_name": s.sponsor_name,
                "study_name": s.study_name,
                "study_type": s.study_type,
                "nct_number": s.nct_number,
                "due_date": s.due_date.isoformat() if s.due_date else None,
                "status": s.status,
                "feasibility_score": s.feasibility_score,
                "completion_percentage": s.completion_percentage,
                "days_until_due": (s.due_date - date.today()).days if s.due_date else None
            }
            for s in surveys
        ]
    }

@router.post("/{survey_id}/upload-protocol")
async def upload_protocol(
    survey_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session)
):
    """Upload protocol document AFTER survey is already uploaded and processed"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Check that survey has been uploaded first
    if survey.status not in ["survey_processed", "ready_for_autofill"]:
        raise HTTPException(
            status_code=400,
            detail="Survey document must be uploaded and processed before protocol upload"
        )

    # Save file
    file_content = await file.read()
    file_path = f"protocols/survey_{survey_id}_protocol.pdf"
    # TODO: Save to storage (MinIO/S3)

    survey.protocol_file_path = file_path
    survey.status = "processing_protocol"
    db.commit()

    # STEP 1: Extract real protocol requirements using new extractor
    try:
        from app.services.protocol_requirement_extractor import ProtocolRequirementExtractor

        print("🔍 Processing protocol with real requirement extraction...")

        # Extract requirements from protocol PDF
        extractor = ProtocolRequirementExtractor()
        extraction_result = extractor.extract_requirements_from_pdf(file_content)

        if not extraction_result["success"]:
            raise Exception(f"Protocol extraction failed: {extraction_result.get('error', 'Unknown error')}")

        protocol_requirements = extraction_result["requirements"]

        # Store extracted requirements
        survey.protocol_extracted_data = protocol_requirements
        survey.status = "protocol_processed"
        db.commit()

        # Log actual extraction results with correct keys
        print(f"✅ Protocol extraction complete:")
        print(f"   Equipment: {len(protocol_requirements.get('equipment_required', []))} items")
        print(f"   Staff: {len(protocol_requirements.get('staff_requirements', []))} roles")
        print(f"   Procedures: {len(protocol_requirements.get('procedures', []))} procedures")
        print(f"   Study duration: {protocol_requirements.get('study_timeline', {}).get('total_duration_weeks')} weeks")
        print(f"   Enrollment target: {protocol_requirements.get('study_timeline', {}).get('enrollment_target')} patients")
        print(f"   Phase: {protocol_requirements.get('study_identification', {}).get('phase')}")
        print(f"   Primary indication: {protocol_requirements.get('patient_population', {}).get('primary_indication')}")

        # STEP 2: Score feasibility (Protocol Requirements vs Site Capabilities)
        # Get site info
        site = db.get(models.Site, survey.site_id) if survey.site_id else None

        # Build site profile dict from the 6 JSONB fields
        site_profile = {
            "population_capabilities": site.population_capabilities or {},
            "staff_and_experience": site.staff_and_experience or {},
            "facilities_and_equipment": site.facilities_and_equipment or {},
            "operational_capabilities": site.operational_capabilities or {},
            "historical_performance": site.historical_performance or {},
            "compliance_and_training": site.compliance_and_training or {}
        }

        # Get PI name from site profile
        pi_name = site_profile.get("staff_and_experience", {}).get("principal_investigator", {}).get("name", "")

        # Calculate feasibility score using new async scorer
        try:
            feasibility_result = await calculate_feasibility_score(
                protocol_requirements=protocol_requirements,
                site_profile=site_profile,
                pi_name=pi_name,
                site_name=site.name if site else None
            )

            # Update survey with feasibility scoring
            survey.feasibility_score = int(feasibility_result["total_score"])
            survey.score_breakdown = feasibility_result  # Store full breakdown as JSONB

            print(f"✅ Feasibility score calculated: {feasibility_result['total_score']}/100 ({feasibility_result['grade']})")
            print(f"   Components: {len(feasibility_result.get('components', []))} categories scored")
            print(f"   Flags: {len(feasibility_result.get('flags', []))} issues identified")
        except Exception as e:
            print(f"⚠️ Feasibility auto-calculation failed: {e}")
            # Don't fail the upload if scoring fails
            survey.feasibility_score = None
            survey.score_breakdown = {}

        # STEP 3: Enhanced survey question answering (Survey Questions vs Site Data)
        # This happens SEPARATELY from feasibility scoring
        if survey.survey_questions:
            from app.services.autofill_engine import AutofillEngine
            autofill_engine = AutofillEngine()

            print(f"🔄 Re-processing {len(survey.survey_questions)} extracted questions with enhanced mapping...")

            enhanced_result = await autofill_engine.process_extracted_questions(
                survey.survey_questions,  # Already extracted questions (correct method!)
                site_profile,
                protocol_requirements  # Pass protocol data to mapper!
            )

            if enhanced_result["success"]:
                survey.autofilled_responses = enhanced_result["responses"]
                survey.completion_percentage = enhanced_result["completion_percentage"]
                print(f"✅ Enhanced mapping completed: {enhanced_result['autofilled_count']} questions mapped")
            else:
                print(f"❌ Enhanced mapping failed: {enhanced_result.get('error', 'Unknown error')}")

        survey.status = "autofilled"
        db.commit()

        print(f"🎯 Final feasibility score: {survey.feasibility_score}/100")
        print(f"📋 Survey completion: {survey.completion_percentage:.1f}%")

        return {
            "success": True,
            "extracted_fields": sum(len(v) if isinstance(v, list) else 1 for v in protocol_requirements.values()),
            "equipment_requirements": len(protocol_requirements.get("equipment_required", [])),
            "staff_requirements": len(protocol_requirements.get("staff_requirements", [])),
            "feasibility_score": survey.feasibility_score,
            "score_breakdown": survey.score_breakdown,
            "completion_percentage": survey.completion_percentage,
            "grade": survey.score_breakdown.get("grade", "Unknown") if survey.score_breakdown else None,
            "flags": survey.score_breakdown.get("flags", []) if survey.score_breakdown else [],
            "gaps": survey.score_breakdown.get("gaps", []) if survey.score_breakdown else []
        }

    except Exception as e:
        # Log the error and return a basic response
        print(f"Error processing protocol: {e}")
        survey.status = "protocol_uploaded"
        db.commit()

        return {
            "success": True,
            "extracted_fields": 0,
            "feasibility_score": None,
            "flags": []
        }

@router.post("/{survey_id}/calculate-feasibility")
async def calculate_feasibility(survey_id: int, db: Session = Depends(get_session)):
    """
    Calculate feasibility score by comparing protocol requirements to site capabilities.
    Uses site profile data + ClinicalTrials.gov API for historical verification.
    """
    import asyncio

    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if not survey.protocol_extracted_data:
        raise HTTPException(status_code=400, detail="Protocol must be uploaded first")

    # Get site profile
    site = db.get(models.Site, survey.site_id) if survey.site_id else None
    if not site:
        raise HTTPException(status_code=400, detail="No site associated with survey")

    # Build site profile dict from the 6 JSONB fields
    site_profile = {
        "population_capabilities": site.population_capabilities or {},
        "staff_and_experience": site.staff_and_experience or {},
        "facilities_and_equipment": site.facilities_and_equipment or {},
        "operational_capabilities": site.operational_capabilities or {},
        "historical_performance": site.historical_performance or {},
        "compliance_and_training": site.compliance_and_training or {}
    }

    # Get PI name from site profile
    pi_name = None
    staff = site_profile.get("staff_and_experience", {})
    pi = staff.get("principal_investigator", {})
    if pi:
        pi_name = pi.get("name", "")

    # Calculate feasibility score
    try:
        result = await calculate_feasibility_score(
            protocol_requirements=survey.protocol_extracted_data,
            site_profile=site_profile,
            pi_name=pi_name,
            site_name=site.name
        )

        # Store results in survey
        survey.feasibility_score = int(result["total_score"])
        survey.score_breakdown = result  # Store full breakdown as JSONB
        db.commit()

        return {
            "success": True,
            "survey_id": survey_id,
            "feasibility_score": result["total_score"],
            "grade": result["grade"],
            "components": result["components"],
            "flags": result["flags"],
            "gaps": result["gaps"],
            "requirements_comparison": result["requirements_comparison"]
        }

    except Exception as e:
        print(f"Feasibility calculation error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Feasibility calculation failed: {str(e)}")


@router.get("/{survey_id}/feasibility")
async def get_feasibility(survey_id: int, db: Session = Depends(get_session)):
    """Get the stored feasibility score and breakdown for a survey"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    if not survey.score_breakdown:
        return {
            "success": False,
            "message": "Feasibility score not yet calculated",
            "survey_id": survey_id
        }

    breakdown = survey.score_breakdown
    return {
        "success": True,
        "survey_id": survey_id,
        "feasibility_score": survey.feasibility_score,
        "grade": breakdown.get("grade", "Unknown"),
        "components": breakdown.get("components", []),
        "flags": breakdown.get("flags", []),
        "gaps": breakdown.get("gaps", []),
        "requirements_comparison": breakdown.get("requirements_comparison", [])
    }

@router.post("/{survey_id}/upload-survey")
async def upload_survey_document(
    survey_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_session)
):
    """Upload survey questionnaire FIRST (PDF or Excel) - extract questions to understand what needs answering"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Survey should be uploaded first, before protocol
    if survey.status not in ["pending"]:
        raise HTTPException(
            status_code=400,
            detail="Survey can only be uploaded when status is 'pending'"
        )

    # Determine file type
    file_extension = file.filename.split('.')[-1].lower()
    if file_extension not in ['pdf', 'xlsx', 'xls']:
        raise HTTPException(status_code=400, detail="Only PDF and Excel files supported")

    # Save file
    file_content = await file.read()
    file_path = f"surveys/survey_{survey_id}_questionnaire.{file_extension}"
    # TODO: Save to storage

    survey.survey_file_path = file_path
    survey.survey_format = 'excel' if file_extension in ['xlsx', 'xls'] else 'pdf'
    survey.status = "processing_survey"
    db.commit()

    # Extract questions using Universal AI Parser
    try:
        from app.services.autofill_engine import AutofillEngine

        # Initialize AI engine
        autofill_engine = AutofillEngine()

        # CRITICAL FIX: Only extract and categorize questions - DO NOT AUTOFILL yet!
        # Autofill will happen AFTER protocol upload when we have complete context
        print("📋 Survey upload: Extracting and categorizing questions (no autofill yet)")
        result = await autofill_engine.extract_and_categorize_questions_only(
            file_content, file.filename
        )

        if result["success"]:
            # Store extracted questions ONLY - no responses yet
            survey.survey_questions = result["questions"]
            survey.autofilled_responses = []  # Empty - will be filled after protocol upload
            survey.completion_percentage = 0  # Will be calculated after protocol upload
            survey.feasibility_score = None  # Will be calculated after protocol upload
            survey.flags = []  # Will be generated after protocol upload
            survey.status = "survey_processed"  # Ready for protocol upload
            db.commit()

            print(f"✅ Extracted {result['questions_extracted']} questions")
            print(f"   Objective: {result['categorization']['objective_questions']}")
            print(f"   Subjective: {result['categorization']['subjective_questions']}")
            print(f"⏭️  Next: Upload protocol to enable autofill")

            return {
                "success": True,
                "questions_extracted": result["questions_extracted"],
                "objective_questions": result["categorization"]["objective_questions"],
                "subjective_questions": result["categorization"]["subjective_questions"],
                "autofilled_questions": 0,  # No autofill yet
                "completion_percentage": 0,  # No autofill yet
                "feasibility_score": None,  # No scoring yet
                "categorization": result["categorization"],
                "mapping_statistics": {},
                "flags": [],
                "next_step": result["next_step"]
            }
        else:
            # Fallback to simple processing
            raise Exception(result.get("error", "AI processing failed"))

    except Exception as e:
        print(f"Error processing survey: {e}")
        survey.status = "survey_upload_failed"
        db.commit()
        return {
            "success": False,
            "error": str(e)
        }

class SubmitRequest(BaseModel):
    sponsor_email: str
    subjective_responses: List[Dict[str, str]]

@router.post("/{survey_id}/submit")
async def submit_survey(
    survey_id: int,
    submit_data: SubmitRequest,
    db: Session = Depends(get_session)
):
    """Submit completed survey with manual responses filled"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # For demo purposes, just update the survey status
    survey.submitted_at = datetime.now()
    survey.submitted_to_email = submit_data.sponsor_email
    survey.status = "submitted"
    db.commit()

    # Mock successful submission
    return {
        "success": True,
        "email_sent": True,
        "pdf_download": f"/surveys/{survey_id}/download/pdf",
        "excel_download": f"/surveys/{survey_id}/download/excel",
        "message": f"Survey submitted to {submit_data.sponsor_email}"
    }

@router.get("/{survey_id}/download/pdf")
async def download_pdf(survey_id: int, db: Session = Depends(get_session)):
    """Download completed survey as PDF"""
    print(f"=== PDF DOWNLOAD CALLED for survey_id: {survey_id} ===")
    from app.services.export_service import ExportService
    from fastapi.responses import Response

    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Get site profile for context
    site = db.get(models.Site, survey.site_id) if survey.site_id else None
    site_profile = {
        "population_capabilities": site.population_capabilities if site else {},
        "staff_and_experience": site.staff_and_experience if site else {},
        "facilities_and_equipment": site.facilities_and_equipment if site else {},
        "operational_capabilities": site.operational_capabilities if site else {},
        "historical_performance": site.historical_performance if site else {},
        "compliance_and_training": site.compliance_and_training if site else {}
    } if site else {}

    # Build responses from JSONB fields (not the empty SurveyResponse table)
    all_responses = []

    # Get autofilled responses (objective questions)
    if survey.autofilled_responses:
        for resp in survey.autofilled_responses:
            all_responses.append({
                "question_number": resp.get("id", ""),  # Fixed: 'id' not 'question_number'
                "question_text": resp.get("text", ""),  # Fixed: 'text' not 'question_text'
                "response": resp.get("response", ""),
                "confidence": resp.get("confidence", 0),
                "is_objective": resp.get("is_objective", True),
                "category": resp.get("category", "General")
            })

    # Get extracted questions that might have manual responses
    if survey.survey_questions:
        # Create a lookup of already-added questions
        added_questions = {r["question_text"] for r in all_responses}

        for q in survey.survey_questions:
            q_text = q.get("text", "")  # Fixed: 'text' not 'question_text'
            if q_text and q_text not in added_questions:
                all_responses.append({
                    "question_number": q.get("id", ""),  # Fixed: 'id' not 'question_number'
                    "question_text": q_text,
                    "response": q.get("response", "Requires manual review"),
                    "confidence": q.get("confidence", 0),
                    "is_objective": q.get("is_objective", False),
                    "category": q.get("category", "General")
                })

    # Sort by question number if available
    all_responses.sort(key=lambda x: (
        int(x["question_number"]) if x["question_number"] and str(x["question_number"]).isdigit() else 999
    ))

    # Build survey data for export
    survey_data = {
        "id": survey.id,
        "sponsor_name": survey.sponsor_name or "Unknown Sponsor",
        "study_name": survey.study_name or "Unknown Study",
        "study_type": survey.study_type or "Unknown Type",
        "nct_number": survey.nct_number or "",
        "due_date": str(survey.due_date) if survey.due_date else "",
        "feasibility_score": survey.feasibility_score or 0,
        "completion_percentage": survey.completion_percentage or 0,
        "submitted_at": str(survey.submitted_at) if survey.submitted_at else "",
        "submitted_to_email": survey.submitted_to_email or "",
        "score_breakdown": survey.score_breakdown or {},
        "site_name": site.name if site else "Unknown Site"
    }

    # Generate PDF
    export_service = ExportService()
    pdf_bytes = export_service.generate_pdf_export(survey_data, all_responses, site_profile)

    filename = f"SiteSync_Survey_{survey.sponsor_name}_{survey.study_name}_{survey.id}.pdf".replace(" ", "_")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@router.get("/{survey_id}/download/excel")
async def download_excel(survey_id: int, db: Session = Depends(get_session)):
    """Download completed survey as Excel"""
    from app.services.export_service import ExportService
    from fastapi.responses import Response

    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Get site profile for context
    site = db.get(models.Site, survey.site_id) if survey.site_id else None
    site_profile = {
        "population_capabilities": site.population_capabilities if site else {},
        "staff_and_experience": site.staff_and_experience if site else {},
        "facilities_and_equipment": site.facilities_and_equipment if site else {},
        "operational_capabilities": site.operational_capabilities if site else {},
        "historical_performance": site.historical_performance if site else {},
        "compliance_and_training": site.compliance_and_training if site else {}
    } if site else {}

    # Build responses from JSONB fields (same logic as PDF)
    all_responses = []

    if survey.autofilled_responses:
        for resp in survey.autofilled_responses:
            all_responses.append({
                "question_number": resp.get("id", ""),  # Fixed: 'id' not 'question_number'
                "question_text": resp.get("text", ""),  # Fixed: 'text' not 'question_text'
                "response": resp.get("response", ""),
                "confidence": resp.get("confidence", 0),
                "is_objective": resp.get("is_objective", True),
                "category": resp.get("category", "General")
            })

    if survey.survey_questions:
        added_questions = {r["question_text"] for r in all_responses}

        for q in survey.survey_questions:
            q_text = q.get("text", "")  # Fixed: 'text' not 'question_text'
            if q_text and q_text not in added_questions:
                all_responses.append({
                    "question_number": q.get("id", ""),  # Fixed: 'id' not 'question_number'
                    "question_text": q_text,
                    "response": q.get("response", "Requires manual review"),
                    "confidence": q.get("confidence", 0),
                    "is_objective": q.get("is_objective", False),
                    "category": q.get("category", "General")
                })

    all_responses.sort(key=lambda x: (
        int(x["question_number"]) if x["question_number"] and str(x["question_number"]).isdigit() else 999
    ))

    survey_data = {
        "id": survey.id,
        "sponsor_name": survey.sponsor_name or "Unknown Sponsor",
        "study_name": survey.study_name or "Unknown Study",
        "study_type": survey.study_type or "Unknown Type",
        "nct_number": survey.nct_number or "",
        "due_date": str(survey.due_date) if survey.due_date else "",
        "feasibility_score": survey.feasibility_score or 0,
        "completion_percentage": survey.completion_percentage or 0,
        "submitted_at": str(survey.submitted_at) if survey.submitted_at else "",
        "submitted_to_email": survey.submitted_to_email or "",
        "score_breakdown": survey.score_breakdown or {},
        "site_name": site.name if site else "Unknown Site"
    }

    # Debug logging
    print(f"Excel export: Survey {survey_id} has {len(all_responses)} responses")
    if all_responses:
        print(f"First response sample: {all_responses[0]}")

    export_service = ExportService()
    excel_bytes = export_service.generate_excel_export(survey_data, all_responses, site_profile)

    filename = f"SiteSync_Survey_{survey.sponsor_name}_{survey.study_name}_{survey.id}.xlsx".replace(" ", "_")

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

@router.get("/{survey_id}")
async def get_survey(survey_id: int, db: Session = Depends(get_session)):
    """Get survey details with responses"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Use actual extracted questions and responses from the database
    responses = []

    if survey.survey_questions is not None and survey.autofilled_responses is not None:
        # Use the real extracted questions and autofilled responses
        questions = survey.survey_questions
        autofilled_responses = survey.autofilled_responses

        # Handle both formats: list of question objects or list of strings
        for i, question_data in enumerate(questions):
            question_id = f"q_{i+1}"

            # Extract question text (handle both object and string formats)
            if isinstance(question_data, dict):
                question_text = question_data.get('text', str(question_data))
                question_type = question_data.get('type', 'text')
                is_objective = question_data.get('is_objective', False)
            else:
                question_text = str(question_data)
                question_type = 'text'
                is_objective = False

            # Find corresponding response (handle both list and dict formats)
            response_data = {}
            if isinstance(autofilled_responses, list) and i < len(autofilled_responses):
                response_data = autofilled_responses[i] if isinstance(autofilled_responses[i], dict) else {}
            elif isinstance(autofilled_responses, dict):
                response_data = autofilled_responses.get(question_id, {})

            responses.append({
                "id": question_id,
                "text": question_text,
                "type": response_data.get("type", question_type),
                "is_objective": response_data.get("is_objective", is_objective),
                "response": response_data.get("response", ""),
                "source": response_data.get("source", "manual_required"),
                "confidence": response_data.get("confidence", 0.0),
                "manually_edited": False
            })
    else:
        # Fallback for surveys that haven't been processed yet
        responses = [{
            "id": "q_1",
            "text": "Survey not yet processed - please upload survey document first",
            "type": "text",
            "is_objective": False,
            "response": "",
            "source": "not_processed",
            "confidence": 0,
            "manually_edited": False
        }]

    return {
        "survey": {
            "id": survey.id,
            "sponsor_name": survey.sponsor_name,
            "study_name": survey.study_name,
            "study_type": survey.study_type,
            "nct_number": survey.nct_number,
            "due_date": survey.due_date.isoformat() if survey.due_date else None,
            "status": survey.status,
            "feasibility_score": survey.feasibility_score,
            "completion_percentage": survey.completion_percentage,
            "score_breakdown": survey.score_breakdown,
            "flags": survey.flags
        },
        "responses": responses
    }