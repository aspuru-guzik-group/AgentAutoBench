# Auto_benchmark/Checks/input_checks.py
from __future__ import annotations
import re
from Auto_benchmark.config import COMPOSITE_METHODS  # e.g., {"B97-3C", "R2SCAN-3C", ...}

__all__ = [
    "method_exist",
    "basis_exist",
    "tasks_exist",
    "charge_mult_exist",
    "xyz_exist",
]

# ---------------- Input checks ----------------

def method_exist(text: str) -> bool:
    """True if there is a method/task line starting with '!'."""
    return bool(re.search(r"^\s*!", text, re.M))


def basis_exist(text: str) -> bool:
    """
    True if a basis is explicitly set OR implied by a composite 3c method.

    Returns True if:
      • a recognized basis keyword appears on the '!' line, OR
      • a '%basis' block is present anywhere, OR
      • the '!' line contains a composite method in COMPOSITE_METHODS (e.g., B97-3c)
        which implies a built-in basis in ORCA.
    """
    basis_regexes = [
        r"sto-\d+g(?:\*\*|\*|)",                   # STO-3G, STO-6G
        r"\d+-\d+g(?:\([\w,+\-]*\))?(?:\*\*|\*|)", # 6-31G(d), 6-311G**, 6-31+G(d,p)
        r"def2-\w+",                               # def2-SVP, def2-TZVP, ...
        r"(?:aug-)?cc-pV\w+",                      # cc-pVDZ/VTZ, aug-cc-pVTZ
        r"def-\w+",                                # def-SVP/TZVP (older)
        r"zora-def2-\w+",                          # ZORA-def2-SVP, ...
    ]
    basis_re = re.compile(r"(?:^|\s)(" + "|".join(basis_regexes) + r")(?:\s|$)", re.I)

    # Find the first '!' line (method/task line)
    excl_line = next((l.strip() for l in text.splitlines() if l.strip().startswith("!")), "")

    # 1) explicit basis on '!' line
    if excl_line and basis_re.search(excl_line):
        return True

    # 2) %basis block anywhere
    if re.search(r"^\s*%basis\b", text, flags=re.I | re.M):
        return True

    # 3) composite 3c method implies a (built-in) basis
    if excl_line:
        tokens = {tok.upper() for tok in excl_line[1:].split()}
        if any(tok in COMPOSITE_METHODS for tok in tokens):
            return True

    return False



def tasks_exist(text: str) -> bool:
    """
    Return True if any known ORCA task keyword appears anywhere in the input.
    Detects tasks on '!' lines, in %blocks, or anywhere else in the text.
    """
    task_keywords = {"OPT", "FREQ", "SP", "MD", "CIS", "TDDFT"}

    # Convert entire input to uppercase once for uniform search
    text_upper = text.upper()

    # Use regex word boundaries to avoid partial matches (e.g., "OPTION")
    for kw in task_keywords:
        if re.search(rf"\b{kw}\b", text_upper):
            return True

    return False


def charge_mult_exist(txt: str) -> bool:
    """
    True if a geometry spec line ('* ...') contains charge and multiplicity.
    Supports both inline geometry and '* xyzfile <charge> <mult> <file>'.
    """
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped.startswith("*"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        charge_idx = 2 if parts[1].lower() == "xyzfile" else 1
        if len(parts) > charge_idx + 1:
            ch, mult = parts[charge_idx], parts[charge_idx + 1]
            if re.fullmatch(r"[+-]?\d+", ch) and re.fullmatch(r"[+-]?\d+", mult):
                return True
    return False


def xyz_exist(text: str) -> bool:
    """True if the input references an external XYZ file via 'xyzfile'."""
    return bool(re.search(r"xyzfile", text, re.I))
