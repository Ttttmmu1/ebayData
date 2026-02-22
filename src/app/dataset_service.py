from __future__ import annotations

import csv
import os
import re
from collections import Counter
from statistics import mean, median, pstdev
from typing import Any, Dict, List, Tuple, Optional


DEFAULT_DATASET_FILENAME = "marketing_sample_for_ebay_com-ebay_com_product_details.csv"

NA_TOKENS = {
    "", "na", "n/a", "nan", "null", "none", "-", "--", "—",
    "not available", "n\\a"
}

NUMERIC_THRESHOLD = 0.70
SUMMARY_SAMPLE_MAX_ROWS = 2000


class DatasetState:
    def __init__(self) -> None:
        self.mode = "default"  # default | upload
        self.path = DEFAULT_DATASET_FILENAME


STATE = DatasetState()


def _project_root_path(filename: str) -> str:
    return filename


def get_current_path() -> str:
    return STATE.path if STATE.mode == "upload" else _project_root_path(DEFAULT_DATASET_FILENAME)


def get_mode_text() -> str:
    if STATE.mode == "default":
        return "Default dataset (preview trimmed to 2000 rows)"
    return "User uploaded dataset (full file, NOT trimmed)"


def set_uploaded_path(path: str) -> None:
    STATE.mode = "upload"
    STATE.path = path


def set_default() -> None:
    STATE.mode = "default"
    STATE.path = DEFAULT_DATASET_FILENAME


_number_cleanup_re = re.compile(r"[,\s]")
_keep_num_chars_re = re.compile(r"[^0-9\.\-]")


def _is_missing(x: Any) -> bool:
    if x is None:
        return True
    s = str(x).strip().lower()
    return s in NA_TOKENS


def _try_float(x: Any) -> Optional[float]:
    """
    Robust number parser:
    - missing tokens: NA, N/A, null, empty, '-', etc -> None
    - strips commas/spaces
    - strips currency/percent and other symbols
    Examples:
      "$1,234.50" -> 1234.5
      "12.5%" -> 12.5
      " 99 " -> 99
    """
    if _is_missing(x):
        return None

    s = str(x).strip()
    s = _number_cleanup_re.sub("", s)
    s = _keep_num_chars_re.sub("", s)

    if s in ("", "-", ".", "-."):
        return None

    try:
        return float(s)
    except Exception:
        return None


def _quantile(sorted_vals: List[float], q: float) -> Optional[float]:
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
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

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
                rows.append({k: (r.get(k, "") if r.get(k, "") is not None else "") for k in cols})

            i += 1

    return {"columns": cols, "rows": rows, "offset": offset, "limit": limit}


def compute_summary() -> Dict[str, Any]:
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

    with open(path, "r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []

        row_count = 0
        missing = Counter()

        non_missing_cnt = Counter()
        numeric_ok_cnt = Counter()
        numeric_vals: Dict[str, List[float]] = {c: [] for c in cols}

        for r in reader:
            if hard_cap is not None and row_count >= hard_cap:
                break
            if row_count >= SUMMARY_SAMPLE_MAX_ROWS and STATE.mode == "upload":
                break

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

        numeric_cols = []
        categorical_cols = []
        num_stats = {}

        for c in cols:
            nm = non_missing_cnt[c]
            ok = numeric_ok_cnt[c]
            if nm == 0:
                categorical_cols.append(c)
                continue

            ratio = ok / nm
            if ratio >= NUMERIC_THRESHOLD and ok >= 5:
                numeric_cols.append(c)
                vals = numeric_vals[c]
                if vals:
                    s = _stats(vals)
                    num_stats[c] = s | {"parse_ratio": ratio}
            else:
                categorical_cols.append(c)

    return {
        "dataset_name": os.path.basename(path),
        "mode": STATE.mode,
        "mode_text": get_mode_text(),
        "row_count": row_count,
        "columns": cols,
        "missing": dict(missing),
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "numeric_stats": num_stats,
        "default_trim_cap": 2000 if is_default else None,
        "numeric_threshold": NUMERIC_THRESHOLD,
        "parsing_note": "Numbers are parsed by treating NA/N/A/null/empty/'-' as missing; removing commas/spaces and symbols like $ and %.",
    }


def get_column_values(name: str, limit: int = 5000) -> List[Any]:
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
    Stats for one column:
    - parses numbers robustly
    - counts missing and unparsable
    """
    path = get_current_path()
    is_default = (STATE.mode == "default")
    hard_cap = 2000 if is_default else None

    vals: List[float] = []
    missing_cnt = 0
    unparsable_cnt = 0
    seen = 0

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