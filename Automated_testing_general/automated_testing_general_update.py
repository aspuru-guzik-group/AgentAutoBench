import re
import os
import pandas as pd
from pathlib import Path

# Input checks
def method_exist(text): return bool(re.search(r"^\s*!", text, re.M))
def basis_exist(text):
    line = next((l for l in text.splitlines() if l.strip().startswith("!")), "")
    return len(line.lstrip("!").split()) >= 2
def tasks_exist(text):
    line = next((l for l in text.splitlines() if l.strip().startswith("!")), "")
    return len(line.lstrip("!").split()) >= 3
def charge_mult_exist(txt: str) -> bool:
    """
    Return True if any line starting with '*' has two integer tokens
    immediately following the '*' (or following 'xyzfile').
    """
    for line in txt.splitlines():
        stripped = line.strip()
        if not stripped.startswith("*"):
            continue
        parts = stripped.split()
        # Determine where the numbers live
        # parts[0] == '*'
        if len(parts) < 3:
            continue
        if parts[1].lower() == "xyzfile":
            charge_idx = 2
        else:
            charge_idx = 1
        # Now check if we have at least two tokens there and both are ints
        if len(parts) > charge_idx + 1:
            ch, mult = parts[charge_idx], parts[charge_idx + 1]
            if re.fullmatch(r"[+-]?\d+", ch) and re.fullmatch(r"[+-]?\d+", mult):
                return True
    return False
def xyz_exist(text): return bool(re.search(r"xyzfile", text, re.I))

# Output checks
def scf_converged(text): return bool(re.search(r"SCF converged", text, re.I))
def geo_opt_converged(text):
    return bool(re.search(
        r"\*+\s*HURRAY\s*\*+.*OPTIMIZATION HAS CONVERGED",
        text, re.I | re.S))
def imaginary_freq_exist(text):
    freqs, in_block = [], False
    for line in text.splitlines():
        if re.search(r"VIBRATIONAL\s+FREQUENCIES", line, re.I):
            in_block = True; continue
        if in_block and not line.strip(): break
        if in_block:
            freqs += [float(n) for n in re.findall(r"[-+]?\d+\.\d+", line)]
    return any(f < 0 for f in freqs)

# Root directory containing subfolders for each molecule
root_dir = Path("/Users/a2011230025/Desktop/Ring_Strain_Energy_test_3")

def _not_forbidden(p: Path) -> bool:
    # optional: skip typical bookkeeping dirs
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
csv_path = "RSE_boolean_report.csv"
df.to_csv(csv_path, index=False)
