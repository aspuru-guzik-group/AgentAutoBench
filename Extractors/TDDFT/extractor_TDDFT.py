from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict

__all__ = [
    "SINGLET_HEADER_RE",
    "TRIPLET_HEADER_RE",
    "STATE_LINE_RE",
    "parse_singlet_states",
    "parse_triplet_states",
    "get_S1",
    "get_T1",
    "s1_oscillator_from_absorption",
    "extract_tddft_core",
]

# ---------------- Patterns ---------------- #
# ORCA headers (allow /TDA, and pluralization variants)
SINGLET_HEADER_RE = re.compile(
    r"TD-DFT(?:/TDA)?\s+EXCITED\s+STATES\s*\(SINGLET[S]?\)", re.I
)
TRIPLET_HEADER_RE = re.compile(
    r"TD-DFT(?:/TDA)?\s+EXCITED\s+STATES\s*\(TRIPLET[S]?\)", re.I
)

# Typical ORCA state lines vary. Examples:
#   STATE  1:  E= 0.116995 au  3.184 eV  25677.4 cm**-1  <S**2>=0.000 ...
#   STATE  1:  E= 3.184 eV  389.4 nm  f=0.0728  <S**2>=0.000 ...
#   STATE  1:  E= 3.184 eV                             (no nm/ cm-1)
#
# We capture "E=<number><unit?>" and also look for any explicit "<number> eV"
# anywhere else on the same line and prefer that value.
STATE_LINE_RE = re.compile(
    r"^\s*STATE\s*(?P<idx>\d+)\s*:\s*"
    r"(?:.*?)\bE\s*=\s*(?P<eval>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*"
    r"(?P<eunit>eV|cm\^?\*?-?1|cm-1|nm|au|a\.?u\.?|hartree|hartrees)?"
    r"(?:.*?\bf\s*=\s*(?P<fval>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?))?",
    re.I | re.M,
)

# ABSORPTION SPECTRUM header:
# ORCA prints at least two variants:
#   "ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS"
#   "ABSORPTION SPECTRUM VIA TRANSITION VELOCITY DIPOLE MOMENTS"
ABS_HEADER_RE = re.compile(
    r"ABSORPTION\s+SPECTRUM\s+VIA\s+TRANSITION\s+(?:ELECTRIC|VELOCITY)\s+DIPOLE\s+MOMENTS",
    re.I,
)

# Example rows (columns may be scientific notation):
#  0-1A  ->  1-1A      2.134225    1.72137E+04   580.9     4.4254817E-02 ...
#  0-1A  ->  1-1A'     2.1342      17213.7       581.0     0.04425 ...
# Columns we care about: e_eV, e_cm^-1, wavelength_nm, fosc
ABS_ROW_RE = re.compile(
    r"^\s*0-\S+\s*->\s*(?P<final>\d-\S+)\s+"
    r"(?P<e_ev>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"(?P<e_cm>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"(?P<wl_nm>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s+"
    r"(?P<fosc>[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)",
    re.M,
)

# ---------------- Unit helpers ---------------- #
EV_PER_CM1 = 1.0 / 8065.544005         # eV per wavenumber
EV_NM_CONST = 1239.841984              # eV*nm
HARTREE_TO_EV = 27.211386245988        # eV per Hartree

# Any explicit "<number> eV" on the same line should be preferred.
EXPLICIT_EV_ON_LINE_RE = re.compile(r"([+-]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*eV\b", re.I)

def _to_eV(value: float, unit: Optional[str], line_text: str | None = None) -> float:
    """
    Convert a numeric energy with unit (eV, nm, cm^-1, au/Hartree) to eV.

    Preference:
      1) If the same line contains an explicit '<number> eV', use that.
      2) Else convert from the provided unit (au/Hartree, cm^-1, nm).
      3) Unknown/missing unit -> assume the number is already eV.
    """
    # 1) Prefer explicit eV on the line, if present
    if line_text:
        m = EXPLICIT_EV_ON_LINE_RE.search(line_text)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass

    # 2) Convert from the captured unit
    if not unit:
        return value
    ul = unit.lower().replace(".", "")
    if ul in {"ev"}:
        return value
    if ul in {"cm-1", "cm^-1", "cm**-1"}:
        return value * EV_PER_CM1
    if ul == "nm":
        return 0.0 if value == 0 else EV_NM_CONST / value
    if ul in {"au", "a u", "hartree", "hartrees"}:
        return value * HARTREE_TO_EV

    # 3) Fallback (assume already eV)
    return value

# ---------------- Data model ---------------- #
@dataclass
class TDState:
    index: int
    energy_eV: float
    oscillator_strength: Optional[float] = None
    raw_line: str = ""

# ---------------- Block slicing ---------------- #
def _blocks(text: str, header_re: re.Pattern, other_header_re: re.Pattern) -> List[str]:
    """Slice sub-blocks starting at header_re and ending at next header or EOF."""
    blocks: List[str] = []
    for m in header_re.finditer(text):
        start = m.end()
        next_same = header_re.search(text, pos=start)
        next_other = other_header_re.search(text, pos=start)
        stops = [x.start() for x in (next_same, next_other) if x]
        end = min(stops) if stops else len(text)
        blocks.append(text[start:end])
    return blocks

def _parse_states_from_blocks(text: str, header_re: re.Pattern, other_header_re: re.Pattern) -> List[TDState]:
    states: List[TDState] = []
    for blk in _blocks(text, header_re, other_header_re):
        for m in STATE_LINE_RE.finditer(blk):
            idx = int(m.group("idx"))
            e_val = float(m.group("eval"))
            e_unit = m.group("eunit")
            f_val = m.group("fval")
            line_txt = m.group(0)

            e_ev = _to_eV(e_val, e_unit, line_txt)  # prefer explicit eV on the line, else convert
            f = float(f_val) if f_val is not None else None
            states.append(TDState(index=idx, energy_eV=e_ev, oscillator_strength=f, raw_line=line_txt))
    states.sort(key=lambda s: s.index)
    return states

# ---------------- Public parsers ---------------- #
def parse_singlet_states(text: str) -> List[TDState]:
    """Return parsed singlet states (sorted by index)."""
    return _parse_states_from_blocks(text, SINGLET_HEADER_RE, TRIPLET_HEADER_RE)

def parse_triplet_states(text: str) -> List[TDState]:
    """Return parsed triplet states (sorted by index)."""
    return _parse_states_from_blocks(text, TRIPLET_HEADER_RE, SINGLET_HEADER_RE)

def get_S1(text: str) -> Optional[TDState]:
    """Return the first singlet state (S1) if present."""
    ss = parse_singlet_states(text)
    return ss[0] if ss else None

def get_T1(text: str) -> Optional[TDState]:
    """Return the first triplet state (T1) if present."""
    ts = parse_triplet_states(text)
    return ts[0] if ts else None

# ---------------- Absorption Spectrum (fallback for f/energy) ---------------- #
def _absorption_block(text: str) -> Optional[str]:
    m = ABS_HEADER_RE.search(text)
    if not m:
        return None
    start = m.end()
    # The table is compact; a few thousand chars are usually plenty.
    return text[start : start + 8000]

def s1_oscillator_from_absorption(out_text: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Return (fosc, energy_eV, wavelength_nm) for the first *singlet* excited state S1
    from the absorption spectrum table. If not found, returns (None, None, None).
    """
    blk = _absorption_block(out_text)
    if not blk:
        return None, None, None
    for m in ABS_ROW_RE.finditer(blk):
        # final like "1-1A", "1-1A'", "1-1A1", etc. (index 1, multiplicity 1 → singlet)
        final = m.group("final")
        # Require the target state index "1-" and multiplicity "1" for S1
        if re.match(r"1-1\S*", final):
            fosc = float(m.group("fosc"))
            e_ev = float(m.group("e_ev"))
            wl_nm = float(m.group("wl_nm"))
            return fosc, e_ev, wl_nm
    return None, None, None

# ---------------- Core extraction API ---------------- #
def extract_tddft_core(out_text: str) -> Dict[str, Optional[float]]:
    """
    Extract core TDDFT values for benchmarking (all energies in eV):

      - S1_energy_eV
      - S1_oscillator_strength
      - T1_energy_eV
      - S1_T1_gap_eV  (S1 - T1)

    Strategy:
      1) Parse S1/T1 from the SINGLET/TRIPLET excited-states blocks.
         Prefer explicit eV printed on the line; otherwise convert from the unit
         (supports au/Hartree, cm^-1, nm).
      2) Use the STATE-line f-value for S1 if present.
      3) If S1 f is missing, fall back to the ABSORPTION SPECTRUM table (fosc).
      4) If S1 energy is missing, but the absorption table gives it, use that.
    """
    result: Dict[str, Optional[float]] = {
        "S1_energy_eV": None,
        "S1_oscillator_strength": None,
        "T1_energy_eV": None,
        "S1_T1_gap_eV": None,
    }

    # Step 1: parse S1/T1 from excited-states listings
    S1 = get_S1(out_text)
    T1 = get_T1(out_text)

    if S1:
        result["S1_energy_eV"] = S1.energy_eV
        result["S1_oscillator_strength"] = S1.oscillator_strength
    if T1:
        result["T1_energy_eV"] = T1.energy_eV

    # Step 2/3: fill S1 oscillator strength from absorption table if missing
    if result["S1_oscillator_strength"] is None:
        fosc, e_ev_abs, wl_nm_abs = s1_oscillator_from_absorption(out_text)
        if fosc is not None:
            result["S1_oscillator_strength"] = fosc
            # Step 4: if S1 energy is still missing, use absorption energy
            if result["S1_energy_eV"] is None and e_ev_abs is not None:
                result["S1_energy_eV"] = e_ev_abs

    # Gap (ensure both are in eV already)
    if result["S1_energy_eV"] is not None and result["T1_energy_eV"] is not None:
        result["S1_T1_gap_eV"] = result["S1_energy_eV"] - result["T1_energy_eV"]

    return result