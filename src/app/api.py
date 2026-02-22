from __future__ import annotations

from datetime import datetime
from urllib.parse import quote
import os

from fastapi import APIRouter, Query, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .config import get_settings
from .ebay_client import EbayClient
from .transform import normalize_search_response, normalize_item_details

from .analytics import compute_analytics
from .excel_export import build_excel

from .dataset_service import (
    compute_summary,
    read_preview,
    get_column_values,
    get_top_values,
    get_column_stats,
    set_uploaded_path,
    get_mode_text,
)
from .dataset_excel import build_filtered_excel, build_report_excel

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

    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.get("/item/{item_id:path}")
def api_item_details(item_id: str):
    try:
        payload = _client_instance().get_item(item_id=item_id)
        return normalize_item_details(payload)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------- Dataset API ----------------

@router.get("/dataset/summary")
def dataset_summary():
    return compute_summary()


@router.get("/dataset/preview")
def dataset_preview(
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
):
    return read_preview(offset=offset, limit=limit)


@router.get("/dataset/column")
def dataset_column(
    name: str = Query(..., min_length=1),
    limit: int = Query(5000, ge=100, le=20000),
):
    return {"name": name, "values": get_column_values(name=name, limit=limit)}


@router.get("/dataset/top")
def dataset_top(
    name: str = Query(..., min_length=1),
    limit: int = Query(10, ge=3, le=30),
):
    labels, counts = get_top_values(name=name, limit=limit)
    return {"name": name, "labels": labels, "counts": counts}


@router.get("/dataset/colstats")
def dataset_colstats(
    name: str = Query(..., min_length=1),
):
    return get_column_stats(name=name)


@router.post("/dataset/upload")
async def dataset_upload(file: UploadFile = File(...)):
    os.makedirs("uploads", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = (file.filename or "dataset.csv").replace("/", "_").replace("\\", "_")
    path = os.path.join("uploads", f"{ts}_{safe_name}")

    data = await file.read()
    with open(path, "wb") as f:
        f.write(data)

    set_uploaded_path(path)
    return {"ok": True, "path": path, "mode_text": get_mode_text()}


# ----------- Dataset Excel Export -----------

class ExportFilteredPayload(BaseModel):
    dataset_name: str
    mode_text: str
    columns: list[str]
    rows: list[dict]
    filter_col: str = ""
    filter_text: str = ""


class ExportReportPayload(BaseModel):
    dataset_name: str
    mode_text: str
    columns: list[str]
    rows: list[dict]
    filter_col: str = ""
    filter_text: str = ""
    numeric_col: str = ""
    colstats: dict = {}
    hist_labels: list[str] = []
    hist_counts: list[int] = []
    cat_col: str = ""
    top_labels: list[str] = []
    top_counts: list[int] = []


@router.post("/dataset/export_filtered")
def dataset_export_filtered(payload: ExportFilteredPayload):
    content = build_filtered_excel(
        dataset_name=payload.dataset_name,
        mode_text=payload.mode_text,
        columns=payload.columns,
        rows=payload.rows,
        filter_col=payload.filter_col,
        filter_text=payload.filter_text,
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dataset_filtered_{ts}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )


@router.post("/dataset/export_report")
def dataset_export_report(payload: ExportReportPayload):
    content = build_report_excel(
        dataset_name=payload.dataset_name,
        mode_text=payload.mode_text,
        columns=payload.columns,
        rows=payload.rows,
        filter_col=payload.filter_col,
        filter_text=payload.filter_text,
        numeric_col=payload.numeric_col,
        colstats=payload.colstats or {},
        hist_labels=payload.hist_labels or [],
        hist_counts=payload.hist_counts or [],
        cat_col=payload.cat_col,
        top_labels=payload.top_labels or [],
        top_counts=payload.top_counts or [],
    )

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"dataset_report_{ts}.xlsx"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}

    return StreamingResponse(
        iter([content]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers,
    )