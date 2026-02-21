from __future__ import annotations

from typing import Any, Dict, List


def _get(cur: Any, path: List[Any], default=None):
    for p in path:
        if isinstance(p, int):
            if not isinstance(cur, list) or p >= len(cur):
                return default
            cur = cur[p]
        else:
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
    return cur


def normalize_item_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    price_val = _get(item, ["price", "value"])
    price_cur = _get(item, ["price", "currency"])

    ship_val = _get(item, ["shippingOptions", 0, "shippingCost", "value"])
    ship_cur = _get(item, ["shippingOptions", 0, "shippingCost", "currency"])

    category_id = _get(item, ["categories", 0, "categoryId"]) or _get(item, ["leafCategoryIds", 0])

    return {
        "itemId": item.get("itemId"),
        "title": item.get("title"),
        "category": _get(item, ["categories", 0, "categoryName"]),
        "category_id": category_id,
        "condition": item.get("condition"),
        "price_value": price_val,
        "price_currency": price_cur,
        "shipping_value": ship_val,
        "shipping_currency": ship_cur,
        "seller_feedback": _get(item, ["seller", "feedbackScore"]),
        "web_url": item.get("itemWebUrl"),
        "item_href": item.get("itemHref"),
        "location_country": _get(item, ["itemLocation", "country"]),
    }


def normalize_search_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    items = payload.get("itemSummaries") or []
    norm = [normalize_item_summary(i) for i in items if isinstance(i, dict)]
    return {
        "total": payload.get("total", 0),
        "limit": payload.get("limit", len(norm)),
        "offset": payload.get("offset", 0),
        "next": payload.get("next"),
        "href": payload.get("href"),
        "items": norm,
    }


def normalize_item_details(payload: Dict[str, Any]) -> Dict[str, Any]:
    # Реальні поля з Browse Item API можуть бути: shortDescription, description (інколи HTML),
    # також itemSpecifics / localizedAspects.
    short_desc = payload.get("shortDescription")
    desc = payload.get("description")

    # інколи description = {"text": "..."} або щось схоже — підстрахуємось
    if isinstance(desc, dict):
        desc = desc.get("text") or desc.get("content") or str(desc)

    aspects = payload.get("localizedAspects") or []
    # зробимо з аспектів "Brand: Apple; Model: iPhone..."
    aspects_kv = []
    if isinstance(aspects, list):
        for a in aspects:
            if isinstance(a, dict):
                n = a.get("name")
                v = a.get("value")
                if n and v:
                    aspects_kv.append(f"{n}: {v}")

    return {
        "itemId": payload.get("itemId"),
        "shortDescription": short_desc,
        "description": desc,
        "aspects": aspects_kv,
    }