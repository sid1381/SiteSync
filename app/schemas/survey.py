from pydantic import BaseModel
from typing import Optional
from datetime import date

class SurveyCreate(BaseModel):
    site_id: int
    sponsor_name: str
    study_name: str
    study_type: str
    nct_number: Optional[str] = None
    due_date: Optional[date] = None