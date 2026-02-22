from __future__ import annotations

from collections import Counter
from statistics import mean, median, pstdev
from typing import Any, Dict, List, Optional, Tuple


def _to_float(x: Any) -> Optional[float]:
    """Безпечне перетворення в float"""
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def _quantile(sorted_vals: List[float], q: float) -> Optional[float]:
    """
    Обчислення квантиля (лінійна інтерполяція).
    """
    if not sorted_vals:
        return None
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])

    n = len(sorted_vals)
    pos = (n - 1) * q  # позиція в масиві
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


def _stats(values: List[float]) -> Dict[str, Any]:
    """Розрахунок основних статистик"""
    if not values:
        return {  # якщо даних немає
            "count": 0,
            "min": None,
            "max": None,
            "avg": None,
            "median": None,
            "std": None,
            "q1": None,
            "q3": None,
            "iqr": None,
        }

    vals = sorted(values)
    q1 = _quantile(vals, 0.25)  # перший квартиль
    q3 = _quantile(vals, 0.75)  # третій квартиль
    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None  # міжквартильний розмах

    return {
        "count": len(vals),
        "min": float(vals[0]),
        "max": float(vals[-1]),
        "avg": float(mean(vals)),
        "median": float(median(vals)),
        "std": float(pstdev(vals)) if len(vals) >= 2 else 0.0,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
    }


def _histogram(values: List[float], bins: int = 10) -> Dict[str, Any]:
    """Побудова гістограми (рівні інтервали)"""
    if not values:
        return {"bins": []}

    vals = list(values)
    mn = min(vals)
    mx = max(vals)

    if mn == mx:
        # якщо всі значення однакові
        return {"bins": [{"from": mn, "to": mx, "count": len(vals)}]}

    step = (mx - mn) / bins
    if step <= 0:
        step = 1.0  # захист від ділення на 0

    counts = [0] * bins

    # розподіл значень
    for v in vals:
        idx = int((v - mn) / step)
        if idx >= bins:
            idx = bins - 1
        if idx < 0:
            idx = 0
        counts[idx] += 1

    out = []
    for i, c in enumerate(counts):
        a = mn + i * step
        b = mn + (i + 1) * step
        out.append({"from": float(a), "to": float(b), "count": int(c)})

    return {"bins": out}


def compute_analytics(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Головна функція аналітики по товарах.
    Очікує нормалізовані дані з /api/search.
    """

    prices: List[float] = []
    ship: List[float] = []
    totals: List[float] = []
    seller_scores: List[float] = []

    missing = Counter()
    currencies = Counter()

    by_condition = Counter()
    by_country = Counter()
    by_category = Counter()

    for it in items or []:
        # безпечне перетворення
        pv = _to_float(it.get("price_value"))
        sv = _to_float(it.get("shipping_value"))
        sf = _to_float(it.get("seller_feedback"))

        # визначення валюти
        cur = (it.get("price_currency") or it.get("shipping_currency") or "").strip()
        if cur:
            currencies[cur] += 1

        # ціна
        if pv is None:
            missing["price_value"] += 1
        else:
            prices.append(pv)

        # доставка
        if sv is None:
            missing["shipping_value"] += 1
        else:
            ship.append(sv)

        # total
        if pv is None and sv is None:
            missing["total"] += 1
        else:
            totals.append((pv or 0.0) + (sv or 0.0))

        # рейтинг продавця
        if sf is None:
            missing["seller_feedback"] += 1
        else:
            seller_scores.append(sf)

        # групування
        cond = (it.get("condition") or "—").strip()
        by_condition[cond] += 1

        ctry = (it.get("location_country") or "—").strip()
        by_country[ctry] += 1

        cat = (it.get("category") or "—").strip()
        by_category[cat] += 1

    # функція для топ-N
    def top(counter: Counter, n: int = 7) -> List[Dict[str, Any]]:
        return [{"key": k, "count": int(v)} for k, v in counter.most_common(n)]

    common_currency = currencies.most_common(1)[0][0] if currencies else ""

    # обчислення статистик
    price_stats = _stats(prices)
    ship_stats = _stats(ship)
    total_stats = _stats(totals)
    seller_stats = _stats(seller_scores)

    # фінальний результат
    return {
        "count_items": len(items or []),
        "currency_most_common": common_currency,
        "missing": dict(missing),
        "price": price_stats,
        "shipping": ship_stats,
        "total": total_stats,
        "seller_feedback": seller_stats,
        "hist": {
            "price": _histogram(prices, bins=10),
            "total": _histogram(totals, bins=10),
        },
        "top": {
            "conditions": top(by_condition, 7),
            "countries": top(by_country, 7),
            "categories": top(by_category, 7),
        },
    }