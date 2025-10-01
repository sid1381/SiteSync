from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Load variables from .env (docker passes ENV_FILE=.env)
load_dotenv(os.getenv("ENV_FILE", ".env"))

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+psycopg2://sitesync:password@db:5432/sitesync")
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "sitesync")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_FALLBACK_MODEL: str = os.getenv("LLM_FALLBACK_MODEL", "gpt-4o")
    LLM_TIMEOUT_SECS: int = int(os.getenv("LLM_TIMEOUT_SECS", "20"))
    ENV: str = os.getenv("ENV", "dev")

settings = Settings()
