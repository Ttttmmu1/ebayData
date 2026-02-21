from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from .config import get_settings
from .ebay_client import EbayClient
from .transform import normalize_search_response

router = APIRouter(prefix="/api", tags=["api"])

_client: EbayClient | None = None

def _client_instance() -> EbayClient:
    global _client
    if _client is None:
        _client = EbayClient(get_settings())
    return _client

@router.get("/search")
def api_search(
    q: str = Query(..., min_length=1, description="Search keywords"),
    limit: int = Query(20, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str | None = Query(None, description="eBay sort string (optional)"),
):
    offset = (page - 1) * limit
    payload = _client_instance().search(q=q, limit=limit, offset=offset, sort=sort)
    return JSONResponse(normalize_search_response(payload))
