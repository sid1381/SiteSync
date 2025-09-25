from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from app.db import get_session
from app.services.feasibility_processor import FeasibilityProcessor
import asyncio

router = APIRouter(prefix="/feasibility", tags=["feasibility"])

@router.post("/process-protocol")
async def process_protocol_for_feasibility(
    site_id: int,
    protocol_file: UploadFile = File(...),
    db: Session = Depends(get_session)
):
    """
    Main endpoint: Upload protocol PDF and get auto-filled feasibility assessment
    """

    # Validate file
    if not protocol_file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files supported")

    if protocol_file.size and protocol_file.size > 50 * 1024 * 1024:  # 50MB limit
        raise HTTPException(status_code=400, detail="File too large (max 50MB)")

    try:
        # Read PDF content
        pdf_content = await protocol_file.read()

        # Process with feasibility processor
        processor = FeasibilityProcessor()
        result = processor.process_protocol_for_feasibility(
            db=db,
            protocol_pdf_bytes=pdf_content,
            site_id=site_id
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "success": True,
            "message": f"Processed {protocol_file.filename} successfully",
            "data": result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")

@router.get("/form-templates")
async def get_feasibility_form_templates():
    """
    Get available feasibility form templates
    """

    return {
        "templates": {
            "uab_abbreviated": {
                "name": "UAB Abbreviated Protocol Feasibility Assessment",
                "description": "Standard UAB feasibility form",
                "sections": [
                    {
                        "title": "Protocol Information",
                        "questions": [
                            {"key": "protocol_title", "label": "Protocol Title", "type": "text", "required": True},
                            {"key": "protocol_number", "label": "Protocol Number", "type": "text", "required": True},
                            {"key": "phase", "label": "Protocol Phase", "type": "select",
                             "options": ["Phase I", "Phase II", "Phase III", "Phase IV", "Device", "Other"]},
                            {"key": "sponsor", "label": "Sponsor/CRO", "type": "text"},
                            {"key": "drug_administration", "label": "Drug Administration", "type": "select",
                             "options": ["N/A", "PO", "SQ", "IM", "IV"]}
                        ]
                    },
                    {
                        "title": "Population",
                        "questions": [
                            {"key": "population_age", "label": "Population age", "type": "text"},
                            {"key": "participant_health_status", "label": "Participant health status", "type": "select",
                             "options": ["life threatening", "chronic", "healthy"]},
                            {"key": "expected_enrollment", "label": "Expected enrollment", "type": "number"},
                            {"key": "enrollment_realistic", "label": "Is enrollment realistic?", "type": "yes_no"},
                            {"key": "access_to_population", "label": "Access to population?", "type": "yes_no"},
                            {"key": "inclusion_exclusion_restrictive", "label": "Are criteria restrictive?", "type": "yes_no"}
                        ]
                    },
                    {
                        "title": "Procedures",
                        "questions": [
                            {"key": "procedures_complex", "label": "Complex procedures?", "type": "yes_no"},
                            {"key": "washout_period", "label": "Washout period?", "type": "yes_no"},
                            {"key": "pk_samples", "label": "PK samples?", "type": "yes_no"},
                            {"key": "pk_intensive", "label": "Intensive PK sampling?", "type": "yes_no"},
                            {"key": "special_equipment", "label": "Special equipment required?", "type": "yes_no"}
                        ]
                    },
                    {
                        "title": "Staff & Resources",
                        "questions": [
                            {"key": "workload_manageable", "label": "Workload manageable?", "type": "yes_no"},
                            {"key": "adequate_staff", "label": "Adequate staff?", "type": "yes_no"},
                            {"key": "extended_hours", "label": "Extended hours required?", "type": "yes_no"},
                            {"key": "additional_specialists", "label": "Additional specialists needed?", "type": "yes_no"},
                            {"key": "budget_covers", "label": "Budget adequate?", "type": "yes_no"}
                        ]
                    },
                    {
                        "title": "Time Estimates",
                        "questions": [
                            {"key": "time_recruitment", "label": "Recruitment hours", "type": "number"},
                            {"key": "time_visits", "label": "Visit hours", "type": "number"},
                            {"key": "time_monitoring", "label": "Monitoring hours", "type": "number"},
                            {"key": "time_queries", "label": "Query hours", "type": "number"}
                        ]
                    }
                ]
            }
        }
    }

@router.post("/save-responses")
async def save_feasibility_responses(
    site_id: int,
    protocol_id: int,
    responses: Dict[str, Any],
    db: Session = Depends(get_session)
):
    """
    Save completed feasibility responses
    """

    # Here you would save the completed responses to database
    # For now, return success

    return {
        "success": True,
        "message": "Feasibility responses saved",
        "site_id": site_id,
        "protocol_id": protocol_id,
        "response_count": len(responses)
    }

@router.get("/export/{site_id}/{protocol_id}")
async def export_feasibility_report(
    site_id: int,
    protocol_id: int,
    format: str = "pdf",
    db: Session = Depends(get_session)
):
    """
    Export completed feasibility assessment as PDF or Excel
    """

    # This would generate the export file
    # For now, return placeholder

    return {
        "success": True,
        "message": f"Export generated in {format} format",
        "download_url": f"/downloads/feasibility_{site_id}_{protocol_id}.{format}"
    }

@router.get("/demo/uab-form-preview")
async def get_uab_form_preview():
    """
    Get preview of what a completed UAB form looks like for demo purposes
    """

    return {
        "form_name": "UAB Abbreviated Protocol Feasibility Assessment Form",
        "demo_responses": {
            "protocol_title": {
                "answer": "A Phase II Study of XYZ-123 in Advanced NASH",
                "confidence": "high",
                "locked": True,
                "evidence": "Extracted from protocol document",
                "source": "protocol_extraction"
            },
            "protocol_number": {
                "answer": "NCT05123456",
                "confidence": "high",
                "locked": True,
                "evidence": "Extracted from protocol document",
                "source": "protocol_extraction"
            },
            "phase": {
                "answer": "Phase II",
                "confidence": "high",
                "locked": True,
                "evidence": "Extracted from protocol document",
                "source": "protocol_extraction"
            },
            "sponsor": {
                "answer": "Pharma Company Inc",
                "confidence": "high",
                "locked": True,
                "evidence": "Extracted from protocol document",
                "source": "protocol_extraction"
            },
            "access_to_population": {
                "answer": "Yes",
                "confidence": "medium",
                "locked": False,
                "evidence": "Site specializes in: NASH, Hepatology, GI Disorders",
                "rationale": "Protocol indication 'NASH' matches site experience"
            },
            "special_equipment": {
                "answer": "Yes",
                "confidence": "high",
                "locked": True,
                "evidence": "All required equipment available",
                "rationale": "Site equipment inventory confirms availability"
            },
            "time_recruitment": {
                "answer": "",
                "confidence": "manual",
                "locked": False,
                "evidence": "Site coordinator input required",
                "prompt": "Estimate hours for 45 patients",
                "helper_text": "Consider your typical recruitment rate and methods"
            }
        },
        "completion_stats": {
            "total_questions": 25,
            "auto_filled": 18,
            "high_confidence": 12,
            "locked_answers": 8,
            "manual_required": 7,
            "completion_percentage": 72,
            "estimated_time_saved_minutes": 35
        }
    }