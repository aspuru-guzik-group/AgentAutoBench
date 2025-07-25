import pandas as pd
from pathlib import Path

# Paths to the CSV reports
root_dir = Path("Your_root_path")
bool_csv = root_dir / "carbocation_boolean_report.csv"
logic_csv = root_dir / "carbocation_logic_report.csv"
num_csv = root_dir / "carbocation_numerical_report.csv"

# Load data
df_bool = pd.read_csv(bool_csv).set_index("Folder")
df_logic = pd.read_csv(logic_csv).set_index("species")
df_num = pd.read_csv(num_csv).set_index("species")

# Species to score
species_list = df_num.index.tolist()

# Prepare results
score_records = []

for sp in species_list:
    b = df_bool.loc[sp]
    l = df_logic.loc[sp]
    n = df_num.loc[sp]
    
    points = 0.0
    
    # 1-5 Input existence
    points += 1 if b["Method exist?"] == "yes" else 0
    points += 1 if b["Basis set exist?"] == "yes" else 0
    points += 1 if b["Tasks exist?"] == "yes" else 0
    points += 1 if b["Charge & mult exist?"] == "yes" else 0
    points += 1 if b["XYZ file exist?"] == "yes" else 0
    
    # 6-8 Output convergence
    points += 1 if b["SCF converged?"] == "yes" else 0
    points += 1 if b["Geo opt converged?"] == "yes" else 0
    points += 1 if b["Imag freq exist?"] == "no"  else 0
    
    # 9-10 Thermo existence
    points += 1 if l["enthalpy_exist"] == "yes" else 0
    points += 1 if l["gibbs_exist"] == "yes" else 0
    
    # 11-12 Numerical errors
    dh_err = abs(n["dH_err_pct"])
    dg_err = abs(n["dG_err_pct"])
    # delta-H
    if dh_err < 0.5:
        points += 1
    elif dh_err < 1.0:
        points += 0.5
    # delta-G
    if dg_err < 0.5:
        points += 1
    elif dg_err < 1.0:
        points += 0.5
    
    # Percentage score
    pct = (points / 12) * 100
    
    score_records.append({
        "species": sp,
        "score_points": points,
        "score_pct": round(pct, 2)
    })

# Build DataFrame and save
df_scores = pd.DataFrame(score_records)
score_csv = root_dir / "carbocation_score_report.csv"
df_scores.to_csv(score_csv, index=False)

# Display results
df_scores