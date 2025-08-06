# ============================
# Structure-based scoring (RDKit-only)
# ============================
import re
import pandas as pd
from pathlib import Path

# ---- RDKit (no Open Babel needed) ----
from rdkit import Chem
from rdkit.Chem import inchi
from rdkit.Chem import rdDetermineBonds

# -----------------------------
# 0) Paths
# -----------------------------
root     = Path("/Users/a2011230025/Desktop/Ring_Strain_Energy_test_3")
bool_csv = root / "RSE_boolean_report.csv"
logic_csv= root / "RSE_logic_report.csv"
num_csv  = root / "RSE_numerical_report.csv"

# -----------------------------
# 1) Load and index your reports
# -----------------------------
df_bool  = pd.read_csv(bool_csv).set_index("Folder")
df_logic = pd.read_csv(logic_csv).set_index("species")
df_num   = pd.read_csv(num_csv).set_index("ring_size")

# force string indices
for df in (df_bool, df_logic):
    df.index = df.index.astype(str)
df_num.index = df_num.index.astype(str)

# -----------------------------
# 2) Structure helpers (RDKit)
# -----------------------------
def smiles_cycloalkane(k: int) -> str:
    # k=3 -> C1CC1, k=4 -> C1CCC1, ..., k=8 -> C1CCCCCCC1
    if k < 3:
        raise ValueError("Cycloalkane ring size must be >= 3")
    return "C1" + "C" * (k - 1) + "1"

def smiles_methylcycloalkane(k: int) -> str:
    # Methyl attached to the ring: k=3 -> CC1CC1; k=5 -> CC1CCCC1
    if k < 3:
        raise ValueError("Ring size must be >= 3")
    return "CC1" + "C" * (k - 1) + "1"

def inchikey_from_smiles(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError(f"Cannot parse SMILES: {smiles}")
    return inchi.MolToInchiKey(m)

def inchikey_from_xyz(xyz_path: Path) -> str:
    """
    Read XYZ -> infer bonds -> InChIKey (RDKit).
    Works well for neutral hydrocarbons used here.
    """
    # Try direct file read
    m = Chem.MolFromXYZFile(str(xyz_path))
    if m is None:
        # Fallback: read as block
        m = Chem.MolFromXYZBlock(xyz_path.read_text())
    if m is None:
        raise ValueError(f"Failed to read XYZ: {xyz_path}")

    # Infer connectivity/bond orders from geometry
    rdDetermineBonds.DetermineBonds(m)  # charge=0 default (OK for alkanes)

    # Sanitize before InChI generation
    try:
        Chem.SanitizeMol(m)
    except Exception:
        # Some edge cases may sanitize during InChI conversion anyway
        pass

    return inchi.MolToInchiKey(m)

def _pick_primary_xyz(folder: Path):
    """
    Prefer *.xyz not named *_trj.xyz or *_initial.xyz; else *_initial.xyz; else first *.xyz.
    """
    xyzs = sorted(folder.glob("*.xyz"), key=lambda p: p.name)
    if not xyzs:
        return None
    non_special = [p for p in xyzs if not re.search(r"(_trj|_initial)\.xyz$", p.name, flags=re.I)]
    if non_special:
        return non_special[0]
    initials = [p for p in xyzs if p.name.lower().endswith("_initial.xyz")]
    if initials:
        return initials[0]
    return xyzs[0]

def build_structure_index(root_dir: Path):
    """
    Build: InChIKey -> {'folder': <folder name>, 'xyz': <Path>}
    """
    idx = {}
    for folder in root_dir.iterdir():
        if not folder.is_dir():
            continue
        if folder.name.lower() in ("results", "jobinfo"):
            continue
        xyz = _pick_primary_xyz(folder)
        if not xyz:
            continue
        try:
            ik = inchikey_from_xyz(xyz)
        except Exception as e:
            print(f"[WARN] Skipping {folder.name}: {e}")
            continue
        # Keep first occurrence; if duplicates appear, they’re same structure
        idx.setdefault(ik, {"folder": folder.name, "xyz": xyz})
    return idx

# Build structure index once
structure_index = build_structure_index(root)

# -----------------------------
# 3) Scoring setup (unchanged)
# -----------------------------
input_cols  = ["Method exist?","Basis set exist?","Tasks exist?",
               "Charge & mult exist?","XYZ file exist?"]
output_cols = [("SCF converged?","yes"),
               ("Geo opt converged?","yes"),
               ("Imag freq exist?","no")]
thermo_cols = ["enthalpy_exist","gibbs_exist"]

# Only for readable expected labels
pref = {"3":"prop", "4":"but", "5":"pent", "6":"hex", "7":"hept", "8":"oct"}

# -----------------------------
# 4) Score by *structure-resolved* names
# -----------------------------
records = []
for n in ["3","4","5","6","7","8"]:
    n_int = int(n)

    # Product structure: methylcyclo[n]ane
    prod_smiles = smiles_methylcycloalkane(n_int)
    prod_key    = inchikey_from_smiles(prod_smiles)
    prod_name   = structure_index.get(prod_key, {}).get("folder", "")

    # Reactant structure: cyclo[n+1]ane (only up to 8 here)
    react_name = ""
    if n_int + 1 <= 8:
        react_smiles = smiles_cycloalkane(n_int + 1)
        react_key    = inchikey_from_smiles(react_smiles)
        react_name   = structure_index.get(react_key, {}).get("folder", "")

    # Pull rows by resolved names; default to "no" if missing
    bR = df_bool.loc[react_name] if react_name in df_bool.index else pd.Series("no", index=df_bool.columns)
    bP = df_bool.loc[prod_name]  if prod_name  in df_bool.index  else pd.Series("no", index=df_bool.columns)
    lR = df_logic.loc[react_name] if react_name in df_logic.index else pd.Series({"enthalpy_exist":"no","gibbs_exist":"no"})
    lP = df_logic.loc[prod_name]  if prod_name  in df_logic.index  else pd.Series({"enthalpy_exist":"no","gibbs_exist":"no"})
    row = df_num.loc[n]  # numeric row for ring size n

    # ---- Scoring (unchanged) ----
    pts = 0.0

    # 1–5 input flags on both R & P → 10 pts
    for c in input_cols:
        pts += (1 if bR.get(c)=="yes" else 0)
        pts += (1 if bP.get(c)=="yes" else 0)

    # 6–8 output flags on both → 6 pts
    for c,val in output_cols:
        pts += (1 if bR.get(c)==val else 0)
        pts += (1 if bP.get(c)==val else 0)

    # 9–10 thermo existence on both → 4 pts
    for c in thermo_cols:
        pts += (1 if lR.get(c)=="yes" else 0)
        pts += (1 if lP.get(c)=="yes" else 0)

    # 11–12 reaction ΔH/ΔG error for n != 3 → 2 pts
    if n != "3":
        for diff_key, err_key in [
            ("reaction_dH_diff", "reaction_dH_err_pct"),
            ("reaction_dG_diff", "reaction_dG_err_pct")
        ]:
            diff = row.get(diff_key, None)
            if diff == 0:
                pts += 1
            else:
                err = abs(row.get(err_key, 999.0))
                if   err < 0.5:
                    pts += 1
                elif err < 1.0:
                    pts += 0.5

    # Ring-strain ΔH/ΔG error for all n → up to 2 pts
    for diff_key, err_key in [
        ("strain_dH_diff", "strain_dH_err_pct"),
        ("strain_dG_diff", "strain_dG_err_pct")
    ]:
        diff = row.get(diff_key, None)
        if diff == 0:
            pts += 1
        else:
            err = abs(row.get(err_key, 999.0))
            if   err < 0.5:
                pts += 1
            elif err < 1.0:
                pts += 0.5

    # Denominator: 22 for n=3, else 24
    pct = (pts / (22 if n == "3" else 24)) * 100

    records.append({
        "n":        n_int,
        "reactant": react_name,  # resolved from structure
        "product":  prod_name,   # resolved from structure
        "points":   round(pts, 2),
        "percent":  round(pct, 2),
        # Optional: expected labels (for human check)
        "expected_reactant": f"cyclo{pref.get(str(n_int+1),'?')}ane" if n_int+1 <= 8 else "",
        "expected_product":  f"methylcyclo{pref.get(n,'?')}ane",
    })

# -----------------------------
# 5) Save final score report
# -----------------------------
df_scores = pd.DataFrame(records).sort_values("n", ascending=False)
df_scores.to_csv(root / "RSE_score_report.csv", index=False)
print(df_scores)
