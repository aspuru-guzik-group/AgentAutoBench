import re
import unicodedata
import pandas as pd
from pathlib import Path

# --- Setup paths ---
root_dir = Path("/Users/a2011230025/Desktop/Ring_Strain_Energy_test_3")
calc_csv = root_dir / "report.csv"
ref_csv  = root_dir / "refrenced_data.csv"  # keep as-is per your current layout

# --- 1) Logic report: existence of thermal data in each species folder ---
def check_enthalpy_exist(txt: str) -> bool:
    return "Total enthalpy" in txt

def check_gibbs_exist(txt: str) -> bool:
    return "Final Gibbs free energy" in txt

logic_records = []
for folder in root_dir.iterdir():
    if not folder.is_dir():
        continue
    if folder.name.lower() in ("results", "jobinfo"):
        continue
    out_file = next((f for f in folder.glob("*.out")
                     if "slurm" not in f.name.lower()), None)
    logic_records.append({
        "species": folder.name,
        "out_exist":       "yes" if out_file else "no",
        "enthalpy_exist":  "yes" if out_file and check_enthalpy_exist(out_file.read_text()) else "no",
        "gibbs_exist":     "yes" if out_file and check_gibbs_exist(out_file.read_text())   else "no"
    })
df_logic = pd.DataFrame(logic_records)
logic_csv = root_dir / "RSE_logic_report.csv"
df_logic.to_csv(logic_csv, index=False)

# -------------------------
# --- 2) Numerical report ---
#     Auto-detect headers and standardize column names
# -------------------------

def _normalize_label(s: str) -> str:
    """Normalize a header for robust matching, keeping ΔH/ΔG info."""
    s = unicodedata.normalize("NFKC", s or "")
    # unify delta symbol
    s = s.replace("Δ", "delta")
    # expose (deltaH)/(deltaG) -> ' delta h ' / ' delta g '
    s = re.sub(r"\(\s*(delta\s*[hg]|d\s*[hg])\s*\)", r" \1 ", s, flags=re.I)
    # add space between 'delta' or 'd' and H/G when adjacent (e.g., 'deltaH' -> 'delta h')
    s = re.sub(r"\b(delta)\s*([hg])\b", r"\1 \2", s, flags=re.I)
    s = re.sub(r"\b(d)\s*([hg])\b", r"\1 \2", s, flags=re.I)
    # drop unit parentheses like (kcal/mol), (kJ/mol), (hartree), (au)
    s = re.sub(r"\(\s*(k(?:cal|j)\/mol|hartree|au)\s*\)", " ", s, flags=re.I)
    # remove any remaining brackets but keep content
    s = s.replace("(", " ").replace(")", " ")
    # normalize synonyms and spacing
    s = re.sub(r"\b(rx|rxn)\b", "reaction", s, flags=re.I)
    s = re.sub(r"[_\-]+", " ", s)
    s = re.sub(r"\s+", " ", s.strip())
    return s.lower()

def _auto_map_columns(columns):
    """Return dict canonical_key -> original_column_header detected in CSV."""
    norm = {c: _normalize_label(c) for c in columns}

    def pick(predicate, *, exclude=None):
        for c, cn in norm.items():
            if predicate(cn) and not (exclude and exclude(cn)):
                return c
        return None

    is_strain = lambda cn: "strain" in cn
    has_dh    = lambda cn: bool(re.search(r"\b(delta|d)\s*h\b|\benthalpy\b", cn))
    has_dg    = lambda cn: bool(re.search(r"\b(delta|d)\s*g\b|\bgibbs\b|\bfree energy\b", cn))

    # 1) ring_size
    ring = pick(lambda cn: ("ring" in cn and "size" in cn) or re.search(r"\bring\b.*\bsize\b", cn))
    if not ring:
        # mild fallback: column named just "n"
        ring = pick(lambda cn: cn in {"n", "ring n", "size n"})
    if not ring:
        raise KeyError(f"Could not find column for 'ring_size'. Available columns: {list(columns)}")

    # 2) strain_dH / strain_dG (must include 'strain')
    strain_h = pick(lambda cn: is_strain(cn) and has_dh(cn))
    strain_g = pick(lambda cn: is_strain(cn) and has_dg(cn))
    if not strain_h:
        raise KeyError(f"Could not find column for 'strain_dH'. Available columns: {list(columns)}")
    if not strain_g:
        raise KeyError(f"Could not find column for 'strain_dG'. Available columns: {list(columns)}")

    # 3) reaction_dH / reaction_dG (delta H/G but NOT 'strain')
    rxn_h = pick(has_dh, exclude=is_strain)
    rxn_g = pick(has_dg, exclude=is_strain)
    if not rxn_h:
        raise KeyError(f"Could not find column for 'reaction_dH'. Available columns: {list(columns)}")
    if not rxn_g:
        raise KeyError(f"Could not find column for 'reaction_dG'. Available columns: {list(columns)}")

    return {
        "ring_size": ring,
        "reaction_dH": rxn_h,
        "reaction_dG": rxn_g,
        "strain_dH": strain_h,
        "strain_dG": strain_g,
    }

# 1) Load and auto-detect/standardize column names
df_rep_raw = pd.read_csv(calc_csv)
rep_map = _auto_map_columns(df_rep_raw.columns)
df_rep = df_rep_raw.rename(columns={
    rep_map["ring_size"]:      "ring_size",
    rep_map["reaction_dH"]:    "reaction_dH_report",
    rep_map["reaction_dG"]:    "reaction_dG_report",
    rep_map["strain_dH"]:      "strain_dH_report",
    rep_map["strain_dG"]:      "strain_dG_report",
})

df_ref_raw = pd.read_csv(ref_csv)
ref_map = _auto_map_columns(df_ref_raw.columns)
df_ref = df_ref_raw.rename(columns={
    ref_map["ring_size"]:      "ring_size",
    ref_map["reaction_dH"]:    "reaction_dH_ref",
    ref_map["reaction_dG"]:    "reaction_dG_ref",
    ref_map["strain_dH"]:      "strain_dH_ref",
    ref_map["strain_dG"]:      "strain_dG_ref",
})

# 2) Merge on ring_size
df = pd.merge(df_rep, df_ref, on="ring_size", how="inner")

# 3) Coerce to numeric (N/A → NaN)
for col in [
    "reaction_dH_report","reaction_dG_report",
    "strain_dH_report","strain_dG_report",
    "reaction_dH_ref",   "reaction_dG_ref",
    "strain_dH_ref",     "strain_dG_ref"
]:
    df[col] = pd.to_numeric(df[col], errors="coerce")

# 4) Compute absolute differences
df["reaction_dH_diff"] = df["reaction_dH_report"] - df["reaction_dH_ref"]
df["reaction_dG_diff"] = df["reaction_dG_report"] - df["reaction_dG_ref"]
df["strain_dH_diff"]   = df["strain_dH_report"]   - df["strain_dH_ref"]
df["strain_dG_diff"]   = df["strain_dG_report"]   - df["strain_dG_ref"]

# 5) Compute percent errors
df["reaction_dH_err_pct"] = df["reaction_dH_diff"] / df["reaction_dH_ref"] * 100
df["reaction_dG_err_pct"] = df["reaction_dG_diff"] / df["reaction_dG_ref"] * 100
df["strain_dH_err_pct"]   = df["strain_dH_diff"]   / df["strain_dH_ref"]   * 100
df["strain_dG_err_pct"]   = df["strain_dG_diff"]   / df["strain_dG_ref"]   * 100

# 6) Save clean numerical report
out_csv = root_dir / "RSE_numerical_report.csv"
df.to_csv(out_csv, index=False)
print("Saved numerical report to:", out_csv)
print(df)
