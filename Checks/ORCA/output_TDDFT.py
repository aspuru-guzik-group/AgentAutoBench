from __future__ import annotations
import re

__all__ = [
    "tddft_block_executed",
    "excitation_energy_exist",
    "oscillator_strengths_available",
    "check_output_tddft",
]

# Recognize both singlet and triplet TD-DFT/TDA excited-state sections
HEADER_SINGLET_RE = re.compile(r"TD-DFT(?:/TDA)?\s+EXCITED\s+STATES\s*\(SINGLET[S]?\)", re.I)
HEADER_TRIPLET_RE = re.compile(r"TD-DFT(?:/TDA)?\s+EXCITED\s+STATES\s*\(TRIPLET[S]?\)", re.I)

# absorption-spectrum header used by ORCA for oscillator strengths
ABS_SPECTRUM_HDR_RE = re.compile(
    r"ABSORPTION\s+SPECTRUM\s+VIA\s+TRANSITION\s+ELECTRIC\s+DIPOLE\s+MOMENTS",
    re.I,
)

E_PATTERN = re.compile(r"\bE\s*=\s*[-+]?\d+(?:\.\d+)?", re.I)
F_PATTERN = re.compile(r"\bf\s*=\s*[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?", re.I)

# OPTIONAL: explicitly look for the fosc(D2) column token
FOSC_HEADER_RE = re.compile(r"\bfosc\s*\(\s*D2\s*\)", re.I)

def _blocks(text: str, header_re: re.Pattern) -> list[str]:
    blocks: list[str] = []
    for m in header_re.finditer(text):
        start = m.end()
        next_same = header_re.search(text, pos=start)
        end = next_same.start() if next_same else len(text)
        blocks.append(text[start:end])
    return blocks


def _singlet_blocks(text: str) -> list[str]:
    return _blocks(text, HEADER_SINGLET_RE)


def _triplet_blocks(text: str) -> list[str]:
    return _blocks(text, HEADER_TRIPLET_RE)
    

def tddft_block_executed(out_text: str) -> bool:
    """True if a TD-DFT/TDA excited-states (SINGLETS) block is present."""
    return bool(_singlet_blocks(out_text) or _triplet_blocks(out_text))

def excitation_energy_exist(out_text: str) -> bool:
    """Energy evidence either as `E=` in singlet block OR in absorption spectrum table."""
    # 1) classic: E= inside the singlet block
    for blk in _singlet_blocks(out_text):
        if E_PATTERN.search(blk):
            return True
    # 2) absorption-spectrum table lists energies in eV/nm — treat header presence as sufficient
    if ABS_SPECTRUM_HDR_RE.search(out_text):
        return True
    return False

def oscillator_strengths_available(out_text: str) -> bool:
    """
    True if:
      • at least one `f=` appears in singlet blocks, OR
      • an 'ABSORPTION SPECTRUM VIA TRANSITION ELECTRIC DIPOLE MOMENTS' table
        with a 'fosc(D2)' column is present (ORCA's oscillator-strength table).
    """
    # 1) classic: f= in singlet blocks
    for blk in _singlet_blocks(out_text):
        if F_PATTERN.search(blk):
            return True

    # 2) absorption-spectrum table with fosc(D2)
    if ABS_SPECTRUM_HDR_RE.search(out_text) and FOSC_HEADER_RE.search(out_text):
        # If you want to be stricter, you could also require at least one numeric line below.
        return True

    return False

def check_output_tddft(out_text: str) -> dict[str, str]:
    return {
        "TDDFT block executed?": "yes" if tddft_block_executed(out_text) else "no",
        "Excitation energy exist?": "yes" if excitation_energy_exist(out_text) else "no",
        "Oscillator strengths available?": "yes" if oscillator_strengths_available(out_text) else "no",
    }
