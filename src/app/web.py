from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from .config import get_settings
from .ebay_client import EbayClient
from .transform import normalize_search_response

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="templates")

_client: EbayClient | None = None

def _client_instance() -> EbayClient:
    global _client
    if _client is None:
        _client = EbayClient(get_settings())
    return _client

@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    s = get_settings()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "defaults": {"q": "iphone", "limit": 20, "page": 1, "sort": ""}, "env": s.ebay_env, "marketplace": s.marketplace_id},
    )

@router.get("/ui/search", response_class=HTMLResponse)
def ui_search(
    request: Request,
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
):
    offset = (page - 1) * limit
    payload = _client_instance().search(q=q, limit=limit, offset=offset, sort=(sort or None))
    data = normalize_search_response(payload)

    total = int(data.get("total") or 0)
    total_pages = max(1, int(ceil(total / max(1, limit))))

    s = get_settings()
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "items": data.get("items", []),
            "meta": {
                "q": q,
                "limit": limit,
                "page": page,
                "sort": sort or "",
                "total": total,
                "total_pages": total_pages,
                "prev_page": max(1, page - 1),
                "next_page": min(total_pages, page + 1),
                "offset": offset,
                "env": s.ebay_env,
                "marketplace": s.marketplace_id,
            },
        },
    )
