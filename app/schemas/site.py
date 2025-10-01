from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class SiteCreate(BaseModel):
    name: str

class SiteOut(BaseModel):
    id: int
    name: str
    population_capabilities: Optional[Dict[str, Any]] = {}
    staff_and_experience: Optional[Dict[str, Any]] = {}
    facilities_and_equipment: Optional[Dict[str, Any]] = {}
    operational_capabilities: Optional[Dict[str, Any]] = {}
    historical_performance: Optional[Dict[str, Any]] = {}
    compliance_and_training: Optional[Dict[str, Any]] = {}
    profile_completeness: Optional[float] = 0.0
    last_updated: Optional[datetime] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class TruthFieldUpsert(BaseModel):
    key: str
    value: str
    unit: Optional[str] = None
    evidence_required: bool = False

class TruthFieldOut(BaseModel):
    id: int
    key: str
    value: str
    unit: Optional[str] = None
    evidence_required: bool
    class Config:
        from_attributes = True