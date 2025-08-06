import re
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
root_dir = Path("Your_root_path")

rows = []
for folder in root_dir.iterdir():
    if not folder.is_dir():
        continue
    # Find one .inp and one .out (excluding slurm files)
    inp_files = list(folder.glob("*.inp"))
    out_files = [f for f in folder.glob("*.out") if not f.name.startswith("slurm")]
    if not inp_files or not out_files:
        continue
    inp_file = inp_files[0]
    out_file = out_files[0]
    itxt = inp_file.read_text()
    otxt = out_file.read_text()
    row = {
        "Folder":                 folder.name,
        "Method exist?":          "yes" if method_exist(itxt)       else "no",
        "Basis set exist?":       "yes" if basis_exist(itxt)        else "no",
        "Tasks exist?":           "yes" if tasks_exist(itxt)        else "no",
        "Charge & mult exist?":   "yes" if charge_mult_exist(itxt)  else "no",
        "XYZ file exist?":        "yes" if xyz_exist(itxt)          else "no",
        "SCF converged?":         "yes" if scf_converged(otxt)      else "no",
        "Geo opt converged?":     "yes" if geo_opt_converged(otxt)  else "no",
        "Imag freq exist?":       "yes" if imaginary_freq_exist(otxt) else "no",
    }
    rows.append(row)

# Create DataFrame and export to CSV
df = pd.DataFrame(rows)
csv_path = "carbocation_boolean_report.csv"
df.to_csv(csv_path, index=False)
