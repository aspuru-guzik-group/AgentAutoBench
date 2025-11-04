from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List
import re

from pydantic import BaseModel, Field
from ElAgente.Agent import StructureOutputAgent

# ---------- unicode normalization ----------
# Normalize common Unicode punctuation to ASCII so regex works on negatives like “−13.88”
def _normalize(md: str) -> str:
    # minus signs & dashes that often show up from editors/exporters
    md = md.replace("\u2212", "-")   # minus sign
    md = md.replace("\u2012", "-")   # figure dash
    md = md.replace("\u2013", "-")   # en dash
    md = md.replace("\u2014", "-")   # em dash (rare in numbers but harmless)
    md = md.replace("\u00A0", " ")   # nonbreaking space
    return md

# ---------- regex helpers (fast path) ----------
# Matches rows like: "| 3 | -13.88 | -12.81 |" with optional +/− and unit hints nearby
ROW_RE = re.compile(
    r"^\s*\|\s*(\d+)\s*\|\s*([+\-]?\d+(?:\.\d+)?)\s*\|\s*([+\-]?\d+(?:\.\d+)?)\s*\|\s*$",
    re.M,
)

def _regex_table_extract(md: str) -> Dict[int, Dict[str, float]]:
    md = _normalize(md)
    # Require a kcal/mol context somewhere near the header to reduce false positives
    header_ok = re.search(r"kcal\s*/\s*mol", md, re.I) is not None
    out: Dict[int, Dict[str, float]] = {}
    for m in ROW_RE.finditer(md):
        if not header_ok:
            continue
        n = int(m.group(1))
        dH = float(m.group(2))
        dG = float(m.group(3))
        out[n] = {
            "ring_size": n,
            "strain_delta_H_kcal_mol": dH,
            "strain_delta_G_kcal_mol": dG,
        }
    return out

# ---------- reference detection ----------
_REF_CHEX_RE = re.compile(
    r"\b(cyclohexane)\b.*\b(reference\s+point|zero\s+strain\s+energy)\b", re.I
)

def _detect_cyclohexane_reference(md: str) -> bool:
    md_norm = _normalize(md)
    return _REF_CHEX_RE.search(md_norm) is not None

# ---------- LLM schema ----------
class RSRow(BaseModel):
    ring_size: int = Field(..., description="Integer ring size (e.g., 3, 4, 5, 6, 7, 8).")
    strain_delta_H_kcal_mol: float | str = Field(..., description="ΔH (kcal/mol) or 'Do Not Exist'.")
    strain_delta_G_kcal_mol: float | str = Field(..., description="ΔG (kcal/mol) or 'Do Not Exist'.")

class RSResult(BaseModel):
    rows: List[RSRow] = Field(..., description="One row per ring size present in the passage.")

# ---------- utilities ----------
NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
def _num(x) -> Optional[float]:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip()
    if s.lower() in {"", "none", "null", "n/a", "do not exist"}:
        return None
    m = NUM_RE.search(s)
    return float(m.group(0)) if m else None

# ---------- Public API ----------
def extract_ringstrain_from_md(md_path: str) -> Dict[str, object]:
    """
    Parse a ring-strain section in kcal/mol from a Markdown report.

    Returns:
      {
        "rows": {
          3: {"ring_size": 3, "strain_delta_H_kcal_mol": -13.88, "strain_delta_G_kcal_mol": -12.81},
          4: {...},
          ...
        },
        "reference_is_cyclohexane": True/False
      }
    """
    md = Path(md_path).read_text(encoding="utf-8", errors="ignore")

    # 1) Try deterministic table parse first (fast & robust when table formatting is clean)
    rows = _regex_table_extract(md)
    if rows:
        return {
            "rows": rows,
            "reference_is_cyclohexane": _detect_cyclohexane_reference(md),
        }

    # 2) LLM fallback (handles prose, variants, or imperfect tables)
    sys_lines = [
        "You are a precise scientific parsing agent.",
        "Extract ring strain data in kcal/mol.",
        "Return one row per ring size, with fields: ring_size, strain_delta_H_kcal_mol, strain_delta_G_kcal_mol.",
        "If a value is missing, output 'Do Not Exist'.",
        "If units differ, convert to kcal/mol. If conversion is impossible, leave 'Do Not Exist'.",
        "Do NOT infer data for ring sizes that are not explicitly present.",
    ]
    agent = StructureOutputAgent(model="gpt-4o", agent_schema=RSResult)
    for s in sys_lines:
        agent.append_system_message(s)

    result = agent.stream_return_graph_state(
        "Extract a normalized rows array from this passage (kcal/mol):\n\n" + _normalize(md)
    )
    agent.clear_memory()
    payload = result["structure_output"]

    out_rows: Dict[int, Dict[str, Optional[float]]] = {}
    for r in payload.get("rows", []):
        try:
            n = int(r.get("ring_size"))
        except Exception:
            continue
        dH = _num(r.get("strain_delta_H_kcal_mol"))
        dG = _num(r.get("strain_delta_G_kcal_mol"))
        out_rows[n] = {
            "ring_size": n,
            "strain_delta_H_kcal_mol": dH,
            "strain_delta_G_kcal_mol": dG,
        }

    return {
        "rows": out_rows,
        "reference_is_cyclohexane": _detect_cyclohexane_reference(md),
    }
