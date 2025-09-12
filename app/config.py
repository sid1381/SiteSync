from pydantic import BaseModel
from dotenv import load_dotenv
import os

# Load variables from .env (docker passes ENV_FILE=.env)
load_dotenv(os.getenv("ENV_FILE", ".env"))

class Settings(BaseModel):
    DATABASE_URL: str = os.getenv("DATABASE_URL")

settings = Settings()
