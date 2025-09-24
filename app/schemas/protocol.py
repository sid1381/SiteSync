from pydantic import BaseModel, Field
from typing import List, Optional, Any

class ProtocolCreate(BaseModel):
    name: str
    sponsor: Optional[str] = None
    disease: Optional[str] = None
    phase: Optional[str] = None
    nct_id: Optional[str] = None
    notes: Optional[str] = None

class RequirementIn(BaseModel):
    key: str
    op: str  # "==", ">=", "<=", ">", "<", "in", "n/a" (for subjective placeholders)
    value: Any = None
    weight: int = 1
    type: str = Field(default="objective", regex="^(objective|subjective)$")
    source_question: Optional[str] = None

class RequirementsListIn(BaseModel):
    requirements: List[RequirementIn]

class ProtocolOut(BaseModel):
    id: int
    name: str
    sponsor: Optional[str] = None
    disease: Optional[str] = None
    phase: Optional[str] = None
    nct_id: Optional[str] = None
    notes: Optional[str] = None
    class Config:
        from_attributes = True

class RequirementOut(BaseModel):
    id: int
    key: str
    op: str
    value: Optional[str] = None
    weight: int
    type: str
    source_question: Optional[str] = None
    class Config:
        from_attributes = True

class CtgovImportIn(BaseModel):
    nct_id: str = Field(regex=r"^NCT\d{8}$")

class CtgovImportOut(BaseModel):
    protocol_id: int
    protocol_name: str
    requirements_created: int
    message: str