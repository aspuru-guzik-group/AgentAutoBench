# Auto_benchmark/Grading/Scorer/pKa.py
from __future__ import annotations
from typing import Dict, Any, Optional, List, Union
import re

from Auto_benchmark.Grading.Rubrics import PKA_RUBRIC as RUBRIC
from Auto_benchmark.Config import defaults
from Auto_benchmark.io import fs

__all__ = [
    "score_boolean_pka",
    "score_numerical_pka",
    "score_pka_case",
]

# ---------------- helpers ----------------
def _coerce_float(x: Any) -> Optional[float]:
    if x is None or (isinstance(x, str) and fs._norm_str(x) in {"", "none", "null", "do not exist", "n/a", "na"}):
        return None
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        try:
            return float(x)
        except Exception:
            return None
    m = defaults.NUM.search(str(x))
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None

# ==========================================================
# BOOLEAN block (rubric["boolean"])
#   - input_qc: 8×8 checks (64 pts)
#   - delta_g: up to 8 yes × 1.5 (12 pts)
# ==========================================================
def score_boolean_pka(
    *,
    input_qc_rows: List[Dict[str, Any]],
    delta_g_items: Optional[List[Union[bool, Dict[str, Any], str]]],
    delta_g_key: str = "deltaG_exist",
) -> tuple[float, dict]:
    bcfg = RUBRIC.get("boolean", {}) or {}
    sections = bcfg.get("sections", {}) or {}

    # ---- input_qc ----
    icfg = sections.get("input_qc", {}) or {}
    cols       = icfg.get("columns", [
        "Method exist?","Basis set exist?","Tasks exist?","Charge & mult exist?",
        "XYZ file exist?","SCF converged?","Geo opt converged?","Imag freq exist?",
    ])
    yes_score  = float(icfg.get("yes_score", 1.0))
    imag_score = float(icfg.get("imag_no_score", 1.0))
    icfg_max   = float(icfg.get("max_points", 64.0))

    input_pts = 0.0
    per_row_points: List[float] = []
    for r in input_qc_rows:
        rp = 0.0
        for c in cols[:7]:
            rp += yes_score if fs._is_yes(r.get(c)) else 0.0
        rp += imag_score if fs._is_no(r.get(cols[7])) else 0.0
        per_row_points.append(rp)
        input_pts += rp
    # no extra cap here; upstream you typically have exactly 8 rows

    # ---- delta_g ----
    dcfg = sections.get("delta_g", {}) or {}
    n_items    = int(dcfg.get("n_items", 8))
    per_yes    = float(dcfg.get("per_yes", 1.5))
    dcfg_max   = float(dcfg.get("max_points", 12.0))

    if not delta_g_items:
        dg_pts = 0.0
        dg_info = {"reason": "no ΔG items provided", "max": dcfg_max}
        yes_capped = 0
        rows_seen = 0
    else:
        yes_count = 0
        for item in delta_g_items:
            flag_val = item.get(delta_g_key) if isinstance(item, dict) else item
            if fs._is_yes(flag_val):
                yes_count += 1
        yes_capped = min(yes_count, n_items)
        dg_pts = min(yes_capped * per_yes, dcfg_max)
        rows_seen = len(delta_g_items)
        dg_info = {
            "rows_seen": rows_seen,
            "yes_count_capped": yes_capped,
            "n_items_cap": n_items,
            "flag_key": delta_g_key,
            "max": dcfg_max,
        }

    boolean_total_cfg = float(bcfg.get("total", 76.0))
    total_pts = input_pts + dg_pts
    # (do not cap across subsections unless you really want to enforce exact 76.0)

    details = {
        "input_qc": {
            "points": input_pts,
            "max": icfg_max,
            "columns_used": cols,
            "per_row_points": per_row_points,
        },
        "delta_g": {
            "points": dg_pts,
            **dg_info,
        },
        "max": boolean_total_cfg,
    }
    return total_pts, details

# ==========================================================
# NUMERICAL block (rubric["numerical"])
#   - linear_regression presence (12)
#   - pKa windowing: full (12) / half (6)
# ==========================================================
def score_numerical_pka(md_extraction: Dict[str, Any]) -> tuple[float, dict]:
    ncfg = RUBRIC.get("numerical", {}) or {}
    crit = ncfg.get("criteria", {}) or {}
    max_total = float(ncfg.get("total", 24.0))

    lin_cfg  = crit.get("linear_regression", {}) or {}
    lin_pts  = float(lin_cfg.get("weight", 12.0))

    pka_cfg  = crit.get("pka_value", {}) or {}
    full_win = pka_cfg.get("full", {"min": 1.4, "max": 1.6, "award": 12.0})
    half_win = pka_cfg.get("half", {"min": 1.2, "max": 1.8, "award": 6.0})

    pts = 0.0
    details: Dict[str, Any] = {}

    # 1) linear regression model presence
    lin_ok = fs._is_yes(md_extraction.get("has_linear_regression_model"))
    details["linear_regression_found"] = bool(lin_ok)
    if lin_ok:
        pts += lin_pts

    # 2) pKa windowing
    pka_val = _coerce_float(md_extraction.get("pKa_of_chlorofluoroacetic_acid"))
    details["pka_extracted"] = pka_val
    if pka_val is not None:
        if float(full_win["min"]) <= pka_val <= float(full_win["max"]):
            pts += float(full_win["award"])
            details["pka_points"] = float(full_win["award"])
        elif float(half_win["min"]) <= pka_val <= float(half_win["max"]):
            pts += float(half_win["award"])
            details["pka_points"] = float(half_win["award"])
        else:
            details["pka_points"] = 0.0
    else:
        details["pka_points"] = 0.0

    details["max"] = max_total
    return pts, details

# ==========================================================
# Unified 2-section scorer
# ==========================================================
def score_pka_case(
    *,
    section1_rows: List[Dict[str, Any]],                # input_qc rows
    section2_deltag_items: Optional[List[Union[bool, Dict[str, Any], str]]],
    md_extraction: Dict[str, Any],
) -> Dict[str, Any]:
    boolean_pts, boolean_details = score_boolean_pka(
        input_qc_rows=section1_rows,
        delta_g_items=section2_deltag_items,
    )
    numerical_pts, numerical_details = score_numerical_pka(md_extraction)

    total = round(boolean_pts + numerical_pts, 3)
    return {
        "boolean_points": boolean_pts,
        "boolean_details": boolean_details,
        "numerical_points": numerical_pts,
        "numerical_details": numerical_details,
        "total_points": total,
        "rubric_max": {
            "boolean_total": float(RUBRIC.get("boolean", {}).get("total", 76.0)),
            "numerical_total": float(RUBRIC.get("numerical", {}).get("total", 24.0)),
            "total": float(RUBRIC.get("metadata", {}).get("total_max_points", 100.0)),
        },
    }
