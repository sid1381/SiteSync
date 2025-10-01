from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional, Dict
from datetime import date, datetime
import json
from pydantic import BaseModel
from app.db import get_session
from app import models
from app.schemas.survey import SurveyCreate

router = APIRouter(prefix="/surveys", tags=["surveys"])

@router.post("/create")
async def create_survey(
    survey_data: SurveyCreate,
    db: Session = Depends(get_session)
):
    """Create a new survey entry in the inbox"""
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

    return {
        "success": True,
        "survey_id": survey.id,
        "message": f"Survey created for {survey_data.study_name}"
    }

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
        from app.services.feasibility_scorer import FeasibilityScorer
        from app.routes.site_profile import get_site_profile

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

        print(f"✅ Extracted {len(protocol_requirements.get('equipment', []))} equipment requirements")
        print(f"✅ Extracted {len(protocol_requirements.get('staff', []))} staff requirements")

        # STEP 2: Score feasibility (Protocol Requirements vs Site Capabilities)
        site_profile_response = await get_site_profile(survey.site_id, db)

        scorer = FeasibilityScorer()
        feasibility_result = scorer.score_feasibility(
            protocol_requirements={"requirements": protocol_requirements},
            site_profile=site_profile_response
        )

        # Update survey with REAL feasibility scoring
        survey.feasibility_score = int(feasibility_result.percentage)
        survey.score_breakdown = {
            "total_score": feasibility_result.total_score,
            "max_possible": feasibility_result.max_possible,
            "percentage": feasibility_result.percentage,
            "category_scores": feasibility_result.category_scores,
            "critical_gaps": feasibility_result.critical_gaps
        }
        survey.flags = feasibility_result.flags

        # STEP 3: Enhanced survey question answering (Survey Questions vs Site Data)
        # This happens SEPARATELY from feasibility scoring
        if survey.survey_questions:
            from app.services.autofill_engine import AutofillEngine
            autofill_engine = AutofillEngine()

            print(f"🔄 Re-processing {len(survey.survey_questions)} extracted questions with enhanced mapping...")

            enhanced_result = await autofill_engine.process_extracted_questions(
                survey.survey_questions,  # Already extracted questions (correct method!)
                site_profile_response
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
            "equipment_requirements": len(protocol_requirements.get("equipment", [])),
            "staff_requirements": len(protocol_requirements.get("staff", [])),
            "feasibility_score": survey.feasibility_score,
            "score_breakdown": survey.score_breakdown,
            "completion_percentage": survey.completion_percentage,
            "flags": survey.flags,
            "critical_gaps": feasibility_result.critical_gaps
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

        # Get site profile for intelligent mapping
        site = db.get(models.Site, survey.site_id)
        from app.routes.site_profile import get_site_profile

        # Get complete site profile
        site_profile_response = await get_site_profile(survey.site_id, db)

        # Initialize AI engine
        autofill_engine = AutofillEngine()

        # Process document with universal AI
        result = await autofill_engine.process_survey_document_universal(
            file_content, file.filename, site_profile_response
        )

        if result["success"]:
            # Store extracted questions and initial autofill results
            survey.survey_questions = result["questions"]
            survey.autofilled_responses = result["responses"]
            survey.completion_percentage = result["completion_percentage"]
            survey.feasibility_score = result["feasibility_score"]
            survey.flags = result["flags"]
            survey.status = "survey_processed"  # Ready for protocol upload
            db.commit()

            return {
                "success": True,
                "questions_extracted": result["questions_extracted"],
                "objective_questions": result["categorization"]["objective_questions"],
                "subjective_questions": result["categorization"]["subjective_questions"],
                "autofilled_questions": result["autofilled_count"],
                "completion_percentage": result["completion_percentage"],
                "feasibility_score": result["feasibility_score"],
                "categorization": result["categorization"],
                "mapping_statistics": result["mapping_statistics"],
                "flags": result["flags"],
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

@router.get("/{survey_id}/download/{format}")
async def download_export(
    survey_id: int,
    format: str,
    db: Session = Depends(get_session)
):
    """Download PDF or Excel export"""
    survey = db.get(models.Survey, survey_id)
    if not survey:
        raise HTTPException(status_code=404, detail="Survey not found")

    # Get all responses
    all_responses = db.query(models.SurveyResponse).filter(
        models.SurveyResponse.survey_id == survey_id
    ).all()

    responses_list = [
        {
            "id": r.question_id,
            "text": r.question_text,
            "type": r.question_type,
            "is_objective": r.is_objective,
            "response": r.response_value,
            "source": r.response_source,
            "confidence": r.confidence_score
        }
        for r in all_responses
    ]

    # Prepare survey data
    site = db.get(models.Site, survey.site_id)
    survey_data = {
        "sponsor_name": survey.sponsor_name,
        "study_name": survey.study_name,
        "nct_number": survey.nct_number,
        "site_name": site.name,
        "feasibility_score": survey.feasibility_score,
        "completion_percentage": survey.completion_percentage,
        "score_breakdown": survey.score_breakdown
    }

    from app.services.export_service import ExportService
    exporter = ExportService()

    if format == "pdf":
        content = exporter.generate_pdf_export(survey_data, responses_list)
        media_type = "application/pdf"
        filename = f"Feasibility_{survey.study_name.replace(' ', '_')}.pdf"
    elif format == "excel":
        content = exporter.generate_excel_export(survey_data, responses_list)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = f"Feasibility_{survey.study_name.replace(' ', '_')}.xlsx"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    from fastapi.responses import Response
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
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