# Auto_benchmark/Extractors/pKa/ORCA_out_extractor_pKa.py
from __future__ import annotations
import re, os
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from pathlib import Path

__all__ = [
    "GIBBS_LINE_RE",
    "SCF_CONV_RE",
    "OPT_CONV_RE",
    "TOTAL_CHARGE_RE",
    "MULTIPLICITY_RE",
    "imaginary_freq_exist",
    "parse_gibbs_free_energy",
    "extract_pka_orca_core",
    "pick_latest_orca_out",
]

# ---------------- Patterns ---------------- #
# ORCA prints several variants for Gibbs free energy; capture value + optional unit
GIBBS_LINE_RE = re.compile(
    r"""
    (?:
        ^\s*Final\s+Gibbs\s+free\s+energy\s*[:=]\s*
      | ^\s*Gibbs\s+free\s+energy\s*[:=]\s*
      | ^\s*G\s*\(\s*Gibbs\s*free\s*energy\s*\)\s*[:=]\s*
    )
    (?P<val>[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
    (?:\s*(?P<unit>Eh|Hartree|a\.?u\.?|kcal/mol|kJ/mol|eV))?
    """,
    re.I | re.M | re.X,
)

# SCF / Optimization convergence hints
SCF_CONV_RE = re.compile(r"\bSCF\s+CONVERGED\b|\bSCF\s+converged\s+after\b", re.I)
SCF_NOT_CONV_RE = re.compile(r"\bSCF\s+NOT\s+CONVERGED\b", re.I)
OPT_CONV_RE = re.compile(r"(?:OPTIMIZATION|OPTIMISATION)\s+CONVERGED", re.I)
OPT_NOT_CONV_RE = re.compile(r"(?:OPTIMIZATION|OPTIMISATION)\s+FAILED|NOT\s+CONVERGED", re.I)

# Charge / multiplicity (useful for upstream checks)
TOTAL_CHARGE_RE = re.compile(r"\bTotal\s+Charge\s*:\s*([+-]?\d+)\b", re.I)
MULTIPLICITY_RE = re.compile(r"\bMultiplicity\s*:\s*(\d+)\b", re.I)

# Vibrational frequencies block header
VIB_HEADER_RE = re.compile(r"VIBRATIONAL\s+FREQUENCIES", re.I)

# ---------------- Unit helpers ---------------- #
HARTREE_TO_EV = 27.211386245988
HARTREE_TO_KJMOL = 2625.49962
KCAL_TO_KJ = 4.184
EV_TO_KJMOL = 96.48530749925793  # 1 eV per particle = 96.485... kJ/mol

def _coerce_float(s: str) -> Optional[float]:
    try:
        return float(s)
    except Exception:
        return None

def _to_hartree(value: float, unit: Optional[str]) -> float:
    """Convert a G value to Hartree. Missing/unknown unit → assume Hartree."""
    if unit is None:
        return value
    u = unit.lower().replace(".", "")
    if u in {"eh", "hartree", "au", "a u"}:
        return value
    if u == "ev":
        # eV per particle -> Hartree
        return value / HARTREE_TO_EV
    if u == "kj/mol" or u == "kjmol":
        return value / HARTREE_TO_KJMOL
    if u == "kcal/mol" or u == "kcalmol":
        return (value * KCAL_TO_KJ) / HARTREE_TO_KJMOL
    # fallback assume Hartree
    return value

def _hartree_to_ev(h: float) -> float:
    return h * HARTREE_TO_EV

def _hartree_to_kjmol(h: float) -> float:
    return h * HARTREE_TO_KJMOL

# ---------------- Data model ---------------- #
@dataclass
class GibbsEntry:
    value_hartree: float
    raw_line: str = ""

# ---------------- Parsers ---------------- #
def parse_gibbs_free_energy(out_text: str) -> Optional[GibbsEntry]:
    """
    Return the *last* reported Gibbs free energy converted to Hartree.
    (ORCA usually prints at most a few; we use the last as the final value.)
    """
    last: Optional[GibbsEntry] = None
    for m in GIBBS_LINE_RE.finditer(out_text):
        val = _coerce_float(m.group("val"))
        unit = m.group("unit")
        if val is None:
            continue
        hartree = _to_hartree(val, unit)
        last = GibbsEntry(value_hartree=hartree, raw_line=m.group(0))
    return last

def imaginary_freq_exist(out_text: str) -> bool:
    """
    True if any vibrational frequency is negative in the 'VIBRATIONAL FREQUENCIES' block.
    """
    lines = out_text.splitlines()
    in_block = False
    for ln in lines:
        if VIB_HEADER_RE.search(ln):
            in_block = True
            continue
        if in_block and not ln.strip():
            break
        if in_block:
            for num in re.findall(r"[-+]?\d+\.\d+", ln):
                try:
                    if float(num) < 0.0:
                        return True
                except Exception:
                    pass
    return False

def scf_converged(out_text: str) -> Optional[bool]:
    if SCF_NOT_CONV_RE.search(out_text):
        return False
    if SCF_CONV_RE.search(out_text):
        return True
    return None  # unknown

def opt_converged(out_text: str) -> Optional[bool]:
    if OPT_NOT_CONV_RE.search(out_text):
        return False
    if OPT_CONV_RE.search(out_text):
        return True
    return None  # unknown

def charge_and_mult(out_text: str) -> Tuple[Optional[int], Optional[int]]:
    q = None
    m = None
    qm = TOTAL_CHARGE_RE.search(out_text)
    mm = MULTIPLICITY_RE.search(out_text)
    if qm:
        try:
            q = int(qm.group(1))
        except Exception:
            pass
    if mm:
        try:
            m = int(mm.group(1))
        except Exception:
            pass
    return q, m

# ---------------- Folder helper ---------------- #
def pick_latest_orca_out(folder: Path) -> Optional[Path]:
    """
    Pick the newest ORCA .out under a folder, skipping slurm logs and bookkeeping dirs.
    """
    def _not_forbidden(p: Path) -> bool:
        forbidden = {"results", "jobinfo"}
        return not any(part.lower() in forbidden for part in p.parts)

    outs = [
        p for p in folder.rglob("*.out")
        if _not_forbidden(p) and not p.name.lower().startswith("slurm")
    ]
    if not outs:
        return None
    outs.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return outs[0]

# ---------------- Core extraction API ---------------- #
def extract_pka_orca_core(out_text: str) -> Dict[str, Optional[float | bool]]:
    """
    Extract pKa-relevant core values/flags from a single ORCA output:

      Returns dict with:
        - gibbs_free_energy_hartree: float|None
        - gibbs_free_energy_eV: float|None
        - gibbs_free_energy_kJmol: float|None
        - deltaG_exist: bool           # for rubric Section 2
        - imaginary_freq_exist: bool   # 'no' is desired in rubric Section 1
        - scf_converged: bool|None
        - geo_opt_converged: bool|None
        - total_charge: int|None
        - multiplicity: int|None
    """
    result: Dict[str, Optional[float | bool]] = {
        "gibbs_free_energy_hartree": None,
        "gibbs_free_energy_eV": None,
        "gibbs_free_energy_kJmol": None,
        "deltaG_exist": False,
        "imaginary_freq_exist": False,
        "scf_converged": None,
        "geo_opt_converged": None,
        "total_charge": None,
        "multiplicity": None,
    }

    # Gibbs
    g = parse_gibbs_free_energy(out_text)
    if g is not None:
        result["gibbs_free_energy_hartree"] = g.value_hartree
        result["gibbs_free_energy_eV"] = _hartree_to_ev(g.value_hartree)
        result["gibbs_free_energy_kJmol"] = _hartree_to_kjmol(g.value_hartree)
        result["deltaG_exist"] = True  # presence == True for rubric Section 2

    # QC flags
    result["imaginary_freq_exist"] = imaginary_freq_exist(out_text)
    result["scf_converged"] = scf_converged(out_text)
    result["geo_opt_converged"] = opt_converged(out_text)

    # Charge & multiplicity
    q, m = charge_and_mult(out_text)
    result["total_charge"] = q
    result["multiplicity"] = m

    return result

# ---------------- Convenience: folder → dict ---------------- #
def extract_pka_orca_core_from_folder(folder_path: str) -> Dict[str, Optional[float | bool]]:
    """
    Scan a folder, pick the newest ORCA .out, and run extract_pka_orca_core on it.
    Mirrors your existing pKa directory scan (skips slurm/results/jobinfo).
    """
    folder = Path(folder_path)
    outp = pick_latest_orca_out(folder)
    if outp is None:
        return {
            "file": None,
            "gibbs_free_energy_hartree": None,
            "gibbs_free_energy_eV": None,
            "gibbs_free_energy_kJmol": None,
            "deltaG_exist": False,
            "imaginary_freq_exist": False,
            "scf_converged": None,
            "geo_opt_converged": None,
            "total_charge": None,
            "multiplicity": None,
        }
    text = outp.read_text(errors="ignore")
    data = extract_pka_orca_core(text)
    data["file"] = str(outp)
    return data
