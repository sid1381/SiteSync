#!/usr/bin/env python3
"""
Populate comprehensive site profile for UAB-style surveys with 90%+ completion
"""

import json
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db import get_session_direct
from app import models

def create_comprehensive_site_profile():
    """
    Create City Hospital Clinical Research Center with comprehensive mock data
    """

    comprehensive_profile = {
        "population_capabilities": {
            "age_groups_treated": ["Pediatric", "Adult", "Geriatric"],
            "annual_patient_volume": 15000,
            "common_health_conditions": [
                "Diabetes",
                "Hypertension",
                "Cardiovascular Disease",
                "Oncology (various cancers)",
                "Metabolic Disorders"
            ],
            "special_populations": "Diverse urban population; ~30% elderly, 20% pediatric patients",
            "common_languages": ["English", "Spanish"]
        },
        "staff_and_experience": {
            "investigators": {
                "count": 3,
                "specialties": ["Cardiology", "Oncology", "Endocrinology"],
                "average_years_experience": 12,
                "coverage": "At least one Sub-Investigator available for backup; PI or sub-I on-call 24/7"
            },
            "coordinators": {
                "count": 5,
                "average_years_experience": 6,
                "certifications": ["2 CCRP (ACRP)", "1 CCRC (SoCRA)"],
                "training": "All coordinators have current GCP and HSP training"
            },
            "other_staff": {
                "research_nurses": 2,
                "pharmacist": 1,
                "lab_technician": 1,
                "regulatory_specialist": 1
            }
        },
        "facilities_and_equipment": {
            "imaging": ["X-Ray", "Ultrasound", "CT (64-slice)", "MRI (1.5T)", "DEXA", "ECG"],
            "lab_capabilities": {
                "onsite_clinical_lab": True,
                "CLIA_certified": True,
                "sample_processing": "Centrifuge (refrigerated) available",
                "freezer_-20C": True,
                "freezer_-80C": True,
                "temperature_monitoring": True,
                "backup_power_for_freezers": True
            },
            "procedure_rooms": 4,
            "infusion_chairs": 4,
            "emergency_equipment": "Crash cart and defibrillator on-site",
            "calibration_schedule": "All medical equipment calibrated annually"
        },
        "operational_capabilities": {
            "inpatient_support": "Access to hospital inpatient units for overnight stays",
            "outpatient_clinic": "Dedicated outpatient research clinic with 4 exam rooms",
            "pharmacy": "On-site investigational pharmacy (temperature-controlled)",
            "departments_involved": ["Radiology", "Cardiology", "Pathology/Lab", "Pharmacy"],
            "data_systems": "CTMS (OnCore), EHR (Epic), EDC experience (Medidata Rave, Oracle InForm)",
            "monitoring_accommodations": "Dedicated CRA workspace with internet access",
            "record_storage": "Secure storage for study records (locked cabinets, limited-access servers)"
        },
        "historical_performance": {
            "studies_conducted_last_5_years": 45,
            "studies_by_phase": {"Phase I": 2, "Phase II": 10, "Phase III": 20, "Phase IV": 5},
            "therapeutic_experience": {"Cardiology": 10, "Oncology": 8, "Endocrinology": 5},
            "current_active_studies": 6,
            "sponsor_types_experience": ["Industry (Pharma/CRO)", "NIH-funded", "Investigator-Initiated"],
            "enrollment_success_rate": "~85% of trials meet enrollment targets",
            "retention_rate": "~95% of enrolled participants retained",
            "protocol_deviation_rate": "<2% (minor deviations only)",
            "average_query_resolution_time": "3 days"
        },
        "compliance_and_training": {
            "IRB_review": "Local Institutional IRB; can use central IRB (avg 4 weeks)",
            "GCP_training": "All staff GCP-certified (renewed every 2-3 years)",
            "human_subjects_training": "All staff completed HSP training (CITI Program)",
            "IATA_certification": "Staff certified for hazardous materials shipping",
            "SOPs": "SOPs in place for all clinical research processes",
            "audit_history": "FDA inspection (2019) no Form 483s; 5 sponsor audits no critical findings"
        }
    }

    return comprehensive_profile

def populate_comprehensive_site():
    """
    Always populate site 1 (City Hospital) with comprehensive profile data
    """
    print("🚀 Starting Comprehensive Site Profile Population...")

    db = next(get_session_direct())

    try:
        # ALWAYS get site 1 (guaranteed to exist from demo data)
        site = db.get(models.Site, 1)
        if not site:
            print("❌ Site 1 not found - this should never happen!")
            return False

        # Update site name and comprehensive profile
        site.name = "City Hospital Clinical Research Center"

        comprehensive_profile = create_comprehensive_site_profile()

        # Populate JSONB fields
        site.population_capabilities = comprehensive_profile["population_capabilities"]
        site.staff_and_experience = comprehensive_profile["staff_and_experience"]
        site.facilities_and_equipment = comprehensive_profile["facilities_and_equipment"]
        site.operational_capabilities = comprehensive_profile["operational_capabilities"]
        site.historical_performance = comprehensive_profile["historical_performance"]
        site.compliance_and_training = comprehensive_profile["compliance_and_training"]

        # Calculate completeness (all major sections filled = 100%)
        site.profile_completeness = 100.0
        site.last_updated = models.datetime.utcnow()

        db.commit()

        print("✅ Site profile updated successfully!")
        print(f"📊 Profile completion: {site.profile_completeness}%")
        print(f"🏥 Site name: {site.name}")
        print(f"👥 Investigators: {site.staff_and_experience['investigators']['count']}")
        print(f"👨‍⚕️ Coordinators: {site.staff_and_experience['coordinators']['count']}")
        print(f"🔬 Equipment items: {len(site.facilities_and_equipment['imaging'])}")
        print(f"📈 Annual patient volume: {site.population_capabilities['annual_patient_volume']:,}")
        print(f"📋 Studies in 5 years: {site.historical_performance['studies_conducted_last_5_years']}")

        print("\n🎯 Comprehensive site profile populated successfully!")
        print("   Ready for UAB survey testing with 90%+ completion target.")

        return True

    except Exception as e:
        print(f"❌ Error populating site profile: {e}")
        db.rollback()
        return False

    finally:
        db.close()

if __name__ == "__main__":
    success = populate_comprehensive_site()
    sys.exit(0 if success else 1)