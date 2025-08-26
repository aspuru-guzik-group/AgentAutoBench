import re
import os
import pandas as pd
from pathlib import Path

# Input checks
def method_exist(text: str) -> bool:
    """
    Checks whether an ORCA input contains a method/task line.

    A method/task line in ORCA typically begins with an exclamation mark (`!`)
    at the start of a line.

    Args:
      text (str): Full text of the ORCA input file.

    Returns:
      bool: True if any line starts with `!` (ignoring leading whitespace), else False.
    """
    return bool(re.search(r"^\s*!", text, re.M))

def basis_exist(text: str) -> bool:
    """
    Detects whether a basis set is specified (keyword-based).

    Checks for common basis-set tokens/patterns on the '!' line (e.g., 6-31G(d),
    6-311G**, def2-SVP/TZVP/QZVP, cc-pVDZ/VTZ, aug-cc-pVTZ, STO-3G). If none
    are found there, also returns True when a '%basis' block is present anywhere
    in the file (indicating a custom basis definition).

    Args:
        text (str): Full text of the ORCA input file.

    Returns:
        bool: True if a recognized basis keyword is on the '!' line or a
            '%basis' block exists; otherwise False.

    Raises:
        None.
    """
    basis_regexes = [
        r"sto-\d+g(?:\*\*|\*|)",                   # STO-3G, STO-6G, ...
        r"\d+-\d+g(?:\([\w,+\-]*\))?(?:\*\*|\*|)", # 6-31G(d), 6-311G**, 6-31+G(d,p)
        r"def2-\w+",                               # def2-SVP, def2-TZVP, ...
        r"(?:aug-)?cc-pV\w+",                      # cc-pVDZ, cc-pVTZ, aug-cc-pVTZ
        r"def-\w+",                                # def-SVP, def-TZVP (older Ahlrichs)
        r"zora-def2-\w+",                          # ZORA-def2-SVP, etc.
    ]
    basis_re = re.compile(r"(?:^|\s)(" + "|".join(basis_regexes) + r")(?:\s|$)",
                          re.IGNORECASE)

    excl_line = next((l.strip() for l in text.splitlines() if l.strip().startswith("!")), "")

    if excl_line and basis_re.search(excl_line):
        return True

    if re.search(r"^\s*%basis\b", text, flags=re.IGNORECASE | re.MULTILINE):
        return True

    return False

def tasks_exist(text: str) -> bool:
    """
    Detects whether any recognized ORCA task keyword appears on the `!` line.

    The search is case-insensitive and looks for common task keywords such as
    OPT, FREQ, SP, MD, CIS, and TDDFT on any `!` line.

    Args:
      text (str): Full text of the ORCA input file.

    Returns:
      bool: True if at least one known task keyword is present on a `!` line,
        else False.
    """
    task_keywords = {"OPT", "FREQ", "SP", "MD", "CIS", "TDDFT"}
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("!"):
            tokens = [tok.upper() for tok in s[1:].split()]
            if any(tok in task_keywords for tok in tokens):
                return True
    return False

def charge_mult_exist(txt: str) -> bool:
    """
    Checks whether charge and multiplicity are specified on a line starting with `*`.

    ORCA geometry-spec lines typically begin with `*`, optionally followed by
    the token `xyzfile`, and then the system charge and spin multiplicity
    (integers). This function verifies two integer tokens appear in the expected
    positions.

    Args:
      txt (str): Full text of the ORCA input file.

    Returns:
      bool: True if a `*` line contains two integer tokens for charge and
        multiplicity (with or without the `xyzfile` token), else False.
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
    """
    Checks whether the input references an external XYZ coordinate file.

    This detects the presence of the token `xyzfile` (case-insensitive) anywhere
    in the text.

    Args:
      text (str): Full text of the ORCA input file.

    Returns:
      bool: True if `xyzfile` is found, else False.
    """
    return bool(re.search(r"xyzfile", text, re.I))

# Output checks
def scf_converged(text: str) -> bool:
    """
    Checks whether the Self-Consistent Field (SCF) procedure converged.

    Searches the output for the phrase "SCF converged" (case-insensitive), which
    ORCA prints when the SCF cycle reaches convergence.

    Args:
        text (str): Full text of the ORCA output file.

    Returns:
        bool: True if the phrase "SCF converged" appears; otherwise False.

    Raises:
        None.
    """
    return bool(re.search(r"SCF converged", text, re.I))

def geo_opt_converged(text: str) -> bool:
    """
    Checks whether the geometry optimization finished successfully.

    Matches ORCA’s success banner that includes "HURRAY" and
    "OPTIMIZATION HAS CONVERGED". The search is case-insensitive and spans
    multiple lines.

    Args:
        text (str): Full text of the ORCA output file.

    Returns:
        bool: True if the optimization-converged banner is found; otherwise False.

    Raises:
        None.
    """
    return bool(re.search(
        r"\*+\s*HURRAY\s*\*+.*OPTIMIZATION HAS CONVERGED",
        text, re.I | re.S
    ))

def imaginary_freq_exist(text: str) -> bool:
    """
    Determines whether any imaginary vibrational frequency is present.

    Scans the "VIBRATIONAL FREQUENCIES" block and collects numeric frequency
    values; returns True if any value is negative (indicative of an imaginary
    mode, typically in cm⁻¹).

    Args:
        text (str): Full text of the ORCA output file.

    Returns:
        bool: True if at least one vibrational frequency is negative; otherwise False.

    Raises:
        None.
    """
    freqs, in_block = [], False
    for line in text.splitlines():
        if re.search(r"VIBRATIONAL\s+FREQUENCIES", line, re.I):
            in_block = True
            continue
        if in_block and not line.strip():
            break
        if in_block:
            freqs += [float(n) for n in re.findall(r"[-+]?\d+\.\d+", line)]
    return any(f < 0 for f in freqs)

# Root directory containing subfolders for each molecule
root_dir = Path("/h/400/skaxu/ElAgente/pKa_test_3") # <-- *replace the root directry here*


def _not_forbidden(p: Path) -> bool:
    """
    Filters out bookkeeping directories from traversal candidates.

    Returns True when the path does not contain any segment named "results"
    or "jobinfo" (case-insensitive). Useful for skipping output/status folders
    during project scans without touching the filesystem.

    Args:
        p (Path): Path to check. Only the path components are inspected.

    Returns:
        bool: True if none of the path parts are forbidden; otherwise False.

    Raises:
        None.
    """
    forbidden = {"results", "jobinfo"}
    return not any(part.lower() in forbidden for part in p.parts)

rows = []
for folder in root_dir.iterdir():
    if not folder.is_dir():
        continue

    # 1) collect all .out files (recursively), skip slurm
    out_candidates = [
        p for p in folder.rglob("*.out")
        if _not_forbidden(p) and not p.name.lower().startswith("slurm")
    ]
    if not out_candidates:
        continue

    # 2) choose the .out with NO imaginary frequencies (all freqs >= 0)
    #    if multiple, choose the newest by mtime
    distilled_outs = []
    for p in out_candidates:
        try:
            otxt = p.read_text(errors="ignore")
        except Exception:
            continue
        if not imaginary_freq_exist(otxt):        # <-- NO imaginary freqs
            distilled_outs.append((p, os.path.getmtime(p)))
    if not distilled_outs:
        # none qualifies per your rule -> skip this folder
        continue
    selected_out = max(distilled_outs, key=lambda t: t[1])[0]

    # 3) find .inp with the SAME base name as the selected .out
    stem = selected_out.stem
    inp_matches = [p for p in folder.rglob(f"{stem}.inp") if _not_forbidden(p)]

    # prefer an .inp in the SAME directory as the .out; else take first found
    if inp_matches:
        same_dir = [p for p in inp_matches if p.parent == selected_out.parent]
        selected_inp = same_dir[0] if same_dir else inp_matches[0]
    else:
        # no same-named .inp -> skip (stay strict as you requested)
        continue

    # 4) run your checks and record the row
    itxt = selected_inp.read_text(errors="ignore")
    otxt = selected_out.read_text(errors="ignore")

    row = {
        "Folder":                 folder.name,
        "Method exist?":          "yes" if method_exist(itxt)         else "no",
        "Basis set exist?":       "yes" if basis_exist(itxt)          else "no",
        "Tasks exist?":           "yes" if tasks_exist(itxt)          else "no",
        "Charge & mult exist?":   "yes" if charge_mult_exist(itxt)    else "no",
        "XYZ file exist?":        "yes" if xyz_exist(itxt)            else "no",
        "SCF converged?":         "yes" if scf_converged(otxt)        else "no",
        "Geo opt converged?":     "yes" if geo_opt_converged(otxt)    else "no",
        "Imag freq exist?":       "yes" if imaginary_freq_exist(otxt) else "no",
    }
    rows.append(row)

# Create DataFrame and export to CSV
df = pd.DataFrame(rows)
csv_path = "pKa_boolean_report.csv" # <- *change the name based on the type of questions.*
df.to_csv(csv_path, index=False)
