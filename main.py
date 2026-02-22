from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.app.api import router as api_router
from src.app.web import router as web_router
from src.app.config import get_settings
import src.app.api as api_mod

app = FastAPI(title="eBay Live Search", version="1.0.0")

app.mount("/static", StaticFiles(directory="static"), name="static")  # /static/* - папка static

app.include_router(web_router) # web-роутер (/, /ui/...)
app.include_router(api_router) # api-роутер (/api/...)


@app.get("/health") # проста перевірка, що сервіс живий
def health():
    s = get_settings()  # підтягує env/marketplace та перевіряє EBAY_CLIENT_ID/SECRET
    return {
        "ok": True,
        "env": s.ebay_env,
        "marketplace": s.marketplace_id,
        "api_file": api_mod.__file__, # шлях до api.py
    }


@app.get("/debug/routes") # дебаг: показати всі шляхи, які реально існують в app.routes
def debug_routes():
    return sorted({r.path for r in app.routes}) # унікальні paths, відсортовані