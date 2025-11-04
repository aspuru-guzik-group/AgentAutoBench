from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional
import os
import re
import pandas as pd

# ---- Checks ----
from Auto_benchmark.Checks.ORCA import input_checks as ic
from Auto_benchmark.Checks.ORCA import output_common as oc
from Auto_benchmark.Checks.ORCA import output_opt as oopt

# ---- Extractors ----
from Auto_benchmark.Extractors.RingStrain import extractor_RS as orca_rs
from Auto_benchmark.Extractors.RingStrain import RS_extractor_from_md as agent_rs
from Auto_benchmark.Extractors.RingStrain import ringstrain_calc

# ---- Rubric & Scorer ----
from Auto_benchmark.Grading.Rubrics import RingStrain as rubric_rs
from Auto_benchmark.Grading.Scorer import RingStrain as scorer_rs

# ---- Config ----
from Auto_benchmark.Config.defaults import HARTREE_TO_KCAL as _HARTREE_TO_KCAL

# ---------------------------
# Boolean column schema
# ---------------------------
RINGSTRAIN_BOOL_COLUMNS: List[str] = [
    "Folder",
    "Method exist?",
    "Basis set exist?",
    "Tasks exist?",
    "Charge & mult exist?",
    "XYZ file exist?",
    "SCF converged?",
    "Geo opt converged?",
    "Imag freq exist?",   # scorer awards when this is "no"
]

# ---------------------------
# Booleans
# ---------------------------
def _compute_booleans_rs(itexts: List[str], otexts: List[str], folder_name: str) -> Dict[str, str]:
    if itexts:
        meth_all = all(ic.method_exist(t) for t in itexts)
        base_all = all(ic.basis_exist(t) for t in itexts)
        task_all = all(ic.tasks_exist(t) for t in itexts)
        chmu_all = all(ic.charge_mult_exist(t) for t in itexts)
        xyz_all  = all(ic.xyz_exist(t) for t in itexts)
    else:
        meth_all = base_all = task_all = chmu_all = xyz_all = False

    scf_any = any(oc.scf_converged(t) for t in otexts) if otexts else False
    geo_opt_any = any(oopt.geo_opt_converged(t) for t in otexts) if otexts else False
    imag_freq_exist_any = any(not oopt.imaginary_freq_not_exist(t) for t in otexts) if otexts else False

    return {
        "Folder": folder_name,
        "Method exist?": "yes" if meth_all else "no",
        "Basis set exist?": "yes" if base_all else "no",
        "Tasks exist?": "yes" if task_all else "no",
        "Charge & mult exist?": "yes" if chmu_all else "no",
        "XYZ file exist?": "yes" if xyz_all else "no",
        "SCF converged?": "yes" if scf_any else "no",
        "Geo opt converged?": "yes" if geo_opt_any else "no",
        "Imag freq exist?": "yes" if imag_freq_exist_any else "no",
    }

# ---------------------------
# Ground truth extraction (per-folder, simple)
# NOTE: include FolderPath so scoring can do structure-based mapping.
# ---------------------------
def _extract_ground_truth_rs(otexts: List[str], outs: List[Path]) -> Dict[str, Any]:
    """
    Return per-folder totals. The runner aggregates these across folders.
    We also include 'FolderPath' (absolute path to the folder) for structure mapping.
    """
    folder_name: Optional[str] = None
    folder_path: Optional[str] = None
    try:
        if outs and isinstance(outs[0], Path):
            folder = outs[0].parent
            folder_name = folder.name
            folder_path = str(folder.resolve())
    except Exception:
        folder_name = folder_name or None
        folder_path = folder_path or None

    if not otexts:
        return {"Folder": folder_name, "FolderPath": folder_path, "H_total_au": None, "G_total_au": None}

    txt = otexts[0]
    try:
        core = orca_rs.extract_rs_core(txt)
    except Exception:
        core = {}

    return {
        "Folder": folder_name,
        "FolderPath": folder_path,
        "H_total_au": core.get("H_total_au"),
        "G_total_au": core.get("G_total_au"),
    }

# ---------------------------
# Report finder + agent extractor
# ---------------------------
def _find_report_rs(root: Path) -> Optional[Path]:
    candidates: List[Path] = []
    candidates += sorted(root.glob("*.md"))
    rep = root / "reports"
    if rep.is_dir():
        candidates += sorted(rep.glob("*.md"))
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    preferred = {
        "RingStrain_Report.md",
        "ring_strain.md",
        "ringstrain.md",
        "Photophysical_Properties_Final_Report.md",
    }
    by_name = {p.name: p for p in candidates}
    for name in preferred:
        if name in by_name:
            return by_name[name]

    try:
        return max(candidates, key=lambda p: p.stat().st_size)
    except Exception:
        return candidates[0]

def _extract_agent_rs(report_md: Optional[Path], folder: Path) -> Dict[str, Any]:
    if not report_md:
        return {"rows": {}, "reference_is_cyclohexane": False}
    try:
        return agent_rs.extract_ringstrain_from_md(str(report_md))
    except Exception:
        return {"rows": {}, "reference_is_cyclohexane": False}

# ---------------------------
# Helpers for structure-based scoring
# ---------------------------
def _common_root_from_paths(paths: List[str]) -> Optional[Path]:
    try:
        abs_paths = [str(Path(p).resolve()) for p in paths if p]
        if not abs_paths:
            return None
        import os
        common = os.path.commonpath(abs_paths)
        return Path(common)
    except Exception:
        return None

def _overlay_energies_from_gt(
    cyclo: Dict[int, Dict[str, Any]],
    methyl: Dict[int, Dict[str, Any]],
    gt_df: pd.DataFrame,
) -> None:
    """
    Overlay H/G from aggregated per-folder rows onto structure maps by matching folder paths/basenames.
    """
    import os
    # Build quick lookups from GT
    gt_by_path = {}
    gt_by_base = {}
    for _, r in gt_df.iterrows():
        fp = str(r.get("FolderPath") or "").strip()
        fb = str(r.get("Folder") or "").strip()
        H = r.get("H_total_au"); G = r.get("G_total_au")
        try: H = float(H) if H not in (None, "") else None
        except Exception: H = None
        try: G = float(G) if G not in (None, "") else None
        except Exception: G = None
        if fp:
            gt_by_path[os.path.normpath(fp)] = (H, G)
        if fb:
            gt_by_base[fb] = (H, G)

    def _apply(rec: Dict[str, Any]) -> None:
        folder: Path = rec["folder"]
        key_path = os.path.normpath(str(folder.resolve()))
        H, G = None, None
        if key_path in gt_by_path:
            H, G = gt_by_path[key_path]
        else:
            base = folder.name
            if base in gt_by_base:
                H, G = gt_by_base[base]
        if H is not None:
            rec["H_au"] = H
        if G is not None:
            rec["G_au"] = G

    for d in (cyclo, methyl):
        for _, rec in d.items():
            _apply(rec)

# ---------------------------
# Scoring wrapper (STRUCTURE-BASED)
# ---------------------------
def _score_rs(
    booleans: pd.DataFrame,
    gt_numeric: Any,
    agent_numeric: Dict[str, Any],
    rubric: Dict[str, Any],
    **kwargs,
) -> Dict[str, Any]:
    """
    Structure-based GT with cyclo/methyl mapping and cumulative strain anchored at n=6.
    (Debug prints omitted here for brevity.)
    """
    # ---- 1) Normalize aggregated GT rows to DataFrame ----
    if isinstance(gt_numeric, pd.DataFrame):
        gt_df = gt_numeric.copy()
    else:
        gt_df = pd.DataFrame(gt_numeric or [])
    for col in ("Folder", "FolderPath", "H_total_au", "G_total_au"):
        if col not in gt_df.columns:
            gt_df[col] = None

    # ---- 2) Derive dataset root and build structure maps ----
    folder_paths = [p for p in gt_df["FolderPath"].fillna("").tolist() if p]
    root = _common_root_from_paths(folder_paths)
    if root is None:
        return scorer_rs.score_ringstrain(
            booleans=booleans,
            ground_truth_rows={},
            agent_rows={(int(k) if str(k).isdigit() else k): v for k, v in (agent_numeric or {}).get("rows", {}).items()},
            reference_is_cyclohexane=bool((agent_numeric or {}).get("reference_is_cyclohexane", False)),
            rubric=rubric,
        )

    cyclo, methyl = ringstrain_calc.build_structure_energy_maps(root)

    # ---- 3) Overlay energies from aggregated GT onto maps ----
    _overlay_energies_from_gt(cyclo, methyl, gt_df)

    # ---- 4) Adjacent reaction energies in kcal/mol ----
    dH_by_n: Dict[int, Optional[float]] = {}
    dG_by_n: Dict[int, Optional[float]] = {}

    candidate_ns = sorted(set(cyclo.keys()) | {m + 1 for m in methyl.keys()})
    for n in candidate_ns:
        m = n - 1
        dH = dG = None
        cyc = cyclo.get(n)
        met = methyl.get(m)
        if cyc and met:
            Hc = cyc.get("H_au"); Gc = cyc.get("G_au")
            Hm = met.get("H_au"); Gm = met.get("G_au")
            try:
                if (Hm is not None) and (Hc is not None):
                    dH = (float(Hm) - float(Hc)) * _HARTREE_TO_KCAL
            except Exception:
                dH = None
            try:
                if (Gm is not None) and (Gc is not None):
                    dG = (float(Gm) - float(Gc)) * _HARTREE_TO_KCAL
            except Exception:
                dG = None
        dH_by_n[int(n)] = dH
        dG_by_n[int(n)] = dG

    # ---- 5) Cumulative strain series S (anchored at n=6) ----
    rubric_sizes = set(rubric["numerical"]["config"]["ring_sizes_for_scoring"])
    all_ns = sorted(set(candidate_ns) | rubric_sizes | {6})

    S_H: Dict[int, Optional[float]] = {6: 0.0}
    S_G: Dict[int, Optional[float]] = {6: 0.0}

    for n in sorted([k for k in all_ns if k > 6]):
        prev = n - 1
        dH = dH_by_n.get(n); dG = dG_by_n.get(n)
        S_H[n] = (S_H.get(prev) + dH) if (S_H.get(prev) is not None and dH is not None) else None
        S_G[n] = (S_G.get(prev) + dG) if (S_G.get(prev) is not None and dG is not None) else None

    for n in sorted([k for k in all_ns if k < 6], reverse=True):
        nxt = n + 1
        dH = dH_by_n.get(nxt); dG = dG_by_n.get(nxt)
        S_H[n] = (S_H.get(nxt) - dH) if (S_H.get(nxt) is not None and dH is not None) else None
        S_G[n] = (S_G.get(nxt) - dG) if (S_G.get(nxt) is not None and dG is not None) else None

    gt_rows: Dict[int, Dict[str, Any]] = {}
    for n in all_ns:
        if n not in rubric_sizes:
            continue
        gt_rows[int(n)] = {
            "ring_size": int(n),
            "strain_delta_H_kcal_mol": S_H.get(n, None),
            "strain_delta_G_kcal_mol": S_G.get(n, None),
        }

    agent_rows_raw = (agent_numeric or {}).get("rows", {}) if isinstance(agent_numeric, dict) else {}
    agent_rows: Dict[int, Dict[str, Any]] = {}
    for k, v in (agent_rows_raw or {}).items():
        try:
            agent_rows[int(k)] = v
        except Exception:
            continue

    ref_ok = bool((agent_numeric or {}).get("reference_is_cyclohexane", False))

    return scorer_rs.score_ringstrain(
        booleans=booleans,
        ground_truth_rows=gt_rows,
        agent_rows=agent_rows,
        reference_is_cyclohexane=ref_ok,
        rubric=rubric,
    )


# ---------------------------
# Exported JOB spec
# ---------------------------
JOB: Dict[str, Any] = {
    "aggregate_across_folders": True,  # runner aggregates per-folder GT rows, which _score_rs consumes
    "bool_columns": RINGSTRAIN_BOOL_COLUMNS,
    "compute_booleans": _compute_booleans_rs,
    "extract_ground_truth": _extract_ground_truth_rs,
    "find_report": _find_report_rs,
    "extract_agent": _extract_agent_rs,
    "score": _score_rs,
    "rubric": rubric_rs.RUBRIC_RINGSTRAIN,
}
