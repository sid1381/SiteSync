from fastapi import FastAPI
from app.routes import sites, demo, protocols, drafts
from app.routes import llm   # <-- add this line

app = FastAPI(title="SiteSync API")
app.include_router(sites.router)
app.include_router(protocols.router)
app.include_router(demo.router)
app.include_router(drafts.router)
app.include_router(llm.router)  # <-- add this line

@app.get("/health")
def health():
    return {"status": "ok"}
