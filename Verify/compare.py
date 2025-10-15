# Verify/compare.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional, Tuple, Union, Callable

Number = Union[int, float]
TolSpec = Union[Tuple[float, float], float, Callable[[Any, Any], bool]]

@dataclass(frozen=True)
class FieldRule:
    """Definition of one field to compare."""
    name: str
    kind: str = "number"   # 'number' | 'string' | 'bool'
    tolerance: Optional[TolSpec] = None  # numeric tolerance
    required: bool = True  # skip scoring if ground truth missing


# ---------- Internal helpers ----------
def _to_number(x: Any) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip().lower()
        if s in {"", "do not exist", "none", "nan", "null"}:
            return None
        try:
            return float(s)
        except Exception:
            return None
    return None


def _compare_number(gt: Optional[Number], pred: Optional[Number], tol: Optional[TolSpec]) -> Tuple[bool, Dict[str, Any]]:
    if gt is None or pred is None:
        return (False, {"gt": gt, "pred": pred, "reason": "missing"})

    gtf, prf = float(gt), float(pred)

    if callable(tol):
        ok = bool(tol(gtf, prf))
        return (ok, {"gt": gtf, "pred": prf, "mode": "callable"})

    if tol is None:
        ok = (gtf == prf)
        return (ok, {"gt": gtf, "pred": prf, "mode": "exact"})

    if isinstance(tol, (int, float)):
        atol, rtol = float(tol), 0.0
    else:
        atol, rtol = float(tol[0]), float(tol[1])

    diff = abs(gtf - prf)
    thr = atol + rtol * abs(gtf)
    return (diff <= thr, {"gt": gtf, "pred": prf, "diff": diff, "threshold": thr, "mode": "atol/rtol"})


def _compare_string(gt: Optional[str], pred: Optional[str]) -> Tuple[bool, Dict[str, Any]]:
    if gt is None or pred is None:
        return (False, {"gt": gt, "pred": pred, "reason": "missing"})
    return (str(gt).strip() == str(pred).strip(), {"gt": gt, "pred": pred, "mode": "exact"})


def _compare_bool(gt: Optional[bool], pred: Optional[bool]) -> Tuple[bool, Dict[str, Any]]:
    if gt is None or pred is None:
        return (False, {"gt": gt, "pred": pred, "reason": "missing"})
    return (bool(gt) == bool(pred), {"gt": bool(gt), "pred": bool(pred), "mode": "exact"})


def _coerce(kind: str, x: Any) -> Any:
    if kind == "number":
        return _to_number(x)
    if kind == "bool":
        if isinstance(x, bool):
            return x
        if isinstance(x, str):
            s = x.strip().lower()
            if s in {"true", "yes", "1"}:  return True
            if s in {"false", "no", "0"}:  return False
        return None
    return None if x is None else str(x).strip()


# ---------- Main comparison ----------
def compare_payloads(
    ground_truth: Dict[str, Any],
    agent: Dict[str, Any],
    rules: Iterable[FieldRule],
    *,
    score_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Universal comparison between ground truth and agent answers.

    Args:
        ground_truth: parsed data from .out (benchmark answer)
        agent: extracted data from agent output (.md)
        rules: list of FieldRule objects defining fields & tolerances
        score_weights: optional per-field weight dict

    Returns:
        dict with:
            {
              "per_field": {...},
              "score": float (0–100),
              "missing_gt": [fields missing from GT]
            }
    """
    results = {}
    missing_gt = []
    weights = score_weights or {}
    default_w = 1.0
    total_w = 0.0
    gained_w = 0.0

    for rule in rules:
        gt_val_raw = ground_truth.get(rule.name)
        ag_val_raw = agent.get(rule.name)
        gt_val = _coerce(rule.kind, gt_val_raw)
        ag_val = _coerce(rule.kind, ag_val_raw)

        if rule.required and gt_val is None:
            missing_gt.append(rule.name)
            results[rule.name] = {"ok": False, "details": {"gt": gt_val, "pred": ag_val, "reason": "ground_truth_missing"}}
            continue

        if rule.kind == "number":
            ok, info = _compare_number(gt_val, ag_val, rule.tolerance)
        elif rule.kind == "bool":
            ok, info = _compare_bool(gt_val, ag_val)
        else:
            ok, info = _compare_string(gt_val, ag_val)

        results[rule.name] = {"ok": ok, "details": info}

        w = float(weights.get(rule.name, default_w))
        total_w += w
        if ok:
            gained_w += w

    score = 0.0 if total_w == 0 else 100.0 * gained_w / total_w
    return {"per_field": results, "score": round(score, 3), "missing_gt": missing_gt}