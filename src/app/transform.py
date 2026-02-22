from __future__ import annotations

from typing import Any, Dict, List

def _get(cur: Any, path: List[Any], default=None):
    """Безпечний доступ до вкладених полів dict/list за шляхом (ключі та індекси)"""
    for p in path:
        if isinstance(p, int):
            # крок як індекс списку
            if not isinstance(cur, list) or p >= len(cur):
                return default
            cur = cur[p]
        else:
            # крок як ключ словника
            if not isinstance(cur, dict) or p not in cur:
                return default
            cur = cur[p]
    return cur


def normalize_item_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    """Нормалізація одного itemSummary з eBay Browse Search API"""
    price_val = _get(item, ["price", "value"]) # price.value
    price_cur = _get(item, ["price", "currency"]) # price.currency

    ship_val = _get(item, ["shippingOptions", 0, "shippingCost", "value"]) # shippingOptions[0].shippingCost.value
    ship_cur = _get(item, ["shippingOptions", 0, "shippingCost", "currency"]) # shippingOptions[0].shippingCost.currency

    # categoryId з categories або fallback на leafCategoryIds
    category_id = _get(item, ["categories", 0, "categoryId"]) or _get(item, ["leafCategoryIds", 0])

    return {
        "itemId": item.get("itemId"), # ID товару
        "title": item.get("title"), # назва
        "category": _get(item, ["categories", 0, "categoryName"]), # назва категорії
        "category_id": category_id, # ID категорії
        "condition": item.get("condition"), # стан (New/Used...)
        "price_value": price_val, # ціна (value)
        "price_currency": price_cur, # валюта ціни
        "shipping_value": ship_val, # доставка (value)
        "shipping_currency": ship_cur, # валюта доставки
        "seller_feedback": _get(item, ["seller", "feedbackScore"]), # рейтинг продавця
        "web_url": item.get("itemWebUrl"), # URL у браузері
        "item_href": item.get("itemHref"), # API href
        "location_country": _get(item, ["itemLocation", "country"]), # країна
    }


def normalize_search_response(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Нормалізація відповіді пошуку: meta + список нормалізованих items"""
    items = payload.get("itemSummaries") or []  # список item summary
    norm = [normalize_item_summary(i) for i in items if isinstance(i, dict)] # тільки dict

    return {
        "total": payload.get("total", 0), # total з API
        "limit": payload.get("limit", len(norm)), # limit (fallback = len)
        "offset": payload.get("offset", 0), # offset
        "next": payload.get("next"), # next link (якщо є)
        "href": payload.get("href"), # поточний href
        "items": norm, # нормалізовані товари
    }


def normalize_item_details(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Нормалізація деталей товару з Browse Item API"""
    # основні текстові поля
    short_desc = payload.get("shortDescription")
    desc = payload.get("description")

    # якщо description не рядок, а dict - витягнути текст
    if isinstance(desc, dict):
        desc = desc.get("text") or desc.get("content") or str(desc)

    aspects = payload.get("localizedAspects") or []  # список характеристик (name/value)

    # перетворюємо aspects у список рядків "Name: Value"
    aspects_kv = []
    if isinstance(aspects, list):
        for a in aspects:
            if isinstance(a, dict):
                n = a.get("name")
                v = a.get("value")
                if n and v:
                    aspects_kv.append(f"{n}: {v}")

    return {
        "itemId": payload.get("itemId"), # ID товару
        "shortDescription": short_desc, # короткий опис
        "description": desc, # опис (може бути HTML)
        "aspects": aspects_kv, # характеристики
    }
