from __future__ import annotations
from typing import Dict, Any, Tuple, Union, List
import pandas as pd

from Auto_benchmark.Grading.Rubrics.Fukui import RUBRIC_FUKUI
from Auto_benchmark.Grading import utils

__all__ = [
    "score_booleans_fukui",
    "score_numerical_fukui",
    "score_fukui_case",
]

# ---------------- Boolean scoring (60 pts) ----------------
def score_booleans_fukui(
    booleans: Union[pd.DataFrame, Dict[str, Any]],
    *,
    rubric: Dict = RUBRIC_FUKUI,
) -> Tuple[float, Dict[str, Any]]:
    """
    Scores the boolean sections for Fukui using the rubric.
    
    Sections:
      1. input_files (Exist, Task, Structure)
      2. opt_output (SCF, Geo, Imag)
      3. sp_populations (SCF + Populations)
      
    Args:
        booleans: The boolean data (DataFrame row or dict).
        rubric: The rubric configuration.

    Returns:
        Tuple[float, Dict[str, Any]]: (Total points earned, Detailed breakdown).
    """
    # Normalize input to a dict
    row = booleans
    if isinstance(booleans, pd.DataFrame):
        row = booleans.iloc[0].to_dict() if not booleans.empty else {}

    total_pts = 0.0
    details = {"sections": {}, "max": rubric["boolean"]["total"]}
    
    for sec_key, sec_cfg in rubric["boolean"]["sections"].items():
        max_sec_pts = sec_cfg["max_points"]
        yes_score = sec_cfg["yes_score"]
        columns = sec_cfg["columns"]
        
        sec_earned = 0.0
        row_details = {}
        
        for col in columns:
            # Use utility for fuzzy column lookup (handles case/whitespace)
            try:
                actual_col = utils.find_column_fuzzy(pd.DataFrame([row]), col)
                val = row.get(actual_col)
                
                # Use utility for robust boolean check
                if utils.is_yes(val):
                    sec_earned += yes_score
                    row_details[col] = "pass"
                else:
                    row_details[col] = "fail"
            except KeyError:
                row_details[col] = "missing"

        # Cap points at section max
        sec_earned = min(sec_earned, max_sec_pts)
        total_pts += sec_earned
        
        details["sections"][sec_key] = {
            "points": sec_earned,
            "max": max_sec_pts,
            "breakdown": row_details
        }

    return total_pts, details


# ---------------- Numerical scoring (40 pts) ----------------
def score_numerical_fukui(
    ground_truth: Dict[str, Any],
    agent: Dict[str, Any],
    *,
    rubric: Dict = RUBRIC_FUKUI,
) -> Tuple[float, Dict[str, Any]]:
    """
    Scores the Condensed Fukui Indices.
    
    Expects entries like 'f_plus_Mulliken' (Lists of floats).
    Scoring is done per-atom.

    Args:
        ground_truth: Calculated GT values.
        agent: Extracted agent values.
        rubric: The rubric configuration.

    Returns:
        Tuple[float, Dict[str, Any]]: (Total points, Detailed breakdown).
    """
    criteria = rubric["numerical"]["criteria"]
    total_pts = 0.0
    details = {"metrics": {}, "max": rubric["numerical"]["total"]}

    for metric_name, cfg in criteria.items():
        weight = cfg["weight"]
        full_tol = cfg["full_rel"]
        half_tol = cfg["half_rel"]
        
        gt_list = ground_truth.get(metric_name)
        ag_list = agent.get(metric_name)
        
        # Validation
        if not isinstance(gt_list, list) or not isinstance(ag_list, list) or len(gt_list) != len(ag_list):
            details["metrics"][metric_name] = {"points": 0.0, "status": "invalid_data"}
            continue
            
        n_atoms = len(gt_list)
        if n_atoms == 0: continue
            
        pts_per_atom = weight / n_atoms
        metric_earned = 0.0
        atom_details = []
        
        for i, (g_val, a_val) in enumerate(zip(gt_list, ag_list)):
            # Use utility for error calculation
            rel = utils.rel_error(g_val, a_val)
            
            p = 0.0
            status = "fail"
            
            if rel is not None:
                if rel <= full_tol:
                    p = pts_per_atom
                    status = "full"
                elif rel <= half_tol:
                    p = pts_per_atom * 0.5
                    status = "half"
                else:
                    status = f"out_of_tol ({rel:.2f})"
            else:
                # Handle near-zero GT where rel_error is None
                ae = utils.abs_error(g_val, a_val)
                if ae is not None and ae < 1e-3:
                    p = pts_per_atom
                    status = "full (abs)"

            metric_earned += p
            atom_details.append({"idx": i, "status": status, "pts": round(p, 4)})
            
        metric_earned = min(metric_earned, weight)
        total_pts += metric_earned
        
        details["metrics"][metric_name] = {
            "points": round(metric_earned, 2),
            "max": weight,
            "atoms": atom_details
        }

    return min(total_pts, rubric["numerical"]["total"]), details


# ---------------- Combined scorer ----------------
def score_fukui_case(
    booleans: Union[pd.DataFrame, Dict[str, Any]],
    gt_numeric: Dict[str, Any],
    agent_numeric: Dict[str, Any],
    *,
    rubric: Dict = RUBRIC_FUKUI,
) -> Dict[str, Any]:
    """
    Unified per-case scoring for Fukui.
    
    Args:
        booleans: Boolean check results.
        gt_numeric: Calculated Ground Truth.
        agent_numeric: Extracted Agent values.
        rubric: Rubric dictionary.
        
    Returns:
        Dict[str, Any]: Final scoring payload.
    """
    b_pts, b_det = score_booleans_fukui(booleans, rubric=rubric)
    n_pts, n_det = score_numerical_fukui(gt_numeric, agent_numeric, rubric=rubric)
    
    total = round(b_pts + n_pts, 3)
    
    return {
        "boolean_points": round(b_pts, 2),
        "boolean_details": b_det,
        "numerical_points": round(n_pts, 2),
        "numerical_details": n_det,
        "total_points": total,
        "max_points": rubric["metadata"]["total_max_points"]
    }