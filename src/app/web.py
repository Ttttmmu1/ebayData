from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    s = get_settings()
    defaults = {"q": "iphone", "limit": 20, "page": 1}
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "env": s.ebay_env,
            "marketplace": s.marketplace_id,
            "defaults": defaults,
        },
    )


@router.get("/ui/search", response_class=HTMLResponse)
def ui_search(request: Request):
    # alias for index
    return index(request)


@router.get("/ui/dataset", response_class=HTMLResponse)
def ui_dataset(request: Request):
    s = get_settings()
    return templates.TemplateResponse(
        "dataset.html",
        {
            "request": request,
            "env": s.ebay_env,
            "marketplace": s.marketplace_id,
        },
    )