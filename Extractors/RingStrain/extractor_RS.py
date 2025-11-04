# Auto_benchmark/Extractors/RingStrain/extractor_RS.py
from __future__ import annotations
import re
from typing import Dict, Optional, Tuple

__all__ = ["extract_rs_core"]

# -----------------------------
# Robust patterns for ORCA outputs
# -----------------------------
_RE_H = re.compile(r"Total\s+Enthalpy\s+.*?([+-]?\d+\.\d+)\s*Eh", re.I)
_RE_G = re.compile(r"Final\s+Gibbs\s+free\s+energy\s+.*?([+-]?\d+\.\d+)\s*Eh", re.I)
# Fallback if enthalpy is missing
_RE_ELEC_FALLBACK = re.compile(r"FINAL\s+SINGLE\s+POINT\s+ENERGY\s+([+-]?\d+\.\d+)", re.I)


def _extract_enthalpy_gibbs(txt: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Return (H_total_au, G_total_au) from an ORCA .out text.
    If 'Total Enthalpy' is missing, fall back to 'FINAL SINGLE POINT ENERGY' for H.
    """
    H = G = None

    mh = list(_RE_H.finditer(txt))
    if mh:
        H = float(mh[-1].group(1))  # use the last occurrence

    mg = list(_RE_G.finditer(txt))
    if mg:
        G = float(mg[-1].group(1))

    if H is None:
        me = list(_RE_ELEC_FALLBACK.finditer(txt))
        if me:
            H = float(me[-1].group(1))

    return H, G


def extract_rs_core(txt: str) -> Dict[str, Optional[float]]:
    """
    Public API: extract ΔH and ΔG in atomic units from an ORCA output text.

    Returns:
        {
          "H_total_au": float | None,
          "G_total_au": float | None
        }
    """
    H, G = _extract_enthalpy_gibbs(txt)
    return {"H_total_au": H, "G_total_au": G}
