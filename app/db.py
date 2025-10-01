from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings

# Connect SQLAlchemy to Postgres
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for our models
class Base(DeclarativeBase):
    pass

# FastAPI dependency: opens/closes a DB session per request
from typing import Generator

def get_session() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_session_direct():
    """Direct session for scripts"""
    yield SessionLocal()
