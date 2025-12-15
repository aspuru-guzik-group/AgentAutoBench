# Auto_benchmark/Extractors/pKa/LLM_for_extractions_pKa.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List, Tuple
import re
from pydantic import BaseModel, Field
from ElAgente.Agent import StructureOutputAgent

class Result(BaseModel):
    """
    Schema of structured facts extracted from a scientific passage.

    This model captures (1) whether a text reports a pKa value for
    chlorofluoroacetic acid and (2) whether it explicitly mentions a linear
    regression model.

    Attributes:
        pKa_of_chlorofluoroacetic_acid (float | str):
            The reported pKa of chlorofluoroacetic acid. Use a numeric value
            when the text provides one; otherwise set the string
            "Do Not Exist" to indicate the value is not reported.
        has_linear_regression_model (bool):
            True if the text explicitly indicates the presence of a linear
            regression (e.g., mentions "linear regression", provides an
            equation such as y = ax + b, or reports R²/R^2); False otherwise.
    """
    pKa_of_chlorofluoroacetic_acid: float | str = Field(
        ..., description="the pka value of the chlorofluoroacetic_acid, Do Not Exist if not reported"
    )
    has_linear_regression_model: bool = Field(
        ..., description="True if the text explicitly reports a linear regression model (mentions 'linear regression', an equation, or R²)."
    )

def test_expert(message2agent: str):
    """
    Parses a message with a structured-output agent and returns schema-validated fields.
    """
    agent = StructureOutputAgent(model="gpt-4o", agent_schema=Result)
    agent.append_system_message("You are a parsing agent.")
    agent.append_system_message("")
    result = agent.stream_return_graph_state(message2agent)
    agent.clear_memory()
    return result["structure_output"]

# ----------------------------------------------------------
# Helpers & Regex (TDDFT-style mechanism)
# ----------------------------------------------------------
HEADER_RE = re.compile(r"(?m)^(#{1,6})\s+(.*)$")
NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# Names/aliases for chlorofluoroacetic acid
# (Accept variations like hyphens/spaces and both orders if present.)
CFAA_ALIASES = [
    r"chlorofluoroacetic acid",
    r"chloro\-?fluoroacetic acid",
    r"fluorochloroacetic acid",      # sometimes flipped in text
    r"fluoro\-?chloroacetic acid",
    r"CFAA",                          # abbreviation if used in report
]

# pKa capture (accepts “pKa”, “pK_a”, “pK a”, etc.), possibly with “=”, “:”, or whitespace
PKA_TOKEN = r"p\s*K\s*_?a"
PKA_PAT_NEAR = re.compile(
    rf"(?P<name>{'|'.join(CFAA_ALIASES)})[^.\n]{{0,120}}?(?:{PKA_TOKEN})[^0-9\-+]*({NUM_RE.pattern})",
    re.I,
)
PKA_PAT_GENERIC = re.compile(
    rf"(?:{PKA_TOKEN})[^0-9\-+]*({NUM_RE.pattern})",
    re.I,
)

# Linear regression indicators: phrase, equation form, or R^2/R²
LINREG_PAT = re.compile(
    r"(linear\s+regression|R\s*[\^²]?\s*2|R2\b|R\s*=\s*0\.\d+|y\s*=\s*m\s*x\s*\+\s*b|y\s*=\s*a\s*x\s*\+\s*b)",
    re.I,
)

def _coerce_num(val) -> Optional[float]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s.lower() in {"", "none", "null", "do not exist", "n/a", "na"}:
        return None
    m = NUM_RE.search(s)
    if not m:
        return None
    try:
        return float(m.group(0))
    except Exception:
        return None

def _split_sections(md_text: str) -> List[Tuple[str, str, int, int]]:
    """
    Split markdown into sections by headers.
    Returns list of (header_text, body_text, start_idx, end_idx).
    If no headers, returns a single 'DOCUMENT' section.
    """
    sections: List[Tuple[str, str, int, int]] = []
    matches = list(HEADER_RE.finditer(md_text))
    if not matches:
        return [("DOCUMENT", md_text, 0, len(md_text))]
    for i, m in enumerate(matches):
        head_text = m.group(2).strip()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(md_text)
        sections.append((head_text, md_text[body_start:body_end], m.start(), body_end))
    return sections

def _score_section_for_cfaa(header: str, body: str) -> float:
    h = header.lower()
    b = body.lower()
    score = 0.0
    if any(re.search(alias, h, re.I) for alias in CFAA_ALIASES):
        score += 2.0
    if any(re.search(alias, b[:300], re.I) for alias in CFAA_ALIASES):
        score += 1.0
    if re.search(PKA_TOKEN, body, re.I):
        score += 1.0
    return score

def _slice_for_cfaa(md_text: str) -> str:
    """
    Similar to TDDFT's molecule slicing:
      1) Sectionize and pick the best section mentioning CFAA and pKa.
      2) If none, cut a generous window around the first CFAA mention.
      3) Else fall back to the entire document.
    """
    sections = _split_sections(md_text)
    best, best_score = None, -1.0
    for head, body, s, e in sections:
        sc = _score_section_for_cfaa(head, body)
        if sc > best_score:
            best_score, best = sc, (head, body, s, e)
    if best and best_score >= 2.0:
        return best[1]

    # window around first explicit alias
    for alias in CFAA_ALIASES:
        m = re.search(alias, md_text, re.I)
        if m:
            start = max(0, m.start() - 2000)
            end = min(len(md_text), m.end() + 4000)
            return md_text[start:end]

    return md_text

# ----------------------------------------------------------
# Deterministic (regex) extractor
# ----------------------------------------------------------
def _regex_extract(md_text: str) -> Dict[str, Optional[float | bool]]:
    focus = _slice_for_cfaa(md_text)

    # Prefer a pKa matched near the compound name
    pka_val: Optional[float] = None
    m = PKA_PAT_NEAR.search(focus)
    if m:
        pka_val = _coerce_num(m.group(2))

    # If not found, use a generic pKa in the focused region (but still scoped)
    if pka_val is None:
        mg = PKA_PAT_GENERIC.search(focus)
        if mg:
            pka_val = _coerce_num(mg.group(1))

    # Linear regression detection (scoped region)
    has_linreg: Optional[bool] = None
    if re.search(LINREG_PAT, focus):
        has_linreg = True
    elif re.search(LINREG_PAT, md_text):
        # fall back to whole doc if strongly indicated elsewhere
        has_linreg = True
    else:
        has_linreg = False

    return {
        "pKa_of_chlorofluoroacetic_acid": pka_val,
        "has_linear_regression_model": has_linreg,
    }

# ----------------------------------------------------------
# LLM fallback (fill what regex missed) — uses your test_expert
# ----------------------------------------------------------
def _llm_extract(md_text: str) -> Dict[str, Optional[float | bool]]:
    focus = _slice_for_cfaa(md_text)
    payload = test_expert("This is the final answer you need to extract result from:\n" + focus)

    # Coerce to final types (float/None for pKa; bool/None for linreg)
    pka_val = _coerce_num(payload.get("pKa_of_chlorofluoroacetic_acid"))
    linreg_raw = payload.get("has_linear_regression_model")
    linreg_val: Optional[bool] = None
    if isinstance(linreg_raw, bool):
        linreg_val = linreg_raw
    elif isinstance(linreg_raw, str):
        if linreg_raw.strip().lower() in {"true", "yes"}:
            linreg_val = True
        elif linreg_raw.strip().lower() in {"false", "no"}:
            linreg_val = False

    return {
        "pKa_of_chlorofluoroacetic_acid": pka_val,
        "has_linear_regression_model": linreg_val,
    }

# ----------------------------------------------------------
# Public API (TDDFT-style)
# ----------------------------------------------------------
def extract_pka_from_md(md_path: str) -> Dict[str, Optional[float | bool]]:
    """
    Read a Markdown report and return:
        {
            "pKa_of_chlorofluoroacetic_acid": float|None,
            "has_linear_regression_model": bool|None
        }

    Mechanism:
      - Regex first on a CFAA-focused slice of the document.
      - If any field is missing, call the unchanged LLM `test_expert` to fill gaps.
      - Final values are coerced to float/bool where applicable; "Do Not Exist" → None.
    """
    md_text = Path(md_path).read_text(encoding="utf-8", errors="ignore")

    data = _regex_extract(md_text)

    # If anything missing, LLM fills the gaps
    if any(v is None for v in data.values()):
        llm_data = _llm_extract(md_text)
        for k, v in data.items():
            if v is None and llm_data.get(k) is not None:
                data[k] = llm_data[k]

    return data
