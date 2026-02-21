from __future__ import annotations

from fastapi import APIRouter, Query, HTTPException
from .config import get_settings
from .ebay_client import EbayClient
from .transform import normalize_search_response, normalize_item_details

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


@router.get("/item/{item_id:path}")
def api_item_details(item_id: str):
    # item_id містить "|" тому path
    try:
        payload = _client_instance().get_item(item_id=item_id)
        return normalize_item_details(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))