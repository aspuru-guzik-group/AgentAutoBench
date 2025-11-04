from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Iterable, Union
import re
import pandas as pd

from Auto_benchmark.Grading.Rubrics.RingStrain import RUBRIC_RINGSTRAIN
from Auto_benchmark.io import fs

__all__ = [
    "score_booleans_ringstrain",
    "score_reference_ringstrain",
    "score_numerical_ringstrain",
    "score_ringstrain",
]

# ---------------- Boolean scoring (44 pts) ----------------
def score_booleans_ringstrain(
    booleans: Union[Path, pd.DataFrame],
    *,
    rubric: Dict = RUBRIC_RINGSTRAIN,
) -> Tuple[float, Dict[str, Any]]:
    """
    Score the boolean QC section:
      - 8 checks per molecule (award YES for first 7; award NO for imag freq)
      - 11 molecules total × 8 × 0.5 = 44 max
    `booleans` can be a CSV Path or a pandas DataFrame.
    """
    df = pd.read_csv(booleans) if isinstance(booleans, Path) else booleans.copy()
    sec = rubric["boolean"]["sections"]["input_qc"]
    details = {"sections": {}, "max": rubric["boolean"]["total"]}

    cols = [ fs._find_column(df, c) for c in sec["columns"] ]
    yes_cols = cols[:7]
    imag_col = cols[7]

    sec_pts = 0.0
    per_row = []
    for _, row in df.iterrows():
        pts = 0.0
        pts += sum(sec["yes_score"] for c in yes_cols if fs._is_yes(row.get(c)))
        pts += sec["imag_no_score"] if fs._is_no(row.get(imag_col)) else 0.0
        per_row.append(pts)
        sec_pts += pts

    # cap to max (handles if df has > 11 rows)
    sec_pts = min(sec_pts, sec["max_points"])
    details["sections"]["input_qc"] = {
        "points": sec_pts,
        "max": sec["max_points"],
        "per_row_points": per_row,
        "columns_used": sec["columns"],
    }

    return sec_pts, details

# ---------------- Reference point scoring (8 pts) ----------------
def score_reference_ringstrain(
    reference_is_cyclohexane: bool,
    *,
    rubric: Dict = RUBRIC_RINGSTRAIN,
) -> Tuple[float, Dict[str, Any]]:
    """
    Award 8 if cyclohexane is the stated reference point, else 0.
    """
    rsec = rubric["reference_point"]["rule"]
    pts = rsec["true_award"] if bool(reference_is_cyclohexane) else rsec["false_award"]
    details = {
        "key": rsec["key"],
        "value": bool(reference_is_cyclohexane),
        "points": pts,
        "max": rubric["reference_point"]["total"],
    }
    return pts, details

# ---------------- Numerical scoring (48 pts) ----------------
def score_numerical_ringstrain(
    ground_truth_rows: Dict[int, Dict[str, Optional[float]]],
    agent_rows: Dict[int, Dict[str, Optional[float]]],
    *,
    rubric: Dict = RUBRIC_RINGSTRAIN,
) -> Tuple[float, Dict[str, Any]]:
    """
    Score ΔH and ΔG (kcal/mol) for ring sizes listed in the rubric.
    ground_truth_rows and agent_rows are dicts keyed by ring size int:
        n -> {"ring_size": n, "strain_delta_H_kcal_mol": float, "strain_delta_G_kcal_mol": float}
    Scoring per item:
        full if |err| ≤ abs_tol_full
        half if abs_tol_full < |err| ≤ abs_tol_half
        else 0
    Each item worth 4.0 points (12 items → 48 total).
    """
    cfg = rubric["numerical"]["config"]
    sizes: Iterable[int] = cfg["ring_sizes_for_scoring"]
    key_h = cfg["keys"]["delta_h"]
    key_g = cfg["keys"]["delta_g"]
    tol_full = float(cfg["abs_tol_full"])
    tol_half = float(cfg["abs_tol_half"])
    per_pts  = float(cfg["per_item_points"])

    total = 0.0
    per_item_details = []

    def _score_one(name: str, gt: Optional[float], pred: Optional[float]) -> Tuple[float, str, Optional[float]]:
        err = fs._abs_err(gt, pred)
        if err is None:
            return 0.0, "missing", None
        if err <= tol_full:
            return per_pts, "full", err
        if err <= tol_half:
            return 0.5 * per_pts, "half", err
        return 0.0, "out_of_range", err

    for n in sizes:
        gt_row = ground_truth_rows.get(n, {})
        ag_row = agent_rows.get(n, {})

        # ΔH
        pts_h, reason_h, err_h = _score_one(
            f"{n}:{key_h}",
            gt_row.get(key_h),
            ag_row.get(key_h),
        )
        total += pts_h
        per_item_details.append({
            "ring_size": n,
            "metric": key_h,
            "gt": gt_row.get(key_h),
            "pred": ag_row.get(key_h),
            "abs_err": err_h,
            "points": pts_h,
            "reason": reason_h,
        })

        # ΔG
        pts_g, reason_g, err_g = _score_one(
            f"{n}:{key_g}",
            gt_row.get(key_g),
            ag_row.get(key_g),
        )
        total += pts_g
        per_item_details.append({
            "ring_size": n,
            "metric": key_g,
            "gt": gt_row.get(key_g),
            "pred": ag_row.get(key_g),
            "abs_err": err_g,
            "points": pts_g,
            "reason": reason_g,
        })

    # cap to rubric max (48)
    total = min(total, rubric["numerical"]["total"])
    details = {
        "items": per_item_details,
        "max": rubric["numerical"]["total"],
        "abs_tol_full": tol_full,
        "abs_tol_half": tol_half,
        "per_item_points": per_pts,
        "ring_sizes": list(sizes),
        "keys": {"delta_h": key_h, "delta_g": key_g},
    }
    return total, details

# ---------------- Combined scorer (full 100 pts) ----------------
def score_ringstrain(
    booleans: Union[Path, pd.DataFrame],
    ground_truth_rows: Dict[int, Dict[str, Optional[float]]],
    agent_rows: Dict[int, Dict[str, Optional[float]]],
    reference_is_cyclohexane: bool,
    *,
    rubric: Dict = RUBRIC_RINGSTRAIN,
) -> Dict[str, Any]:
    """
    Unified scorer for RingStrain:
      - booleans: CSV path or DataFrame (your 8-per-molecule QC table)
      - ground_truth_rows: tool output keyed by ring size
      - agent_rows: LLM .md extraction keyed by ring size
      - reference_is_cyclohexane: boolean from LLM extractor
    Returns a full breakdown and totals.
    """
    b_pts, b_det = score_booleans_ringstrain(booleans, rubric=rubric)
    r_pts, r_det = score_reference_ringstrain(reference_is_cyclohexane, rubric=rubric)
    n_pts, n_det = score_numerical_ringstrain(ground_truth_rows, agent_rows, rubric=rubric)

    total = round(b_pts + r_pts + n_pts, 3)
    return {
        "boolean_points": b_pts,
        "boolean_details": b_det,
        "reference_points": r_pts,
        "reference_details": r_det,
        "numerical_points": n_pts,
        "numerical_details": n_det,
        "total_points": total,
        "max_points": rubric["metadata"]["total_max_points"],
    }
