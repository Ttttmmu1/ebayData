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
    img = _get(item, ["image", "imageUrl"]) or _get(item, ["thumbnailImages", 0, "imageUrl"])

    return {
        "itemId": item.get("itemId"),
        "title": item.get("title"),
        "category": _get(item, ["categories", 0, "categoryName"]),
        "condition": item.get("condition"),
        "price_value": price_val,
        "price_currency": price_cur,
        "shipping_value": ship_val,
        "shipping_currency": ship_cur,
        "seller_feedback": _get(item, ["seller", "feedbackScore"]),
        "web_url": item.get("itemWebUrl"),
        "item_href": item.get("itemHref"),
        "image_url": img,
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
