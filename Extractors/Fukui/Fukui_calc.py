# Auto_benchmark/Extractors/Fukui/Fukui_calc.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List

# Import the extractor
from Auto_benchmark.Extractors.Fukui.extractor_Fukui import extract_fukui_charges
# Import safe reader utility
from Auto_benchmark.io.readers import read_text_safe

def calculate_fukui_indices(outs: List[Path]) -> Dict[str, Any]:
    """
    Calculates ground truth Condensed Fukui Indices (f+, f-) for Carbon atoms (0-6).
    
    Logic:
      1. Filter output files to EXCLUDE optimization runs (contain 'opt' but not 'sp').
      2. Bucket remaining files into Cation, Neutral, and Anion species.
      3. Extract atomic charges (Mulliken, Hirshfeld, Loewdin).
      4. Apply Finite Difference formulas.
    """
    
    # 1. Pre-selection: Filter out Optimization files
    # We want Single Point (SP) calculations. 
    # If a file/folder says "opt" and NOT "sp", we assume it's a geometry optimization and skip it.
    filtered_outs = []
    for p in outs:
        name = p.name.lower()
        folder = p.parent.name.lower()
        
        # Skip slurm files
        if name.startswith("slurm"):
            continue
            
        # Check for explicit "opt" without "sp" in filename
        if "opt" in name and "sp" not in name:
            continue
            
        # Check for explicit "opt" without "sp" in folder name
        if "opt" in folder and "sp" not in folder:
            continue
            
        filtered_outs.append(p)

    # 2. Bucket files by species
    candidates = {"cation": [], "neutral": [], "anion": []}
    
    for p in filtered_outs:
        fname = p.name.lower()
        
        if "cation" in fname:
            candidates["cation"].append(p)
        elif "anion" in fname:
            candidates["anion"].append(p)
        elif "neutral" in fname:
            candidates["neutral"].append(p)
        else:
            # Fallback: if 'neutral' keyword isn't explicit, but it passed the OPT filter,
            # and isn't cation/anion, it might be the neutral SP file (e.g. "toluene_sp.out")
            candidates["neutral"].append(p)

    # 3. Select BEST file for each species
    # (If multiple exist after filtering, prefer 'sp' explicit naming, then shortest/alpha)
    file_map = {"cation": None, "neutral": None, "anion": None}
    
    for species, paths in candidates.items():
        if not paths: continue
        # Sort key: 
        # 1. Has "sp" in name? (True > False)
        # 2. Length of name (shorter usually better/cleaner)
        best = sorted(paths, key=lambda x: ("sp" in x.name.lower(), -len(x.name)), reverse=True)[0]
        file_map[species] = best

    # 4. Extract Data
    charge_data = {k: {} for k in file_map}
    for species, p in file_map.items():
        if p:
            text = read_text_safe(p)
            charge_data[species] = extract_fukui_charges(text)

    # 5. Calculate Indices
    methods = ["mulliken", "hirshfeld", "loewdin"]
    results = {}
    
    # Helper to get vector for atoms 0-6
    def get_vec(species, method):
        data = charge_data[species].get(method, {})
        # Ensure we have all 7 carbons (indices 0-6)
        if not data: return None
        try:
            return [data[i] for i in range(7)]
        except KeyError:
            return None

    for m in methods:
        # Get Charge Vectors (q)
        q_cat = get_vec("cation", m)   # N-1
        q_neu = get_vec("neutral", m)  # N
        q_ani = get_vec("anion", m)    # N+1
        
        # Init keys
        results[f"f_plus_{m.capitalize()}"] = None
        results[f"f_minus_{m.capitalize()}"] = None

        # Calculate f+ = q(N) - q(N+1)
        if q_neu and q_ani:
            results[f"f_plus_{m.capitalize()}"] = [
                round(n - a, 4) for n, a in zip(q_neu, q_ani)
            ]

        # Calculate f- = q(N-1) - q(N)
        if q_cat and q_neu:
            results[f"f_minus_{m.capitalize()}"] = [
                round(c - n, 4) for c, n in zip(q_cat, q_neu)
            ]

    return results