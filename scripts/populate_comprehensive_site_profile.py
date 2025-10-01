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
    Create City Hospital Clinical Research Unit with COMPREHENSIVE mock data
    This profile FIXES ALL CRITICAL GAPS for UAB survey completion:
    - Hepatology PI (Dr. Jane Doe)
    - FibroScan device
    - 1200 NASH patients
    - PK processing capability
    - -80C freezer
    """

    comprehensive_profile = {
        "population_capabilities": {
            "age_groups_treated": ["Pediatric (12+)", "Adult", "Geriatric"],
            "annual_patient_volume": 50000,
            "therapeutic_areas": [
                "Gastroenterology (Hepatology)",
                "Endocrinology",
                "Cardiology",
                "Oncology",
                "Infectious Disease",
                "Neurology"
            ],
            "patient_population": {
                "annual_patient_visits": 50000,
                "available_patients_by_condition": {
                    "NASH (Non-alcoholic Steatohepatitis)": 1200,
                    "Type 2 Diabetes": 5000,
                    "Obesity (BMI > 30)": 8000,
                    "NAFLD (Non-alcoholic Fatty Liver Disease)": 1500,
                    "Chronic Hepatitis C": 300,
                    "Hepatocellular Carcinoma": 100
                }
            },
            "special_populations": "Diverse urban population; 30% elderly, 20% pediatric",
            "common_languages": ["English", "Spanish"]
        },
        "staff_and_experience": {
            "principal_investigator": {
                "name": "Dr. Jane Doe",
                "specialty": "Hepatology",
                "years_experience": 20,
                "trials_conducted": 50,
                "board_certifications": ["Internal Medicine", "Gastroenterology"],
                "gcp_training_current": True
            },
            "sub_investigators": [
                {
                    "name": "Dr. John Smith",
                    "specialty": "Endocrinology",
                    "years_experience": 15,
                    "gcp_training_current": True
                },
                {
                    "name": "Dr. Alan Brown",
                    "specialty": "Radiology",
                    "years_experience": 10,
                    "gcp_training_current": True
                }
            ],
            "study_coordinators": {
                "count": 4,
                "experience": "Each coordinator has 5+ years experience",
                "certifications": ["ACRP-CCRC", "SOCRA-CCRP"],
                "gcp_training_current": True,
                "IATA_certified": 3
            },
            "research_nurses": {
                "count": 2,
                "roles": "Infusion nurses for IV dosing visits",
                "ALS_certified": True,
                "gcp_training_current": True
            },
            "pharmacist": {
                "available": True,
                "roles": "On-site investigational drug pharmacist",
                "experience": "10 years handling investigational products, including biologics",
                "gcp_training_current": True
            },
            "lab_technician": {
                "available": True,
                "roles": "Certified phlebotomist/lab tech for sample processing",
                "IATA_certified": True
            },
            "regulatory_specialist": {
                "available": True,
                "roles": "Handles IRB submissions, regulatory documents",
                "experience": "8 years in clinical research compliance"
            }
        },
        "facilities_and_equipment": {
            "laboratory": {
                "on_site_lab": True,
                "clia_certified": True,
                "capabilities": ["hematology", "chemistry", "coagulation", "PK processing"],
                "sample_processing": "Refrigerated centrifuge on-site, -80°C freezer for samples, dry ice available"
            },
            "imaging": {
                "CT": True,
                "MRI": True,
                "DXA": True,
                "Ultrasound": True,
                "FibroScan": True,
                "notes": "Full radiology department on-site; FibroScan device available in hepatology clinic"
            },
            "cardiology": {
                "ECG": "12-lead ECG on-site, ECG machine available",
                "echocardiogram": True,
                "holter_monitor": True,
                "notes": "Cardiology support available for QT prolongation monitoring if needed"
            },
            "infusion": {
                "infusion_chairs": 4,
                "infusion_beds": 2,
                "IV_pumps": True,
                "staffed_by": "Certified infusion nurses and physicians on-call"
            },
            "procedure_rooms": {
                "count": 2,
                "capabilities": "Endoscopy suite for biopsies and minor procedures",
                "emergency_equipment": "Crash cart, ACLS-trained staff on-site"
            },
            "pharmacy": {
                "investigational_drug_storage": {
                    "ambient": True,
                    "refrigerated_2_8C": True,
                    "freezer_minus20C": True,
                    "freezer_minus80C": True
                },
                "temperature_monitoring": "Continuous monitoring with alarm and backup power",
                "blinded_drug_handling": "Pharmacist and staff experienced in double-blind trial procedures"
            },
            "monitoring_space": {
                "available": True,
                "description": "Dedicated workspace for sponsor monitors with high-speed internet"
            }
        },
        "operational_capabilities": {
            "inpatient_capability": True,
            "outpatient_clinic": True,
            "overnight_stay": "Available via hospital research unit if needed",
            "ethics_committee": "Local IRB (meets bi-weekly) or central IRB reliance available",
            "average_startup_time_days": 45,
            "contract_budget_negotiation": "Dedicated contracts team, typically 4-6 weeks turnaround",
            "remote_data_capture": "Experience with multiple EDC systems (e.g., Medidata Rave, InForm)",
            "remote_monitoring": True,
            "daily_visit_capacity": 8,
            "recruitment_methods": ["EMR database query", "community outreach", "referrals"],
            "screen_fail_rate": "Approximately 30% (varies by protocol)",
            "retention_rate": "Over 90% of enrolled patients complete studies"
        },
        "historical_performance": {
            "studies_completed_last_5_years": 45,
            "patients_enrolled_last_5_years": 300,
            "phase_experience": {
                "Phase_I": True,
                "Phase_II": True,
                "Phase_III": True,
                "Phase_IV": True
            },
            "therapeutic_experience": [
                "NASH",
                "Type 2 Diabetes",
                "Obesity",
                "Cardiovascular outcomes",
                "Oncology (solid tumors)",
                "Infectious Disease (HCV/HIV)"
            ],
            "top_sponsors_worked_with": ["PharmaCo A", "Biotech B", "GlobalPharma C", "CRO X"],
            "audit_history": "Multiple sponsor audits with no major findings; one FDA audit in 2019 (no 483s issued)"
        },
        "compliance_and_training": {
            "central_irb_used": True,
            "local_irb_used": True,
            "average_irb_approval_time_days": 30,
            "gcp_training": "All staff have current CITI GCP certification (renewed every 2 years)",
            "iata_training": "At least 5 staff with current IATA certification for shipping hazardous materials",
            "gdpr_compliance": "Patient data handled per HIPAA and GDPR guidelines as applicable",
            "sops": "Comprehensive SOPs for all study procedures (e.g. informed consent, AE reporting, IP handling)",
            "quality_assurance": "Internal QA audits conducted quarterly to ensure compliance"
        },
        "subjective_notes": {
            "sponsor_feedback": "Sponsors consistently praise the site's recruitment and data quality; noted as a high-enrolling site",
            "complex_protocol_experience": "Successfully conducted complex trials (e.g., adaptive designs, intensive PK sampling, device integrations)",
            "notable_challenges_overcome": "Experience in managing high screen failure indications (e.g., NASH) by broad outreach and pre-screening",
            "staff_commitment": "Dedicated team with low turnover, ensuring consistency across long trials"
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
        site.name = "City Hospital Clinical Research Unit"

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

        # Calculate total investigators (PI + sub-investigators)
        pi_count = 1 if site.staff_and_experience.get('principal_investigator') else 0
        sub_inv_count = len(site.staff_and_experience.get('sub_investigators', []))
        total_investigators = pi_count + sub_inv_count

        print(f"👥 Investigators: {total_investigators} (1 PI, {sub_inv_count} sub-investigators)")
        print(f"👥 PI: {site.staff_and_experience['principal_investigator']['name']} ({site.staff_and_experience['principal_investigator']['specialty']})")
        print(f"👨‍⚕️ Coordinators: {site.staff_and_experience['study_coordinators']['count']}")
        print(f"🔬 FibroScan: {site.facilities_and_equipment['imaging']['FibroScan']}")
        print(f"🧪 PK Processing: {'PK processing' in site.facilities_and_equipment['laboratory']['capabilities']}")
        print(f"📈 Annual patient volume: {site.population_capabilities['annual_patient_volume']:,}")
        print(f"🏥 NASH patients: {site.population_capabilities['patient_population']['available_patients_by_condition']['NASH (Non-alcoholic Steatohepatitis)']:,}")
        print(f"📋 Studies in 5 years: {site.historical_performance['studies_completed_last_5_years']}")

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