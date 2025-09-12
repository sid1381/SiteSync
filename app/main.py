from fastapi import FastAPI
from app.routes import sites
from app.routes import demo  

app = FastAPI(title="SiteSync API")

@app.get("/health")
def health():
    return {"status": "ok"}

app.include_router(sites.router)
app.include_router(demo.router)  
