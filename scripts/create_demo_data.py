#!/usr/bin/env python3
"""
Create comprehensive demo data for SiteSync
Includes realistic site profiles and test scenarios
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db import engine, get_session
from app import models
from datetime import datetime

def create_demo_sites(db: Session):
    """Create demo site profiles with realistic data"""

    # Valley Medical Research - NASH/Hepatology specialist site
    valley_site = models.Site(
        name="Valley Medical Research",
        address="123 Research Blvd, Phoenix, AZ 85001",
        emr="Epic",
        notes="Leading research site specializing in NASH, hepatology, and gastroenterology studies"
    )
    db.add(valley_site)
    db.commit()
    db.refresh(valley_site)

    # Add site equipment
    equipment_items = [
        {"label": "MRI 1.5T", "model": "GE Signa", "modality": "MRI", "count": 1, "specs": {"tesla": 1.5, "contrast_capable": True}},
        {"label": "CT Scanner", "model": "Siemens SOMATOM", "modality": "CT", "count": 1, "specs": {"slice_count": 64}},
        {"label": "Ultrasound", "model": "Philips EPIQ", "modality": "Ultrasound", "count": 2, "specs": {"doppler": True}},
        {"label": "Fibroscan", "model": "EchoSens FibroScan", "modality": "Elastography", "count": 1, "specs": {"cap_measurement": True}},
        {"label": "ECG Machine", "model": "GE MAC 5000", "modality": "ECG", "count": 3, "specs": {"12_lead": True}},
        {"label": "Centrifuge", "model": "Eppendorf 5804R", "modality": "Lab", "count": 2, "specs": {"refrigerated": True}},
        {"label": "Freezer -80C", "model": "Thermo Scientific", "modality": "Storage", "count": 1, "specs": {"temperature": -80}}
    ]

    for item in equipment_items:
        equipment = models.SiteEquipment(
            site_id=valley_site.id,
            label=item["label"],
            model=item["model"],
            modality=item["modality"],
            count=item["count"],
            specs=item["specs"]
        )
        db.add(equipment)

    # Add site staff
    staff_members = [
        {"role": "Principal Investigator", "fte": 0.3, "certifications": "Board Certified Gastroenterologist, GCP Certified", "experience_years": 15},
        {"role": "Study Coordinator", "fte": 1.0, "certifications": "ACRP-CP, GCP Certified", "experience_years": 8},
        {"role": "Research Nurse", "fte": 0.8, "certifications": "RN, CCRC", "experience_years": 12},
        {"role": "Data Manager", "fte": 0.5, "certifications": "CCDM, GCP Certified", "experience_years": 6},
        {"role": "Regulatory Specialist", "fte": 0.4, "certifications": "RAC, GCP Certified", "experience_years": 10}
    ]

    for staff in staff_members:
        staff_member = models.SiteStaff(
            site_id=valley_site.id,
            role=staff["role"],
            fte=staff["fte"],
            certifications=staff["certifications"],
            experience_years=staff["experience_years"]
        )
        db.add(staff_member)

    # Add site history
    history_entries = [
        {"indication": "NASH Phase II", "phase": "Phase II", "enrollment_rate": 2.5, "startup_days": 45, "completed": True, "n_trials": 3},
        {"indication": "NASH Phase III", "phase": "Phase III", "enrollment_rate": 3.2, "startup_days": 38, "completed": True, "n_trials": 2},
        {"indication": "Hepatitis B", "phase": "Phase III", "enrollment_rate": 1.8, "startup_days": 52, "completed": True, "n_trials": 1},
        {"indication": "Liver Fibrosis", "phase": "Phase II", "enrollment_rate": 2.1, "startup_days": 41, "completed": False, "n_trials": 1},
        {"indication": "Gastroenterology Device", "phase": "Device", "enrollment_rate": 1.5, "startup_days": 35, "completed": True, "n_trials": 2}
    ]

    for history in history_entries:
        history_entry = models.SiteHistory(
            site_id=valley_site.id,
            indication=history["indication"],
            phase=history["phase"],
            enrollment_rate=history["enrollment_rate"],
            startup_days=history["startup_days"],
            completed=history["completed"],
            n_trials=history["n_trials"]
        )
        db.add(history_entry)

    # Add patient capabilities
    patient_capabilities = [
        {
            "indication_code": "K76.0",
            "indication_label": "NASH",
            "age_min_years": 18,
            "age_max_years": 75,
            "sex": "all",
            "annual_eligible_patients": 450,
            "notes": "Large NASH patient population, strong hepatology referral network",
            "evidence_url": "https://example.com/nash-population-data"
        },
        {
            "indication_code": "K73.0",
            "indication_label": "Liver Fibrosis",
            "age_min_years": 21,
            "age_max_years": 80,
            "sex": "all",
            "annual_eligible_patients": 320,
            "notes": "Established fibrosis screening program",
            "evidence_url": None
        },
        {
            "indication_code": "B18",
            "indication_label": "Chronic Hepatitis",
            "age_min_years": 18,
            "age_max_years": 70,
            "sex": "all",
            "annual_eligible_patients": 180,
            "notes": "Active hepatitis B and C treatment programs",
            "evidence_url": None
        }
    ]

    for capability in patient_capabilities:
        patient_cap = models.SitePatientCapability(
            site_id=valley_site.id,
            indication_code=capability["indication_code"],
            indication_label=capability["indication_label"],
            age_min_years=capability["age_min_years"],
            age_max_years=capability["age_max_years"],
            sex=capability["sex"],
            annual_eligible_patients=capability["annual_eligible_patients"],
            notes=capability["notes"],
            evidence_url=capability["evidence_url"]
        )
        db.add(patient_cap)

    # Add site truth fields (normalized capabilities for scoring)
    truth_fields = [
        {"key": "equipment.mri_tesla", "value": "1.5", "unit": "Tesla"},
        {"key": "equipment.ct_scanner", "value": "true", "unit": None},
        {"key": "equipment.ultrasound", "value": "true", "unit": None},
        {"key": "equipment.fibroscan", "value": "true", "unit": None},
        {"key": "equipment.freezer_minus80", "value": "true", "unit": None},
        {"key": "staff.pi_fte", "value": "0.3", "unit": "FTE"},
        {"key": "staff.coordinator_fte", "value": "1.0", "unit": "FTE"},
        {"key": "staff.nurse_fte", "value": "0.8", "unit": "FTE"},
        {"key": "staff.total_research_fte", "value": "2.9", "unit": "FTE"},
        {"key": "emr.vendor", "value": "Epic", "unit": None},
        {"key": "history.nash_trials_3y", "value": "5", "unit": "trials"},
        {"key": "history.avg_startup_days", "value": "42", "unit": "days"},
        {"key": "history.avg_enrollment_rate", "value": "2.2", "unit": "patients/month"},
        {"key": "patients.nash_annual_eligible", "value": "450", "unit": "patients"},
        {"key": "patients.liver_annual_eligible", "value": "500", "unit": "patients"},
        {"key": "patients.age_range", "value": "18-80", "unit": None},
        {"key": "indications", "value": "NASH, Liver Fibrosis, Hepatitis B, Gastroenterology", "unit": None},
        {"key": "certifications.gcp_compliant", "value": "true", "unit": None},
        {"key": "certifications.acrp_coordinator", "value": "true", "unit": None}
    ]

    for field in truth_fields:
        truth_field = models.SiteTruthField(
            site_id=valley_site.id,
            key=field["key"],
            value=field["value"],
            unit=field["unit"],
            evidence_required=False
        )
        db.add(truth_field)

    db.commit()
    return valley_site

def create_demo_protocols(db: Session):
    """Create demo protocols for testing"""

    # NASH Phase II Protocol
    nash_protocol = models.Protocol(
        name="A Phase II Study of XYZ-123 in Advanced NASH",
        sponsor="BioPharma Research Inc",
        disease="NASH",
        phase="Phase II",
        nct_id="NCT05123456",
        notes="Double-blind, placebo-controlled study evaluating XYZ-123 in patients with advanced NASH"
    )
    db.add(nash_protocol)
    db.commit()
    db.refresh(nash_protocol)

    # Add requirements for NASH protocol
    nash_requirements = [
        {"key": "equipment.fibroscan", "op": "==", "value": "true", "weight": 5, "type": "objective", "source_question": "Is Fibroscan available?"},
        {"key": "equipment.mri_tesla", "op": ">=", "value": "1.5", "weight": 4, "type": "objective", "source_question": "MRI capability required?"},
        {"key": "patients.nash_annual_eligible", "op": ">=", "value": "200", "weight": 5, "type": "objective", "source_question": "Access to NASH population?"},
        {"key": "staff.coordinator_fte", "op": ">=", "value": "0.8", "weight": 4, "type": "objective", "source_question": "Adequate coordinator time?"},
        {"key": "emr.vendor", "op": "in", "value": "[\"Epic\",\"Cerner\",\"AllScripts\"]", "weight": 2, "type": "objective", "source_question": "Compatible EMR?"},
        {"key": "history.nash_trials_3y", "op": ">=", "value": "1", "weight": 4, "type": "objective", "source_question": "NASH experience?"},
        {"key": "subjective.recruitment_strategy", "op": "n/a", "value": None, "weight": 3, "type": "subjective", "source_question": "Describe recruitment strategy for NASH patients"},
        {"key": "subjective.retention_plan", "op": "n/a", "value": None, "weight": 3, "type": "subjective", "source_question": "Patient retention plan for 48-week study"}
    ]

    for req in nash_requirements:
        requirement = models.ProtocolRequirement(
            protocol_id=nash_protocol.id,
            key=req["key"],
            op=req["op"],
            value=req["value"],
            weight=req["weight"],
            type=req["type"],
            source_question=req["source_question"]
        )
        db.add(requirement)

    # Oncology Phase III Protocol
    oncology_protocol = models.Protocol(
        name="Phase III Study of ABC-789 in Advanced Lung Cancer",
        sponsor="MegaPharma Global",
        disease="Non-Small Cell Lung Cancer",
        phase="Phase III",
        nct_id="NCT05789012",
        notes="Randomized, double-blind study comparing ABC-789 vs standard of care"
    )
    db.add(oncology_protocol)
    db.commit()
    db.refresh(oncology_protocol)

    # Add requirements for oncology protocol
    onc_requirements = [
        {"key": "equipment.ct_scanner", "op": "==", "value": "true", "weight": 5, "type": "objective", "source_question": "CT scanner available?"},
        {"key": "patients.oncology_annual_eligible", "op": ">=", "value": "100", "weight": 5, "type": "objective", "source_question": "Access to lung cancer patients?"},
        {"key": "staff.total_research_fte", "op": ">=", "value": "2.0", "weight": 4, "type": "objective", "source_question": "Adequate research staff?"},
        {"key": "certifications.oncology_experience", "op": "==", "value": "true", "weight": 3, "type": "objective", "source_question": "Oncology research experience?"},
        {"key": "subjective.enrollment_feasibility", "op": "n/a", "value": None, "weight": 4, "type": "subjective", "source_question": "Enrollment feasibility for 150 patients over 18 months"}
    ]

    for req in onc_requirements:
        requirement = models.ProtocolRequirement(
            protocol_id=oncology_protocol.id,
            key=req["key"],
            op=req["op"],
            value=req["value"],
            weight=req["weight"],
            type=req["type"],
            source_question=req["source_question"]
        )
        db.add(requirement)

    db.commit()
    return nash_protocol, oncology_protocol

def main():
    """Create all demo data"""
    print("Creating SiteSync demo data...")

    # Create database session
    db = next(get_session())

    try:
        # Create demo site
        print("Creating Valley Medical Research site...")
        valley_site = create_demo_sites(db)
        print(f"✅ Created site: {valley_site.name} (ID: {valley_site.id})")

        # Create demo protocols
        print("Creating demo protocols...")
        nash_protocol, oncology_protocol = create_demo_protocols(db)
        print(f"✅ Created NASH protocol: {nash_protocol.name} (ID: {nash_protocol.id})")
        print(f"✅ Created Oncology protocol: {oncology_protocol.name} (ID: {oncology_protocol.id})")

        print("\n🎉 Demo data creation completed!")
        print("\nDemo Site Details:")
        print(f"Site ID: {valley_site.id}")
        print(f"Site Name: {valley_site.name}")
        print(f"EMR: {valley_site.emr}")
        print(f"Equipment count: {len(db.query(models.SiteEquipment).filter(models.SiteEquipment.site_id == valley_site.id).all())}")
        print(f"Staff count: {len(db.query(models.SiteStaff).filter(models.SiteStaff.site_id == valley_site.id).all())}")
        print(f"Truth fields count: {len(db.query(models.SiteTruthField).filter(models.SiteTruthField.site_id == valley_site.id).all())}")

        print(f"\nNASH Protocol ID: {nash_protocol.id}")
        print(f"Oncology Protocol ID: {oncology_protocol.id}")

        print("\n🚀 Ready for testing! Try these API calls:")
        print(f"GET http://localhost:8000/sites/{valley_site.id}/truth")
        print(f"POST http://localhost:8000/protocols/{nash_protocol.id}/score?site_id={valley_site.id}")
        print(f"POST http://localhost:8000/feasibility/process-protocol (with PDF upload)")

    except Exception as e:
        print(f"❌ Error creating demo data: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()