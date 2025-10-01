from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import sites, demo, protocols, drafts, whatif, feasibility
from app.routes import llm, surveys, site_profile
from app.config import settings
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="SiteSync API - Clinical Research Feasibility Platform")

# Log startup configuration
logger.info("=" * 80)
logger.info("🚀 SiteSync Clinical Research Feasibility Platform Starting")
logger.info(f"📦 Configured LLM Model: {settings.LLM_MODEL}")
logger.info(f"🔧 LLM Provider: {settings.LLM_PROVIDER}")
logger.info(f"⚙️  Environment: {settings.ENV}")
logger.info("=" * 80)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router)
app.include_router(protocols.router)
app.include_router(demo.router)
app.include_router(drafts.router)
app.include_router(whatif.router)
app.include_router(feasibility.router)
app.include_router(llm.router)
app.include_router(surveys.router)
app.include_router(site_profile.router)

@app.on_event("startup")
async def startup_event():
    """Log startup information"""
    logger.info("✅ SiteSync API ready to accept requests")
    logger.info(f"🤖 AI Model: {settings.LLM_MODEL} (with automatic fallback to {settings.LLM_FALLBACK_MODEL})")

@app.get("/health")
def health():
    return {
        "status": "ok",
        "model": settings.LLM_MODEL,
        "provider": settings.LLM_PROVIDER
    }
