from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
from app.db import get_session, Base, engine
from app import models

# Sprint-0 convenience: create tables at startup (we'll add proper migrations later)
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/sites", tags=["sites"])

# Request/response schemas
class SiteCreate(BaseModel):
    name: str
    address: Optional[str] = None

class SiteOut(BaseModel):
    id: int
    name: str
    address: Optional[str] = None
    class Config:
        from_attributes = True  # Pydantic v2: allow ORM objects -> model

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

@router.post("/", response_model=SiteOut)
def create_site(payload: SiteCreate, db: Session = Depends(get_session)):
    site = models.Site(name=payload.name, address=payload.address)
    db.add(site)
    db.commit()
    db.refresh(site)
    return site

@router.get("/", response_model=List[SiteOut])
def list_sites(db: Session = Depends(get_session)):
    items = db.query(models.Site).order_by(models.Site.id.asc()).all()
    return items

@router.post("/{site_id}/truth", response_model=TruthFieldOut)
def upsert_truth(site_id: int, payload: TruthFieldUpsert, db: Session = Depends(get_session)):
    site = db.get(models.Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    tf = models.SiteTruthField(
        site_id=site_id,
        key=payload.key,
        value=payload.value,
        unit=payload.unit,
        evidence_required=payload.evidence_required,
    )
    db.add(tf)
    db.commit()
    db.refresh(tf)
    return tf

@router.get("/{site_id}/truth", response_model=List[TruthFieldOut])
def list_truth(site_id: int, db: Session = Depends(get_session)):
    items = db.query(models.SiteTruthField).filter(models.SiteTruthField.site_id == site_id).all()
    return items
