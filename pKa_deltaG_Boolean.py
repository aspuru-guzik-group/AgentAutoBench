import re, os
from pathlib import Path
import pandas as pd

# --- NEW: identify a proton (.xyz with exactly one H atom) ---
def is_proton_xyz(xyz_path: Path) -> bool:
    """
    Determines whether an XYZ file describes a single hydrogen atom (proton).

    Reads the file as plain text, interprets the standard XYZ layout
    (first line = atom count, second line = comment, following lines = atoms),
    and checks that there is exactly one atom and its element symbol is "H".

    Args:
        xyz_path (Path): Path to the XYZ file.

    Returns:
        bool: True if the file is a valid XYZ with one atom and that atom is H;
              otherwise False (including on read/parse errors).

    Raises:
        None. All errors are caught and result in False.
    """
    try:
        with open(xyz_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = [ln.strip() for ln in f if ln.strip()]
        if not lines:
            return False
        # standard xyz: first line = atom count
        try:
            n = int(lines[0].split()[0])
        except ValueError:
            return False
        # next line is a comment; atom lines follow
        atom_lines = lines[2:2+n]
        if len(atom_lines) != n:
            return False
        # element symbol is the first token on each atom line
        elems = [ln.split()[0].capitalize() for ln in atom_lines]
        return (n == 1) and (elems[0] == "H")
    except Exception:
        return False


def folder_is_proton(folder: Path) -> bool:
    """
    Checks whether a folder contains any XYZ file that represents a proton.

    The folder (recursively) is scanned for '*.xyz' files; if any file is
    recognized by `is_proton_xyz` as a single-atom hydrogen structure, the
    folder is treated as "proton".

    Args:
        folder (Path): Directory to search recursively.

    Returns:
        bool: True if any matching proton XYZ is found; otherwise False.

    Raises:
        OSError: If directory traversal fails due to filesystem errors.
    """
    for xyz in folder.rglob("*.xyz"):
        if is_proton_xyz(xyz):
            return True
    return False


def _not_forbidden(p: Path) -> bool:
    """
    Filters out bookkeeping directories from traversal candidates.

    Returns True when the path does not contain any segment named "results"
    or "jobinfo" (case-insensitive). Useful for skipping output/status folders
    during scans.

    Args:
        p (Path): Path to check; only its parts are inspected.

    Returns:
        bool: True if none of the path parts are forbidden; otherwise False.

    Raises:
        None.
    """
    forbidden = {"results", "jobinfo"}
    return not any(part.lower() in forbidden for part in p.parts)


def imaginary_freq_exist(text: str) -> bool:
    """
    Determines whether any imaginary vibrational frequency is present.

    Searches the "VIBRATIONAL FREQUENCIES" block in the output text, collects
    numeric frequency values, and returns True if any value is negative
    (indicative of an imaginary mode).

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
    return any(f < 0.0 for f in freqs)


def deltaG_exists(text: str) -> bool:
    """
    Checks whether a Gibbs free energy value is reported in the output.

    Looks for several common headings that ORCA (and related tools) print when
    reporting Gibbs free energy, in a case-insensitive manner.

    Args:
        text (str): Full text of the ORCA output file.

    Returns:
        bool: True if a recognized Gibbs free-energy label is found; otherwise False.

    Raises:
        None.
    """
    pats = [
        r"Final\s+Gibbs\s+free\s+energy",
        r"GIBBS\s+FREE\s+ENERGY",
        r"Total\s+Gibbs\s+free\s+energy",
    ]
    return any(re.search(p, text, re.I) for p in pats)

# --------- MAIN ---------
root_dir = Path("/h/400/skaxu/ElAgente/pKa_test_3")  # <-- *set this*
out_csv  = "pKa_deltaG_boolean_report.csv"

rows = []
folders = {}

# 1) Optionally pre-skip proton folders
candidate_dirs = [d for d in root_dir.iterdir() if d.is_dir()]
candidate_dirs = [d for d in candidate_dirs if not folder_is_proton(d)]

# 2) Collect qualifying .out (no imaginary freq) grouped by parent folder
for d in candidate_dirs:
    for out_path in d.rglob("*.out"):
        if not _not_forbidden(out_path): 
            continue
        if out_path.name.lower().startswith("slurm"):
            continue
        try:
            txt = out_path.read_text(errors="ignore")
        except Exception:
            continue
        if imaginary_freq_exist(txt):
            continue
        folders.setdefault(out_path.parent, []).append((out_path, os.path.getmtime(out_path), txt))

# 3) One row per folder that has a qualifying .out
for folder, items in folders.items():
    items.sort(key=lambda t: t[1], reverse=True)
    _, _, chosen_text = items[0]
    rows.append({
        "Folder": folder.name,
        "deltaG_exist": "yes" if deltaG_exists(chosen_text) else "no",
    })

pd.DataFrame(rows).to_csv(out_csv, index=False)
print(f"Saved: {out_csv} | rows: {len(rows)}")
