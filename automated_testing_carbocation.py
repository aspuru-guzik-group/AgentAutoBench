import re
import pandas as pd
from pathlib import Path

# --- Setup paths ---
root_dir = Path("Your_root_path")
calc_csv = root_dir / "results" / "carbocation_formation_energies.csv"
ref_csv  = Path("Your_referenced_value")

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
logic_csv = root_dir / "carbocation_logic_report.csv"
df_logic.to_csv(logic_csv, index=False)

# --- 2) Numerical report: formation energetics errors for RH only ---
df_calc = pd.read_csv(calc_csv)
df_ref  = pd.read_csv(ref_csv)

# --- Dynamically detect ΔH & ΔG in df_calc ---
h_calc_col = next(c for c in df_calc.columns if "h" in c.lower() and "kcal" in c.lower())
g_calc_col = next(c for c in df_calc.columns if "g" in c.lower() and "kcal" in c.lower())
df_calc = df_calc.rename(columns={h_calc_col: "dH_calc", g_calc_col: "dG_calc"})

# --- Dynamically detect ΔH & ΔG in df_ref ---
h_ref_col = next(c for c in df_ref.columns if "h" in c.lower() and "kcal" in c.lower())
g_ref_col = next(c for c in df_ref.columns if "g" in c.lower() and "kcal" in c.lower())
df_ref  = df_ref.rename(columns={h_ref_col: "dH_ref", g_ref_col: "dG_ref"})

# --- Detect key columns for species in both tables ---
calc_key = next((c for c in ("Reactant","Molecule","RH") if c in df_calc.columns),
                df_calc.columns[0])
ref_key  = next((c for c in ("Reactant","Molecule","RH") if c in df_ref.columns),
                df_ref.columns[0])

# --- Normalize to a common 'species' column ---
def normalize(s):
    return (
        s.strip()
         .lower()
         .replace("(", "")
         .replace(")", "")
         .replace(" ", "_")
    )

df_calc["species"] = df_calc[calc_key].astype(str).apply(normalize)
df_ref["species"]  = df_ref[ref_key].astype(str).apply(normalize)

# --- Drop old key columns ---
df_calc = df_calc.drop(columns=[calc_key])
df_ref  = df_ref.drop(columns=[ref_key])

# --- Merge and compute errors ---
df_num = pd.merge(df_calc, df_ref, on="species", how="inner")
df_num["dH_diff"]    = df_num["dH_calc"] - df_num["dH_ref"]
df_num["dH_err_pct"] = df_num["dH_diff"] / df_num["dH_ref"] * 100
df_num["dG_diff"]    = df_num["dG_calc"] - df_num["dG_ref"]
df_num["dG_err_pct"] = df_num["dG_diff"] / df_num["dG_ref"] * 100

# --- Dynamically filter to subfolder species (excluding results/jobinfo) ---
original_species = [
    f.name.lower() for f in root_dir.iterdir()
    if f.is_dir() and f.name.lower() not in ("results","jobinfo")
]
df_num = df_num[df_num["species"].isin(original_species)].reset_index(drop=True)

# --- Save numeric report ---
numerical_csv = root_dir / "carbocation_numerical_report.csv"
df_num.to_csv(numerical_csv, index=False)
print(f"Numerical report saved to: {numerical_csv}")
print(df_num)