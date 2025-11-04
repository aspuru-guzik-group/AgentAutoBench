from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import re
import pandas as pd

# ---- checks used by the TDDFT job ----
from Auto_benchmark.Checks.ORCA import input_checks as ic
from Auto_benchmark.Checks.ORCA import output_common as oc
from Auto_benchmark.Checks.ORCA import output_opt as oopt
from Auto_benchmark.Checks.ORCA import output_TDDFT as otd

# ---- extractors ----
from Auto_benchmark.Extractors.TDDFT import extractor_TDDFT as gt_tddft
from Auto_benchmark.Extractors.TDDFT import TDDFT_extractor_from_md as agent_tddft

# ---- scoring ----
from Auto_benchmark.Grading.Rubrics import TDDFT as rubric_tddft
from Auto_benchmark.Grading.Scorer import TDDFT as scorer_tddft

# ---- shared helpers (IO + freq parsing) ----
from Auto_benchmark.io import fs, readers


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
# Local helpers (TDDFT-only)
# ---------------------------
def _rank_out_for_tddft(fname: str, text: str) -> Tuple[int, int, str]:
    """
    Lower rank is better.
      0: file contains a TDDFT block (singlet or triplet); 1 otherwise
      then: 0 if all freqs >= 0; 1 if no freq block; 2 if any imaginary
      then: filename for stable tiebreak
    """
    has_tddft = otd.tddft_block_executed(text)
    tddft_rank = 0 if has_tddft else 1

    freqs = fs._extract_freqs(text) or []
    if not freqs:
        freq_rank = 1
    else:
        freq_rank = 0 if all(f >= 0.0 for f in freqs) else 2

    return (tddft_rank, freq_rank, fname.lower())


def _gather_all_outs_unfiltered(folder: Path) -> List[Path]:
    """TDDFT-only: gather every *.out under folder (no SKIP_DIRS, no slurm-* exclusion)."""
    return sorted(folder.rglob("*.out"))


def find_best_out_for_tddft(folder: Path) -> Tuple[Optional[Path], Optional[str]]:
    """Return (best_path, best_text) for TDDFT extraction."""
    candidates = _gather_all_outs_unfiltered(folder)
    if not candidates:
        return None, None
    ranked: List[Tuple[Tuple[int, int, str], Path, str]] = []
    for p in candidates:
        txt = readers.read_text_safe(p)
        ranked.append((_rank_out_for_tddft(p.name, txt), p, txt))
    ranked.sort(key=lambda r: r[0])
    _, best_path, best_text = ranked[0]
    return best_path, best_text


# ---------------------------
# TDDFT helpers expected by run.py
# ---------------------------
def _compute_booleans_tddft(itexts: List[str], otexts: List[str], folder_name: str) -> Dict[str, str]:
    # INPUT checks (all inputs must satisfy each check)
    if itexts:
        meth_all = all(ic.method_exist(t) for t in itexts)
        base_all = all(ic.basis_exist(t) for t in itexts)
        task_all = all(ic.tasks_exist(t) for t in itexts)
        chmu_all = all(ic.charge_mult_exist(t) for t in itexts)
        xyz_all  = all(ic.xyz_exist(t) for t in itexts)
    else:
        meth_all = base_all = task_all = chmu_all = xyz_all = False

    # OUTPUT common
    scf_all = all(oc.scf_converged(t) for t in otexts) if otexts else False

    # OPT & FREQ
    geo_opt_any = False
    imag_freq_exist_any = False
    for ot in otexts or []:
        if oopt.geo_opt_converged(ot):
            geo_opt_any = True
        # "Imag freq exist?" = at least one imaginary frequency present
        imag_freq_exist_any = imag_freq_exist_any or (not oopt.imaginary_freq_not_exist(ot))

    # TDDFT specifics — compute from the best TDDFT .out in this folder
    tddft_block = tddft_energy = tddft_f = False
    try:
        folder_path = Path(folder_name)
        best_path, best_text = (None, None)
        if folder_path.exists():
            best_path, best_text = find_best_out_for_tddft(folder_path)
        if not best_text and otexts:
            best_text = otexts[0]
        if best_text:
            tddft_block  = otd.tddft_block_executed(best_text)
            tddft_energy = otd.excitation_energy_exist(best_text)
            tddft_f      = otd.oscillator_strengths_available(best_text)
    except Exception:
        pass

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
    """Select the correct TDDFT OUT from the folder and extract numeric ground truth."""
    empty = {
        "S1_energy_eV": None,
        "S1_oscillator_strength": None,
        "T1_energy_eV": None,
        "S1_T1_gap_eV": None,
    }
    if not outs:
        return empty
    folder = outs[0].parent
    _, best_text = find_best_out_for_tddft(folder)
    if not best_text or not otd.tddft_block_executed(best_text):
        return empty
    try:
        return gt_tddft.extract_tddft_core(best_text)
    except Exception:
        return empty


def _find_report_tddft(root: Path) -> Optional[Path]:
    """
    1) If exactly one .md in ROOT, return it.
    2) Else consider ROOT and ROOT/reports/*.md together.
    3) Prefer canonical TDDFT names, else return largest by size.
    """
    root_mds = sorted(root.glob("*.md"))
    if len(root_mds) == 1:
        return root_mds[0]

    candidates: List[Path] = []
    candidates += root_mds
    rep = root / "reports"
    if rep.is_dir():
        candidates += sorted(rep.glob("*.md"))

    if not candidates:
        return None

    preferred = [
        "Photophysical_Properties_Final_Report.md",
        "TDDFT_Report.md",
        "tddft_report.md",
        "S1_T1_summary.md",
    ]
    by_name = {p.name: p for p in candidates}
    for name in preferred:
        if name in by_name:
            return by_name[name]

    try:
        return max(candidates, key=lambda p: p.stat().st_size)
    except Exception:
        return candidates[0]


def _extract_agent_tddft(report_md: Optional[Path], folder: Path) -> Dict[str, Any]:
    """
    Extract numeric values for S1/T1 from a Markdown report produced by the agent.
    Tries (a) formula match against a Molecule table, (b) molecule index from names,
    (c) single-molecule fallback.
    """
    empty = {
        "S1_energy_eV": None,
        "S1_oscillator_strength": None,
        "T1_energy_eV": None,
        "S1_T1_gap_eV": None,
    }
    if not report_md:
        return empty

    SUBSCRIPT_MAP = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")

    def _norm_formula_string(s: str) -> str:
        s = (s or "").translate(SUBSCRIPT_MAP)
        return "".join(ch for ch in s if ch.isalnum())

    def _parse_formula_to_dict(s: str) -> Optional[Dict[str, int]]:
        if not s:
            return None
        s = _norm_formula_string(s)
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
        m = re.search(r"_(?P<form>(?:[A-Z][a-z]?\d+)+)_", folder.name)
        if m:
            return m.group("form")
        m = re.search(r"(?P<form>(?:[A-Z][a-z]?\d+){2,})", folder.name)
        if m:
            return m.group("form")
        for x in sorted(folder.glob("*.xyz")):
            m = re.search(r"_(?P<form>(?:[A-Z][a-z]?\d+)+)_", x.stem)
            if m:
                return m.group("form")
            m = re.search(r"(?P<form>(?:[A-Z][a-z]?\d+){2,})", x.stem)
            if m:
                return m.group("form")
        return None

    def _scan_report_molecule_map(md_text: str) -> List[Tuple[str, str]]:
        rows: List[Tuple[str, str]] = []
        for line in md_text.splitlines():
            m = re.match(r"^\s*\|\s*Molecule\s+(\d+)\s*\|\s*([^|]+?)\s*\|", line, flags=re.IGNORECASE)
            if not m:
                continue
            idx = int(m.group(1))
            formula_raw = m.group(2).strip()
            rows.append((f"mol{idx}", formula_raw))
        return rows

    def _has_values(d: Dict[str, Any]) -> bool:
        keys = ("S1_energy_eV", "S1_oscillator_strength", "T1_energy_eV", "S1_T1_gap_eV")
        return any(d.get(k) is not None for k in keys)

    try:
        md_text = report_md.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        md_text = ""

    folder_formula = _extract_folder_formula(folder)
    if folder_formula:
        folder_dict = _parse_formula_to_dict(folder_formula)
        for molkey, formula_raw in _scan_report_molecule_map(md_text):
            rep_dict = _parse_formula_to_dict(formula_raw)
            if rep_dict and folder_dict and rep_dict == folder_dict:
                try:
                    res = agent_tddft.extract_tddft_from_md(str(report_md), molecule=molkey)
                    if _has_values(res):
                        return res
                except Exception:
                    pass

    idx_pat = re.compile(r"\b(?:molecule|mol)[_\s-]*0*([0-9]+)\b", re.IGNORECASE)
    mol_idx: Optional[str] = None
    for p in sorted(folder.glob("*.xyz")):
        m = idx_pat.search(p.stem)
        if m:
            mol_idx = m.group(1)
            break
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


JOB: Dict[str, Any] = {
    "aggregate_across_folders": False,
    "bool_columns": TDDFT_BOOL_COLUMNS,
    "compute_booleans": _compute_booleans_tddft,
    "extract_ground_truth": _extract_ground_truth_tddft,
    "find_report": _find_report_tddft,
    "extract_agent": _extract_agent_tddft,
    "score": _score_tddft,
    "rubric": rubric_tddft.RUBRIC_TDDFT,
}
