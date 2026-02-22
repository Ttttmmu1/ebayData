from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings

router = APIRouter(tags=["web"]) # роутер для веб-сторінок (UI)
templates = Jinja2Templates(directory="templates") # папка з HTML-шаблонами


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Головна сторінка (пошук)"""
    s = get_settings() # конфігурація

    # значення за замовчуванням для форми пошуку
    defaults = {"q": "iphone", "limit": 20, "page": 1}

    return templates.TemplateResponse(
        "index.html", # HTML шаблон
        {
            "request": request, # обов'язково для Jinja2
            "env": s.ebay_env, # sandbox / production
            "marketplace": s.marketplace_id, # EBAY_US тощо
            "defaults": defaults, # дефолтні значення форми
        },
    )

@router.get("/ui/search", response_class=HTMLResponse)
def ui_search(request: Request):
    """Alias для головної сторінки пошуку"""
    return index(request)  # просто викликає index()

@router.get("/ui/dataset", response_class=HTMLResponse)
def ui_dataset(request: Request):
    """Сторінка роботи з датасетом"""
    s = get_settings()  # конфігурація

    return templates.TemplateResponse(
        "dataset.html",  # HTML шаблон датасету
        {
            "request": request,
            "env": s.ebay_env, # середовище API
            "marketplace": s.marketplace_id, # marketplace
        },
    )