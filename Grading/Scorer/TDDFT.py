# Verify/scorer_tddft.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, Iterable, Union
import re
import pandas as pd

from Auto_benchmark.Grading.Rubrics.TDDFT import RUBRIC_TDDFT
from Auto_benchmark.io import fs

__all__ = [
    "score_booleans_tddft",
    "score_numerical_tddft",
    "score_tddft_case",
]

# ---------------- Boolean scoring (51 pts) ----------------
def score_booleans_tddft(
    booleans: Union[Path, pd.DataFrame],
    *,
    rubric: Dict = RUBRIC_TDDFT,
) -> Tuple[float, Dict[str, Any]]:
    """
    Score the boolean section for TDDFT using the rubric.
    `booleans` can be a CSV Path or a pandas DataFrame.
    Returns (points, details).
    """
    df = pd.read_csv(booleans) if isinstance(booleans, Path) else booleans.copy()
    details = {"sections": {}, "max": rubric["boolean"]["total"]}
    total_pts = 0.0

    # 1) Input checks (×2 inputs)
    sec = rubric["boolean"]["input"]
    inp_cols = [ fs._find_column(df, c) for c in sec["columns"] ]
    sec_pts = 0.0; per_row = []
    for _, row in df.iterrows():
        row_pts = sum(sec["yes_score"] for c in inp_cols if fs._is_yes(row.get(c)))
        per_row.append(row_pts)
        sec_pts += row_pts
    sec_pts *= sec.get("multiplicity", 1)
    sec_pts = min(sec_pts, sec["max_points"])
    total_pts += sec_pts
    details["sections"]["input"] = {"points": sec_pts, "max": sec["max_points"], "per_row": per_row}

    # 2) Common output (SCF ×2)
    sec = rubric["boolean"]["common_output"]
    scf_col = fs._find_column(df, sec["columns"][0])
    sec_pts = 0.0; per_row = []
    for _, row in df.iterrows():
        pts = sec["yes_score"] if fs._is_yes(row.get(scf_col)) else 0.0
        per_row.append(pts)
        sec_pts += pts
    sec_pts *= sec.get("multiplicity", 1)
    sec_pts = min(sec_pts, sec["max_points"])
    total_pts += sec_pts
    details["sections"]["common_output"] = {"points": sec_pts, "max": sec["max_points"], "per_row": per_row}

    # 3) Optimization output (Geo opt + Imag freq==no)
    sec = rubric["boolean"]["opt_output"]
    geo_col  = fs._find_column(df, sec["columns_yes"][0])
    imag_col = fs._find_column(df, sec["columns_no"][0])
    sec_pts = 0.0; per_row = []
    for _, row in df.iterrows():
        pts = 0.0
        pts += sec["yes_score"] if fs._is_yes(row.get(geo_col)) else 0.0
        pts += sec["no_score"]  if fs._is_no(row.get(imag_col)) else 0.0
        per_row.append(pts)
        sec_pts += pts
    sec_pts = min(sec_pts, sec["max_points"])
    total_pts += sec_pts
    details["sections"]["opt_output"] = {"points": sec_pts, "max": sec["max_points"], "per_row": per_row}

    # 4) TDDFT block / energy / oscillator
    sec = rubric["boolean"]["tddft_output"]
    tddft_cols = [ fs._find_column(df, c) for c in sec["columns"] ]
    sec_pts = 0.0; per_row = []
    for _, row in df.iterrows():
        pts = sum(sec["yes_score"] for c in tddft_cols if fs._is_yes(row.get(c)))
        per_row.append(pts)
        sec_pts += pts
    sec_pts = min(sec_pts, sec["max_points"])
    total_pts += sec_pts
    details["sections"]["tddft_output"] = {"points": sec_pts, "max": sec["max_points"], "per_row": per_row}

    return total_pts, details

# ---------------- Numerical scoring (49 pts) ----------------
def score_numerical_tddft(
    ground_truth: Dict[str, Optional[float]],
    agent: Dict[str, Optional[float]],
    *,
    json_proof: bool = False,     # set True if your action-trace confirms calc happened
    rubric: Dict = RUBRIC_TDDFT,
) -> Tuple[float, Dict[str, Any]]:
    """
    Score the numerical TDDFT values (S1 energy, S1–T1 gap, oscillator strength)
    using ±10%/±20% tiers from the rubric. If a metric requires JSON proof and
    `json_proof` is False, award 0 for that metric.
    """
    crits = rubric["numerical"]["criteria"]
    total = 0.0
    details = {"metrics": {}, "max": rubric["numerical"]["total"]}

    for name, cfg in crits.items():
        gt   = ground_truth.get(name)
        pred = agent.get(name)
        rel  = fs._rel_err(gt, pred)
        w    = cfg["weight"]

        if cfg.get("require_json_proof", False) and not json_proof:
            details["metrics"][name] = {"points": 0.0, "gt": gt, "pred": pred, "rel_err": rel, "reason": "no_json_proof"}
            continue

        if rel is None:
            details["metrics"][name] = {"points": 0.0, "gt": gt, "pred": pred, "rel_err": rel, "reason": "missing"}
            continue

        if rel <= cfg["full_rel"]:
            pts, reason = w, "full"
        elif rel <= cfg["half_rel"]:
            pts, reason = 0.5 * w, "half"
        else:
            pts, reason = 0.0, "out_of_range"

        total += pts
        details["metrics"][name] = {"points": pts, "gt": gt, "pred": pred, "rel_err": rel, "reason": reason}

    total = min(total, rubric["numerical"]["total"])
    return total, details

# ---------------- Combined scorer (per molecule) ----------------
def score_tddft_case(
    booleans: Union[Path, pd.DataFrame],
    gt_numeric: Dict[str, Optional[float]],
    agent_numeric: Dict[str, Optional[float]],
    *,
    json_proof: bool = False,
    rubric: Dict = RUBRIC_TDDFT,
) -> Dict[str, Any]:
    """
    Unified per-molecule scoring:
      - booleans: CSV path or DataFrame (columns per your boolean report)
      - gt_numeric: parsed ground-truth values from .out extractor
      - agent_numeric: values extracted from agent .md
      - json_proof: set True if the action-trace JSON shows the agent actually did the calc

    Returns:
      {
        "boolean_points": float,
        "boolean_details": {...},
        "numerical_points": float,
        "numerical_details": {...},
        "total_points": float,
      }
    """
    b_pts, b_det = score_booleans_tddft(booleans, rubric=rubric)
    n_pts, n_det = score_numerical_tddft(gt_numeric, agent_numeric, json_proof=json_proof, rubric=rubric)
    return {
        "boolean_points": b_pts,
        "boolean_details": b_det,
        "numerical_points": n_pts,
        "numerical_details": n_det,
        "total_points": round(b_pts + n_pts, 3),
    }
