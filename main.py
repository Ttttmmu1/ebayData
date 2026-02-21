from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.app.api import router as api_router
from src.app.web import router as web_router
from src.app.config import get_settings

app = FastAPI(title="eBay Live Search", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(web_router)
app.include_router(api_router)

@app.get("/health")
def health():
    s = get_settings()
    return {"ok": True, "env": s.ebay_env, "marketplace": s.marketplace_id}
