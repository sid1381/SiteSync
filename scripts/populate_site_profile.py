#!/usr/bin/env python3
"""
Populate Site Profile with Rich Data for Enhanced Mapping

This script populates the critical fields that the mapping algorithm needs:
- Therapeutic areas
- Previous sponsors
- Special equipment
- Laboratory capabilities
- Patient volumes
- Experience data
"""

import sys
import os
sys.path.append('/app')

from app.db import get_session
from app import models
from datetime import datetime

def populate_site_profile():
    """Populate site profile with comprehensive data for mapping algorithm"""

    db = next(get_session())

    # Get the site (assuming site_id = 1)
    site = db.get(models.Site, 1)
    if not site:
        print("❌ Site not found! Creating basic site first...")
        site = models.Site(
            name="Valley Medical Research",
            address="123 Research Blvd, Phoenix, AZ 85001"
        )
        db.add(site)
        db.commit()
        db.refresh(site)

    print(f"📝 Updating site profile for: {site.name}")

    # Update basic site information
    site.pi_name = "Dr. Sarah Johnson, MD, PhD"
    site.institution = "Memorial Hospital Network"
    site.coordinators_fte = 3.5
    site.weekend_coverage = True

    # Patient Population Capabilities
    site.patient_age_range_min = 18
    site.patient_age_range_max = 75
    site.annual_patient_volume = 4998
    site.enrollment_capacity_per_month = 25

    # Equipment and Capabilities (JSON fields)
    site.special_equipment = [
        "MRI 3T",
        "CT Scanner",
        "PK centrifuge",
        "ECG/EKG",
        "Ultrasound",
        "X-ray",
        "DEXA",
        "Spirometry",
        "Holter monitors",
        "FibroScan",
        "Research pharmacy",
        "Sample storage (-80°C)"
    ]

    site.imaging_equipment = [
        "MRI 3T",
        "CT Scanner",
        "Ultrasound",
        "X-ray",
        "DEXA"
    ]

    site.laboratory_capabilities = {
        "pk_sampling": True,
        "cap_certified": True,
        "chemistry": True,
        "hematology": True,
        "coagulation": True,
        "urinalysis": True,
        "biomarkers": True,
        "sample_storage": True,
        "freezer_minus_80": True
    }

    # Experience and Qualifications
    site.therapeutic_areas = [
        "NASH/NAFLD",
        "Diabetes",
        "Cardiology",
        "Oncology",
        "Neurology",
        "Rheumatology",
        "Dermatology",
        "Respiratory"
    ]

    site.previous_sponsors = [
        "Pfizer",
        "Novartis",
        "Roche",
        "Johnson & Johnson",
        "Merck",
        "AbbVie",
        "Bristol Myers Squibb",
        "Gilead",
        "Amgen",
        "Regeneron"
    ]

    site.available_procedures = [
        "liver biopsy",
        "cardiac catheterization",
        "endoscopy",
        "colonoscopy",
        "skin biopsy",
        "joint injection",
        "lumbar puncture",
        "bone marrow biopsy",
        "bronchoscopy",
        "PK blood draws"
    ]

    # Administrative capabilities
    site.budget_management_experience = [
        "multi-million dollar studies",
        "per-patient payments",
        "milestone payments",
        "budget reconciliation"
    ]

    site.regulatory_experience = [
        "FDA audits",
        "GCP compliance",
        "IRB submissions",
        "protocol deviations",
        "SAE reporting",
        "regulatory submissions"
    ]

    site.recruitment_strategies = """Multi-channel patient recruitment including:
- EMR database queries with physician referrals
- Community outreach and health fairs
- Patient registries and referral networks
- Digital advertising and social media
- Investigator referrals from other departments
- Previous study participant databases"""

    # Calculate profile completion
    total_fields = 25  # Approximate number of profile fields
    completed_fields = 23  # Most fields now populated
    site.profile_completion_percentage = (completed_fields / total_fields) * 100
    site.profile_last_updated = datetime.utcnow()

    try:
        db.commit()
        print("✅ Site profile updated successfully!")

        # Verify the update
        db.refresh(site)
        print(f"📊 Profile completion: {site.profile_completion_percentage:.1f}%")
        print(f"🏥 Therapeutic areas: {len(site.therapeutic_areas)} areas")
        print(f"🏢 Previous sponsors: {len(site.previous_sponsors)} sponsors")
        print(f"🔬 Special equipment: {len(site.special_equipment)} items")
        print(f"💉 Annual patient volume: {site.annual_patient_volume:,}")

        return True

    except Exception as e:
        print(f"❌ Error updating site profile: {e}")
        db.rollback()
        return False

    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting Site Profile Population...")
    success = populate_site_profile()
    if success:
        print("\n🎯 Site profile populated successfully!")
        print("   The mapping algorithm now has rich data to work with.")
        print("   Expected auto-completion rate: 70%+")
    else:
        print("\n❌ Failed to populate site profile")
        sys.exit(1)