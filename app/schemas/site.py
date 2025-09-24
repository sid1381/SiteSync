from pydantic import BaseModel
from typing import Optional

class SiteCreate(BaseModel):
    name: str
    address: Optional[str] = None
    emr: Optional[str] = None
    notes: Optional[str] = None

class SiteOut(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    emr: Optional[str] = None
    notes: Optional[str] = None
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