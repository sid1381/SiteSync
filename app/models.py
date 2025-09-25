from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db import Base

class Site(Base):
    __tablename__ = "sites"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    emr = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SiteTruthField(Base):
    __tablename__ = "site_truth_fields"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(128), nullable=False)
    value = Column(Text, nullable=False)
    unit = Column(String(32), nullable=True)
    evidence_required = Column(Boolean, default=False)

    site = relationship("Site")

class SiteEquipment(Base):
    __tablename__ = "site_equipment"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    label = Column(String(255), nullable=False)
    model = Column(String(255), nullable=True)
    modality = Column(String(100), nullable=True)
    count = Column(Integer, default=1)
    specs = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site")

class SiteStaff(Base):
    __tablename__ = "site_staff"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(100), nullable=False)
    fte = Column(Float, nullable=True)
    certifications = Column(Text, nullable=True)
    experience_years = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site")

class SiteHistory(Base):
    __tablename__ = "site_history"
    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)
    indication = Column(String(255), nullable=True)
    phase = Column(String(50), nullable=True)
    enrollment_rate = Column(Float, nullable=True)
    startup_days = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)
    n_trials = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    site = relationship("Site")

class Protocol(Base):
    __tablename__ = "protocols"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    sponsor = Column(String(255), nullable=True)
    disease = Column(String(255), nullable=True)
    phase = Column(String(50), nullable=True)
    nct_id = Column(String(32), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    requirements = relationship("ProtocolRequirement", back_populates="protocol", cascade="all, delete-orphan")

class ProtocolRequirement(Base):
    __tablename__ = "protocol_requirements"

    id = Column(Integer, primary_key=True, index=True)
    protocol_id = Column(Integer, ForeignKey("protocols.id", ondelete="CASCADE"), nullable=False)
    key = Column(String(128), nullable=False)       # e.g. "ct_scanners"
    op = Column(String(8), nullable=False)          # "==", ">=", "<=", ">", "<", "in"
    value = Column(Text, nullable=True)             # store as text; parse as number/list as needed
    weight = Column(Integer, nullable=False, default=1)
    type = Column(String(16), nullable=False, default="objective")  # "objective" | "subjective"
    source_question = Column(Text, nullable=True)   # original question text (for autofill rendering)

    protocol = relationship("Protocol", back_populates="requirements")

# --- NEW: Site Patient Capability (aggregate, no PHI) ---

class SitePatientCapability(Base):
    __tablename__ = "site_patient_capabilities"

    id = Column(Integer, primary_key=True, index=True)
    site_id = Column(Integer, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False)

    indication_code = Column(String(64), nullable=True)   # e.g., MeSH / ICD-10 code
    indication_label = Column(String(255), nullable=True) # human label

    age_min_years = Column(Integer, nullable=True)
    age_max_years = Column(Integer, nullable=True)
    sex = Column(String(8), nullable=True)  # "all" | "male" | "female"

    annual_eligible_patients = Column(Integer, nullable=True)

    notes = Column(Text, nullable=True)
    evidence_url = Column(Text, nullable=True)

    site = relationship("Site")

class FeasibilityAssessment(Base):
    __tablename__ = "feasibility_assessments"

    id = Column(Integer, primary_key=True)
    site_id = Column(Integer, ForeignKey("sites.id"), nullable=False)
    protocol_id = Column(Integer, ForeignKey("protocols.id"), nullable=False)
    overall_score = Column(Integer, nullable=True)
    completion_percentage = Column(Integer, nullable=True)
    time_saved_minutes = Column(Integer, nullable=True)
    status = Column(String(50), default="draft")  # draft, completed, submitted
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    site = relationship("Site")
    protocol = relationship("Protocol")

class FeasibilityResponse(Base):
    __tablename__ = "feasibility_responses"

    id = Column(Integer, primary_key=True)
    assessment_id = Column(Integer, ForeignKey("feasibility_assessments.id"), nullable=False)
    question_key = Column(String(128), nullable=False)
    answer_text = Column(Text, nullable=True)
    confidence = Column(String(20), nullable=True)  # high, medium, low, manual
    is_locked = Column(Boolean, default=False)
    evidence = Column(Text, nullable=True)
    rationale = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    assessment = relationship("FeasibilityAssessment")
