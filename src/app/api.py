from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse

from .config import get_settings
from .ebay_client import EbayClient
from .transform import normalize_search_response, normalize_item_details

from .analytics import compute_analytics
from .excel_export import build_excel

router = APIRouter(prefix="/api", tags=["api"])

_client: EbayClient | None = None


def _client_instance() -> EbayClient:
    global _client
    if _client is None:
        _client = EbayClient(get_settings())
    return _client


@router.get("/search")
def api_search(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
):
    offset = (page - 1) * limit
    payload = _client_instance().search(q=q, limit=limit, offset=offset, sort=(sort or None))
    return normalize_search_response(payload)


@router.get("/analytics")
def api_analytics(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
):
    offset = (page - 1) * limit
    payload = _client_instance().search(q=q, limit=limit, offset=offset, sort=(sort or None))
    norm = normalize_search_response(payload)

    return {
        "meta": {
            "q": q,
            "limit": norm.get("limit"),
            "offset": norm.get("offset"),
            "total": norm.get("total"),
            "sort": sort or "",
        },
        "analytics": compute_analytics(norm.get("items") or []),
    }


@router.get("/export")
def api_export_excel(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None),
):
    offset = (page - 1) * limit
    payload = _client_instance().search(q=q, limit=limit, offset=offset, sort=(sort or None))
    norm = normalize_search_response(payload)

    content = build_excel(
        query=q,
        items=norm.get("items") or [],
        total=norm.get("total"),
        limit=norm.get("limit"),
        offset=norm.get("offset"),
        sort=sort,
    )

    safe_q = "_".join([p for p in q.strip().split() if p])[:40] or "query"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ebay_{safe_q}_{ts}.xlsx"

    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"
    }

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/item/{item_id:path}")
def api_item_details(item_id: str):
    # item_id містить "|" тому path
    try:
        payload = _client_instance().get_item(item_id=item_id)
        return normalize_item_details(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))