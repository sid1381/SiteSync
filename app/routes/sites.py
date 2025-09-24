from fastapi import APIRouter, Depends, HTTPException
from typing import List
from sqlalchemy.orm import Session
from app.db import get_session, Base, engine
from app import models
from app.schemas.site import SiteCreate, SiteOut, TruthFieldUpsert, TruthFieldOut

# Sprint-0 convenience: create tables at startup (we'll add proper migrations later)
Base.metadata.create_all(bind=engine)

router = APIRouter(prefix="/sites", tags=["sites"])

@router.post("/", response_model=SiteOut)
def create_site(payload: SiteCreate, db: Session = Depends(get_session)):
    site = models.Site(name=payload.name, address=payload.address, emr=payload.emr, notes=payload.notes)
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
