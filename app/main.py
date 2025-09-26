from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import sites, demo, protocols, drafts, whatif, feasibility
from app.routes import llm

app = FastAPI(title="SiteSync API - Clinical Research Feasibility Platform")

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

@app.get("/health")
def health():
    return {"status": "ok"}
