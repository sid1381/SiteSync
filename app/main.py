from fastapi import FastAPI
from app.routes import sites, demo, protocols, drafts, whatif
from app.routes import llm

app = FastAPI(title="SiteSync API")
app.include_router(sites.router)
app.include_router(protocols.router)
app.include_router(demo.router)
app.include_router(drafts.router)
app.include_router(whatif.router)
app.include_router(llm.router)

@app.get("/health")
def health():
    return {"status": "ok"}
