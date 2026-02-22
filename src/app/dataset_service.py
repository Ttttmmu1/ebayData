from __future__ import annotations

import csv
import os
import re
from collections import Counter
from statistics import mean, median, pstdev
from typing import Any, Dict, List, Tuple, Optional


DEFAULT_DATASET_FILENAME = "marketing_sample_for_ebay_com-ebay_com_product_details.csv"

NA_TOKENS = { # значення, які є пропусками
    "", "na", "n/a", "nan", "null", "none", "-", "--", "—",
    "not available", "n\\a"
}

NUMERIC_THRESHOLD = 0.70 # поріг: частка успішного парсингу як числа
SUMMARY_SAMPLE_MAX_ROWS = 2000 # максимум рядків для summary (для upload)


class DatasetState:
    def __init__(self) -> None:
        self.mode = "default" # режим: default | upload
        self.path = DEFAULT_DATASET_FILENAME # шлях до активного файлу


STATE = DatasetState() # глобальний стан датасету

def _project_root_path(filename: str) -> str:
    """Побудова шляху до дефолтного файлу (зараз просто повертає filename)"""
    return filename

def get_current_path() -> str:
    """Повертає шлях до активного датасету (upload або default)"""
    return STATE.path if STATE.mode == "upload" else _project_root_path(DEFAULT_DATASET_FILENAME)

def get_mode_text() -> str:
    """Текст, який показується у фронті (dsMode)"""
    if STATE.mode == "default":
        return "Default dataset (прев'ю обмежено першими рядками, усього 2000 рядків)"
    return "User uploaded dataset (full file, NOT trimmed)"

def set_uploaded_path(path: str) -> None:
    """Перемикає режим на upload і зберігає шлях до завантаженого файлу"""
    STATE.mode = "upload"
    STATE.path = path

def set_default() -> None:
    """Повертає режим на default"""
    STATE.mode = "default"
    STATE.path = DEFAULT_DATASET_FILENAME

_number_cleanup_re = re.compile(r"[,\s]") # прибрати коми/пробіли
_keep_num_chars_re = re.compile(r"[^0-9\.\-]") # залишити тільки цифри

def _is_missing(x: Any) -> bool:
    """Перевірка, чи значення є пропуском"""
    if x is None:
        return True
    s = str(x).strip().lower()
    return s in NA_TOKENS

def _try_float(x: Any) -> Optional[float]:
    """
    Надійний парсер чисел:
    - пропуски None
    - прибирає коми/пробіли
    - прибирає валюту/%
    """
    if _is_missing(x):
        return None

    s = str(x).strip()
    s = _number_cleanup_re.sub("", s) # прибрати , та пробіли
    s = _keep_num_chars_re.sub("", s) # прибрати всі нечислові символи

    if s in ("", "-", ".", "-."):
        return None

    try:
        return float(s)
    except Exception:
        return None


def _quantile(sorted_vals: List[float], q: float) -> Optional[float]:
    """Квантиль (лінійна інтерполяція), вхідні дані мають бути відсортовані"""
    if not sorted_vals:
        return None
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    n = len(sorted_vals)
    pos = (n - 1) * q
    lo = int(pos)
    hi = min(lo + 1, n - 1)
    frac = pos - lo
    return float(sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac)


def _stats(values: List[float]) -> Dict[str, Any]:
    """Пакет статистик для списку чисел"""
    if not values:
        return {
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
    q1 = _quantile(vals, 0.25)
    q3 = _quantile(vals, 0.75)
    iqr = (q3 - q1) if (q1 is not None and q3 is not None) else None
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


def read_preview(offset: int = 0, limit: int = 50) -> Dict[str, Any]:
    """Читає сторінку preview таблиці (offset/limit), для default є cap 2000"""
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None # обрізання тільки для default

    rows: List[Dict[str, Any]] = []
    cols: List[str] = []

    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []

        i = 0
        for r in reader:
            if hard_cap is not None and i >= hard_cap:
                break

            if i >= offset and len(rows) < limit:
                # значення не None
                rows.append({k: (r.get(k, "") if r.get(k, "") is not None else "") for k in cols})

            i += 1

    return {"columns": cols, "rows": rows, "offset": offset, "limit": limit}


def compute_summary() -> Dict[str, Any]:
    """Обчислює summary: колонки, пропуски, numeric/categorical, stats (з sample)"""
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None  # обрізання для default

    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []

        row_count = 0
        missing = Counter() # кількість пропусків по колонках

        non_missing_cnt = Counter() # скільки non-missing значень
        numeric_ok_cnt = Counter() # скільки з них успішно парситься як число
        numeric_vals: Dict[str, List[float]] = {c: [] for c in cols} # значення для stats

        for r in reader:
            if hard_cap is not None and row_count >= hard_cap:
                break
            if row_count >= SUMMARY_SAMPLE_MAX_ROWS and STATE.mode == "upload":
                break  # summary для upload

            row_count += 1
            for c in cols:
                v = r.get(c, "")
                if _is_missing(v):
                    missing[c] += 1
                    continue

                non_missing_cnt[c] += 1
                fv = _try_float(v)
                if fv is not None:
                    numeric_ok_cnt[c] += 1
                    numeric_vals[c].append(fv)

        numeric_cols = [] # колонки, які вважаємо числовими
        categorical_cols = [] # решта
        num_stats = {} # stats по числових

        for c in cols:
            nm = non_missing_cnt[c]
            ok = numeric_ok_cnt[c]
            if nm == 0:
                categorical_cols.append(c)
                continue

            ratio = ok / nm  # частка успішного парсингу
            if ratio >= NUMERIC_THRESHOLD and ok >= 5:
                numeric_cols.append(c)
                vals = numeric_vals[c]
                if vals:
                    s = _stats(vals)
                    num_stats[c] = s | {"parse_ratio": ratio} # додавання parse_ratio
            else:
                categorical_cols.append(c)

    return {
        "dataset_name": os.path.basename(path), # ім'я файлу
        "mode": STATE.mode, # default/upload
        "mode_text": get_mode_text(), # текст для UI
        "row_count": row_count, # скільки рядків проскановано
        "columns": cols, # список колонок
        "missing": dict(missing), # пропуски по колонках
        "numeric_columns": numeric_cols, # визначені числові
        "categorical_columns": categorical_cols, # визначені категоріальні
        "numeric_stats": num_stats, # stats по числових
        "default_trim_cap": 2000 if is_default else None, # cap для default
        "numeric_threshold": NUMERIC_THRESHOLD, # поріг numeric
        "parsing_note": "Numbers are parsed by treating NA/N/A/null/empty/'-' as missing; removing commas/spaces and symbols like $ and %.",
    }

def get_column_values(name: str, limit: int = 5000) -> List[Any]:
    """Повертає значення однієї колонки (для гістограми), з cap для default"""
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

    out: List[Any] = []
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        i = 0
        for r in reader:
            if hard_cap is not None and i >= hard_cap:
                break
            i += 1
            if name in r:
                v = r.get(name)
                if not _is_missing(v):
                    out.append(v)
            if len(out) >= limit:
                break
    return out


def get_top_values(name: str, limit: int = 10) -> Tuple[List[str], List[int]]:
    """Top-N частот по колонці (категорії), з cap для default"""
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

    cnt = Counter()
    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        i = 0
        for r in reader:
            if hard_cap is not None and i >= hard_cap:
                break
            i += 1
            v = r.get(name, "")
            if _is_missing(v):
                continue
            s = str(v).strip()
            if s:
                cnt[s] += 1

    top = cnt.most_common(limit)
    labels = [k for k, _ in top]
    counts = [int(v) for _, v in top]
    return labels, counts


def get_column_stats(name: str, max_rows: int = 20000) -> Dict[str, Any]:
    """
    Статистика однієї колонки:
    - missing / unparsable / parsed
    - parse_ratio
    - базові stats
    """
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

    vals: List[float] = [] # зібрані числа
    missing_cnt = 0 # пропуски
    unparsable_cnt = 0 # не парсяться як число
    seen = 0 # скільки рядків переглянули

    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if hard_cap is not None and seen >= hard_cap:
                break
            if STATE.mode == "upload" and seen >= max_rows:
                break

            seen += 1
            v = r.get(name, "")
            if _is_missing(v):
                missing_cnt += 1
                continue

            fv = _try_float(v)
            if fv is None:
                unparsable_cnt += 1
                continue
            vals.append(fv)

    s = _stats(vals)
    non_missing = max(seen - missing_cnt, 0)
    parse_ratio = (len(vals) / non_missing) if non_missing else 0.0

    return {
        "name": name,
        "rows_scanned": seen,
        "missing_count": missing_cnt,
        "unparsable_count": unparsable_cnt,
        "parsed_count": len(vals),
        "parse_ratio": parse_ratio,
        "stats": s,
        "parsing_note": "Parsing: treat NA/N/A/null/empty/'-' as missing; remove commas/spaces; remove symbols like $ and %; keep digits, dot, minus.",
    }