# Auto_benchmark/Extractors/TDDFT/LLM_for_extractions_TDDFT.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import re

from pydantic import BaseModel, Field
from ElAgente.Agent import StructureOutputAgent

# ----------------------------
# Schema for LLM fallback
# ----------------------------
class Result(BaseModel):
    """Schema of structured facts extracted from a TDDFT report (energies in eV)."""
    molecule: Optional[str] = Field(None, description="Molecule/system id, if present.")
    S1_energy_eV: float | str = Field(..., description="S1 excitation energy in eV, or 'Do Not Exist'.")
    S1_oscillator_strength: float | str = Field(..., description="S1 oscillator strength (unitless), or 'Do Not Exist'.")
    T1_energy_eV: float | str = Field(..., description="T1 excitation energy in eV, or 'Do Not Exist'.")
    S1_T1_gap_eV: float | str = Field(..., description="(S1 - T1) in eV, or 'Do Not Exist'.")

EV_PER_HARTREE = 27.211386245988  # for au/Hartree → eV
AU_WORDS = re.compile(r"\b(?:au|a\.?u\.?|hartree|hartrees)\b", re.I)

def _coerce_num(val) -> Optional[float]:
    """Extract first numeric token; tolerate strings like '2.13 eV' or 'Do Not Exist'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s.lower() in {"", "none", "null", "do not exist", "n/a"}:
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None

def _maybe_convert_au(number: Optional[float], local_text: str) -> Optional[float]:
    """If nearby text suggests 'au/Hartree', convert to eV; else return as-is."""
    if number is None:
        return None
    if AU_WORDS.search(local_text):
        return number * EV_PER_HARTREE
    return number

# ----------------------------
# Sectionization & molecule slicing
# ----------------------------
HEADER_RE = re.compile(r"(?m)^(#{1,6})\s+(.*)$")

def _aliases_for(name: str) -> list[str]:
    """
    Generate common aliases for a folder name like 'mol2':
      'mol2', 'mol 2', 'mol-2', 'molecule 2', 'Mol 2', 'Molecule-2', 'Mol_2', etc.
    """
    s = name.strip()
    aliases = {s, s.replace("_", " "), s.replace("_", "-")}
    m = re.match(r"([a-zA-Z_\-]*)(\d+)$", s)
    if m:
        prefix, num = m.group(1), m.group(2)
        base = prefix.rstrip("_- ").lower() or "mol"
        variants = {
            f"{base}{num}", f"{base} {num}", f"{base}-{num}", f"{base}_{num}",
            f"molecule {num}", f"Molecule {num}",
            f"Mol {num}", f"Mol-{num}", f"Mol_{num}", f"Mol{num}",
        }
        aliases |= variants
    return list(aliases)

def _split_sections(md_text: str) -> List[Tuple[str, str, int, int]]:
    """
    Split markdown into sections by headers.
    Returns list of (header_text, body_text, start_idx, end_idx).
    If no headers, returns a single 'document' section.
    """
    sections: List[Tuple[str, str, int, int]] = []
    matches = list(HEADER_RE.finditer(md_text))
    if not matches:
        return [("DOCUMENT", md_text, 0, len(md_text))]

    for i, m in enumerate(matches):
        start = m.start()
        head_text = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i+1].start() if i+1 < len(matches) else len(md_text)
        sections.append((head_text, md_text[body_start:body_end], start, body_end))
    return sections

def _score_section(header: str, body: str, aliases: List[str]) -> float:
    """
    Score a section for how likely it refers to one of the aliases.
      - +2 if alias in header
      - +1 if alias in first 300 chars of body
      - +1 if body contains any 'eV' numbers (we want TDDFT numerics in eV)
    """
    score = 0.0
    h = header.lower()
    b = body.lower()
    if any(a.lower() in h for a in aliases):
        score += 2.0
    if any(a.lower() in b[:300] for a in aliases):
        score += 1.0
    if re.search(r"\b\d+(?:\.\d+)?\s*eV\b", body, re.I):
        score += 1.0
    return score

def _slice_for_molecule(md_text: str, molecule: Optional[str]) -> str:
    """
    Try to slice the markdown to the section corresponding to `molecule`.
    Strategy:
      1) Sectionize by headers and pick the highest-scoring section by alias.
      2) If no good section, line-anchored generous window around first alias hit.
      3) Else fallback to document.
    """
    if not molecule:
        return md_text

    aliases = _aliases_for(molecule)
    sections = _split_sections(md_text)

    # 1) pick best section
    best = None
    best_score = -1.0
    for head, body, s, e in sections:
        sc = _score_section(head, body, aliases)
        if sc > best_score:
            best_score = sc
            best = (head, body, s, e)

    if best and best_score >= 2.0:
        return best[1]  # body

    # 2) line-anchored window
    for alias in aliases:
        pat = re.compile(rf"(^|\n).*?\b{re.escape(alias)}\b.*", re.I)
        m = pat.search(md_text)
        if m:
            start = max(0, m.start() - 2000)
            end = min(len(md_text), m.end() + 4000)
            block = md_text[start:end]
            if re.search(r"\b\d+(?:\.\d+)?\s*eV\b", block, re.I):
                return block

    # 3) fallback
    return md_text

# ----------------------------
# Deterministic (regex) extractor
# ----------------------------
# Try to capture a broad set of notations:
# - Inline: "S1 = 2.134 eV", "E(S1): 2.134 eV"
# - Tables: "| S1 | 2.134 eV | f=0.044 |" or "S1 (eV): 2.134"
S1_PAT = re.compile(
    r"(?:\bS\s*1\b|E\s*\(\s*S\s*1\s*\)|\bS1\b)[^:\n|]{0,40}[:=|]\s*([-+]?\d+(?:\.\d+)?)(?:\s*(eV|au|a\.?u\.?|hartree)s?\b)?",
    re.I,
)
T1_PAT = re.compile(
    r"(?:\bT\s*1\b|E\s*\(\s*T\s*1\s*\)|\bT1\b)[^:\n|]{0,40}[:=|]\s*([-+]?\d+(?:\.\d+)?)(?:\s*(eV|au|a\.?u\.?|hartree)s?\b)?",
    re.I,
)
GAP_PAT = re.compile(
    r"(?:S\s*1\s*[-–]\s*T\s*1|ΔE\s*[_\-]?\s*ST|Δ\s*E\s*\(\s*S\s*-\s*T\s*\)|Δ\s*\(\s*S\s*1\s*[-–]\s*T\s*1\s*\)|S1[-–]T1\s*gap)"
    r"[^:\n|]{0,40}[:=|]\s*([-+]?\d+(?:\.\d+)?)(?:\s*(eV|au|a\.?u\.?|hartree)s?\b)?",
    re.I,
)
FOSC_PAT = re.compile(
    r"(?:\boscillator\s+strength\b|\bf\s*(?:=|:)\b|\bfosc\b)\s*[:=]?\s*([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
    re.I,
)

def _regex_extract(md_text: str, molecule: Optional[str]) -> Dict[str, Optional[float]]:
    text = _slice_for_molecule(md_text, molecule)

    def _match_number(pat: re.Pattern) -> Optional[float]:
        m = pat.search(text)
        if not m:
            return None
        num = _coerce_num(m.group(1))
        # local unit sniff around the match
        window = text[max(0, m.start()-40): m.end()+40]
        unit_group = (m.group(2) or "").lower() if len(m.groups()) >= 2 else ""
        if unit_group in {"au", "a.u.", "a.u", "hartree", "hartrees"}:
            return _maybe_convert_au(num, "au")
        return _maybe_convert_au(num, window)

    s1 = _match_number(S1_PAT)
    t1 = _match_number(T1_PAT)
    gap = _match_number(GAP_PAT)

    fosc = None
    fm = FOSC_PAT.search(text)
    if fm:
        fosc = _coerce_num(fm.group(1))

    # derive missing values when possible
    if s1 is not None and t1 is not None and gap is None:
        gap = s1 - t1
    if s1 is not None and gap is not None and t1 is None:
        t1 = s1 - gap
    if t1 is not None and gap is not None and s1 is None:
        s1 = t1 + gap

    return {
        "S1_energy_eV": s1,
        "S1_oscillator_strength": fosc,
        "T1_energy_eV": t1,
        "S1_T1_gap_eV": gap,
    }

# ----------------------------
# LLM fallback (fill only what regex missed)
# ----------------------------
def _llm_extract(md_text: str, molecule: Optional[str]) -> Dict[str, Optional[float]]:
    focus_text = _slice_for_molecule(md_text, molecule)

    # Strong, molecule-scoped prompt to avoid pulling mol2 into mol3/mol5
    sys_lines = [
        "You are a precise scientific parsing agent.",
        "Extract TDDFT values ONLY for the specified molecule section.",
        "If the passage contains multiple molecules, you MUST extract for molecule=<NAME> only.",
        "If the requested molecule values are absent, output 'Do Not Exist' for all fields.",
        "All energies MUST be reported in eV. If au/Hartree units are present, convert to eV using 1 au = 27.211386245988 eV.",
    ]
    agent = StructureOutputAgent(model="gpt-4o", agent_schema=Result)
    for s in sys_lines:
        agent.append_system_message(s)

    molecule_hint = f"\nMolecule of interest: {molecule}\n" if molecule else "\n"
    result = agent.stream_return_graph_state(
        "TDDFT passage (extract only for the molecule if named):\n"
        + molecule_hint
        + focus_text
    )
    agent.clear_memory()
    payload = result["structure_output"]

    def _num_with_unit_guard(key: str) -> Optional[float]:
        raw = payload.get(key)
        num = _coerce_num(raw)
        s = "" if raw is None else str(raw)
        return _maybe_convert_au(num, s)

    out = {
        "S1_energy_eV": _num_with_unit_guard("S1_energy_eV"),
        "S1_oscillator_strength": _coerce_num(payload.get("S1_oscillator_strength")),
        "T1_energy_eV": _num_with_unit_guard("T1_energy_eV"),
        "S1_T1_gap_eV": _num_with_unit_guard("S1_T1_gap_eV"),
    }

    # derive again if needed
    s1, t1, gap = out["S1_energy_eV"], out["T1_energy_eV"], out["S1_T1_gap_eV"]
    if s1 is not None and t1 is not None and gap is None:
        out["S1_T1_gap_eV"] = s1 - t1
    if s1 is not None and gap is not None and t1 is None:
        out["T1_energy_eV"] = s1 - gap
    if t1 is not None and gap is not None and s1 is None:
        out["S1_energy_eV"] = t1 + gap

    return out

# ----------------------------
# Public API
# ----------------------------
def extract_tddft_from_md(md_path: str, molecule: Optional[str] = None) -> Dict[str, Optional[float]]:
    """
    Read a TDDFT markdown report and return:
        {
            "S1_energy_eV": float|None,
            "S1_oscillator_strength": float|None,
            "T1_energy_eV": float|None,
            "S1_T1_gap_eV": float|None,
        }

    - If `molecule` is provided (e.g., 'mol3'), the extractor focuses
      on that section but falls back to the whole report if needed.
    - Regex pass first; LLM fallback only fills missing fields.
    - Derives missing values when possible (gap, T1, or S1).
    """
    md_text = Path(md_path).read_text(encoding="utf-8", errors="ignore")

    # pass 1: regex scoped to molecule
    data = _regex_extract(md_text, molecule)

    # if mostly empty, retry regex on full doc before LLM
    if sum(v is None for v in data.values()) >= 3 and molecule:
        data = _regex_extract(md_text, molecule=None)

    # LLM fills only what’s missing (stays molecule-scoped if we had a good slice)
    if any(v is None for v in data.values()):
        # If regex was empty and molecule was given, still pass molecule to force the LLM constraint.
        llm_data = _llm_extract(md_text, molecule if molecule else None)
        for k, v in data.items():
            if v is None and llm_data.get(k) is not None:
                data[k] = llm_data[k]

    # final derivation
    s1, t1, gap = data["S1_energy_eV"], data["T1_energy_eV"], data["S1_T1_gap_eV"]
    if s1 is not None and t1 is not None and gap is None:
        data["S1_T1_gap_eV"] = s1 - t1
    if s1 is not None and gap is not None and t1 is None:
        data["T1_energy_eV"] = s1 - gap
    if t1 is not None and gap is not None and s1 is None:
        data["S1_energy_eV"] = t1 + gap

    return data