# Auto_benchmark/registry/jobs.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import re

# ---- import the concrete modules your TDDFT job will use ----
from Auto_benchmark.Checks import input_checks as ic
from Auto_benchmark.Checks import output_common as oc
from Auto_benchmark.Checks import output_opt as oopt
from Auto_benchmark.Checks import output_TDDFT as otd

from Auto_benchmark.Extractors.TDDFT import extractor_TDDFT as gt_tddft
from Auto_benchmark.Extractors.TDDFT import TDDFT_extractor_from_md as agent_tddft

from Auto_benchmark.Grading.Rubrics import TDDFT as rubric_tddft
from Auto_benchmark.Grading.Scorer import TDDFT as scorer_tddft


# ---------------------------
# TDDFT: boolean column schema
# ---------------------------
TDDFT_BOOL_COLUMNS: List[str] = [
    "Folder",
    "Method exist?",
    "Basis set exist?",
    "Tasks exist?",
    "Charge & mult exist?",
    "XYZ file exist?",
    "SCF converged?",
    "Geo opt converged?",
    "Imag freq exist?",
    "TDDFT block executed?",
    "Excitation energy exist?",
    "Oscillator strengths available?",
]


# ---------------------------
# TDDFT helpers expected by run.py
# ---------------------------
def _compute_booleans_tddft(itexts: List[str], otexts: List[str], folder_name: str) -> Dict[str, str]:
    if itexts:
        meth_all = all(ic.method_exist(t) for t in itexts)
        base_all = all(ic.basis_exist(t) for t in itexts)
        task_all = all(ic.tasks_exist(t) for t in itexts)
        chmu_all = all(ic.charge_mult_exist(t) for t in itexts)
        xyz_all  = all(ic.xyz_exist(t) for t in itexts)
    else:
        meth_all = base_all = task_all = chmu_all = xyz_all = False

    scf_all = all(oc.scf_converged(t) for t in otexts) if otexts else False

    geo_opt_any = False
    imag_freq_exist_any = False
    for ot in otexts:
        if oopt.geo_opt_converged(ot):
            geo_opt_any = True
        imag_freq_exist_any = imag_freq_exist_any or (not oopt.imaginary_freq_not_exist(ot))

    tddft_block = False
    tddft_energy = False
    tddft_f = False
    for ot in otexts:
        if otd.tddft_block_executed(ot):
            tddft_block = True
            if otd.excitation_energy_exist(ot):
                tddft_energy = True
            if otd.oscillator_strengths_available(ot):
                tddft_f = True

    return {
        "Method exist?": "yes" if meth_all else "no",
        "Basis set exist?": "yes" if base_all else "no",
        "Tasks exist?": "yes" if task_all else "no",
        "Charge & mult exist?": "yes" if chmu_all else "no",
        "XYZ file exist?": "yes" if xyz_all else "no",
        "SCF converged?": "yes" if scf_all else "no",
        "Geo opt converged?": "yes" if geo_opt_any else "no",
        "Imag freq exist?": "yes" if imag_freq_exist_any else "no",
        "TDDFT block executed?": "yes" if tddft_block else "no",
        "Excitation energy exist?": "yes" if tddft_energy else "no",
        "Oscillator strengths available?": "yes" if tddft_f else "no",
    }


def _extract_ground_truth_tddft(otexts: List[str], outs: List[Path]) -> Dict[str, Any]:
    for p, ot in zip(outs, otexts):
        if otd.tddft_block_executed(ot):
            return gt_tddft.extract_tddft_core(ot)
    return {
        "S1_energy_eV": None,
        "S1_oscillator_strength": None,
        "T1_energy_eV": None,
        "S1_T1_gap_eV": None,
    }


def _find_report_tddft(root: Path) -> Optional[Path]:
    """
    Locate the TDDFT Markdown report in either the root or the 'reports/' subfolder.
    Prefers well-known filenames when multiple candidates exist.
    """
    candidates: List[Path] = []

    # 1) .md in root
    candidates += sorted(root.glob("*.md"))

    # 2) .md in 'reports/' subdir
    rep = root / "reports"
    if rep.is_dir():
        candidates += sorted(rep.glob("*.md"))

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    preferred = {
        "Photophysical_Properties_Final_Report.md",
        "TDDFT_Report.md",
        "tddft_report.md",
        "S1_T1_summary.md",
    }
    by_name = {p.name: p for p in candidates}
    for name in preferred:
        if name in by_name:
            return by_name[name]

    # Fallback: choose the largest file (often the full report)
    try:
        return max(candidates, key=lambda p: p.stat().st_size)
    except Exception:
        return candidates[0]


def _extract_agent_tddft(report_md: Optional[Path], folder: Path) -> Dict[str, Any]:
    """
    Map each folder to the correct molecule row by matching molecular *formula* in the report's table
    to the formula embedded in the folder (or .xyz filename). Once we find the matching row, extract
    values using the LLM-backed extractor constrained to that molecule key (e.g., 'mol3').

    Fallbacks:
      1) If formula mapping fails, try inferring the molecule index (molN) from the folder/.xyz.
      2) If still unresolved and the report appears single-molecule, parse the whole report.
    """
    empty = {
        "S1_energy_eV": None,
        "S1_oscillator_strength": None,
        "T1_energy_eV": None,
        "S1_T1_gap_eV": None,
    }
    if not report_md:
        return empty

    # ----------------------------
    # Helpers
    # ----------------------------
    SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

    def _norm_formula_string(s: str) -> str:
        # Normalize subscripts to ascii digits; keep only letters/digits.
        s = (s or "").translate(SUBSCRIPT_MAP)
        return "".join(ch for ch in s if ch.isalnum())

    def _parse_formula_to_dict(s: str) -> Optional[Dict[str, int]]:
        """Parse a chemical formula string into an element->count dict (order-agnostic)."""
        if not s:
            return None
        s = _norm_formula_string(s)
        # Must start with an element
        if not re.match(r"^[A-Z][a-z]?", s):
            return None
        parts = re.findall(r"([A-Z][a-z]?)(\d*)", s)
        if not parts:
            return None
        out: Dict[str, int] = {}
        for el, cnt in parts:
            n = int(cnt) if cnt else 1
            out[el] = out.get(el, 0) + n
        return out

    def _extract_folder_formula(folder: Path) -> Optional[str]:
        """
        Try to find a compact formula token in the folder name (e.g., _C13H10N2_)
        or in any .xyz filename in the folder.
        """
        # 1) Look for an underscore-delimited formula (requires digits to reduce false positives)
        m = re.search(r"_(?P<form>(?:[A-Z][a-z]?\d+)+)_", folder.name)
        if m:
            return m.group("form")

        # 2) Look for a compact multi-token formula anywhere (two or more element+digits tokens)
        m = re.search(r"(?P<form>(?:[A-Z][a-z]?\d+){2,})", folder.name)
        if m:
            return m.group("form")

        # 3) Try .xyz filenames
        xyzs = sorted(folder.glob("*.xyz"))
        for x in xyzs:
            m = re.search(r"_(?P<form>(?:[A-Z][a-z]?\d+)+)_", x.stem)
            if m:
                return m.group("form")
            m = re.search(r"(?P<form>(?:[A-Z][a-z]?\d+){2,})", x.stem)
            if m:
                return m.group("form")

        return None

    def _scan_report_molecule_map(md_text: str) -> List[Tuple[str, str]]:
        """
        Parse the Markdown table to (mol_key, formula_string) rows.
        Expects rows like:
          | Molecule 3 | C₁₃H₁₀N₂ | 1.697 | 0.254 | 0.023 |
        Returns list of (molkey, formula) where molkey is 'mol3'.
        """
        rows: List[Tuple[str, str]] = []
        for line in md_text.splitlines():
            # match a table row with "Molecule N" in the first column
            m = re.match(
                r"^\s*\|\s*Molecule\s+(\d+)\s*\|\s*([^|]+?)\s*\|",
                line,
                flags=re.IGNORECASE,
            )
            if not m:
                continue
            idx = int(m.group(1))
            formula_raw = m.group(2).strip()
            rows.append((f"mol{idx}", formula_raw))
        return rows

    def _has_values(d: Dict[str, Any]) -> bool:
        keys = ("S1_energy_eV", "S1_oscillator_strength", "T1_energy_eV", "S1_T1_gap_eV")
        return any(d.get(k) is not None for k in keys)

    # ----------------------------
    # 1) Formula-based mapping
    # ----------------------------
    try:
        md_text = report_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        md_text = ""

    folder_formula = _extract_folder_formula(folder)
    if folder_formula:
        folder_dict = _parse_formula_to_dict(folder_formula)

        report_rows = _scan_report_molecule_map(md_text)
        for molkey, formula_raw in report_rows:
            rep_dict = _parse_formula_to_dict(formula_raw)
            if rep_dict and folder_dict and rep_dict == folder_dict:
                try:
                    res = agent_tddft.extract_tddft_from_md(str(report_md), molecule=molkey)
                    if _has_values(res):
                        return res
                except Exception:
                    pass

    # ----------------------------
    # 2) Fallback: infer mol index from folder/.xyz and try 'molN'
    # ----------------------------
    idx_pat = re.compile(r"\b(?:molecule|mol)[_\s-]*0*([0-9]+)\b", re.IGNORECASE)
    mol_idx: Optional[str] = None

    # from .xyz
    for p in sorted(folder.glob("*.xyz")):
        m = idx_pat.search(p.stem)
        if m:
            mol_idx = m.group(1)
            break
    # from folder name
    if mol_idx is None:
        m = idx_pat.search(folder.name)
        if m:
            mol_idx = m.group(1)

    if mol_idx is not None:
        molkey = f"mol{int(mol_idx)}"
        try:
            res = agent_tddft.extract_tddft_from_md(str(report_md), molecule=molkey)
            if _has_values(res):
                return res
        except Exception:
            pass

    # ----------------------------
    # 3) Final fallback: single-molecule report → parse whole doc
    # ----------------------------
    mol_tokens = len(re.findall(r"\bMolecule\s+\d+\b", md_text, flags=re.IGNORECASE))
    if mol_tokens <= 1:
        try:
            res_full = agent_tddft.extract_tddft_from_md(str(report_md), molecule=None)
            if _has_values(res_full):
                return res_full
        except Exception:
            pass

    return empty



def _score_tddft(booleans: pd.DataFrame, gt_numeric: Dict[str, Any], agent_numeric: Dict[str, Any], rubric) -> Dict[str, Any]:
    return scorer_tddft.score_tddft_case(
        booleans=booleans,
        gt_numeric=gt_numeric,
        agent_numeric=agent_numeric,
        json_proof=True,
        rubric=rubric,
    )


_JOBS: Dict[str, Dict[str, Any]] = {
    "tddft": {
        "bool_columns": TDDFT_BOOL_COLUMNS,
        "compute_booleans": _compute_booleans_tddft,
        "extract_ground_truth": _extract_ground_truth_tddft,
        "find_report": _find_report_tddft,
        "extract_agent": _extract_agent_tddft,
        "score": _score_tddft,
        "rubric": rubric_tddft.RUBRIC_TDDFT,
    },
    "tddft_sp": {
        "bool_columns": TDDFT_BOOL_COLUMNS,
        "compute_booleans": _compute_booleans_tddft,
        "extract_ground_truth": _extract_ground_truth_tddft,
        "find_report": _find_report_tddft,
        "extract_agent": _extract_agent_tddft,
        "score": _score_tddft,
        "rubric": rubric_tddft.RUBRIC_TDDFT,
    },
}


def get_job(job_type: str) -> Dict[str, Any]:
    key = (job_type or "").strip().lower()
    if key not in _JOBS:
        available = ", ".join(sorted(_JOBS.keys()))
        raise KeyError(f"Unknown job '{job_type}'. Available: {available}")
    return _JOBS[key]

