import os
import sys
import re
import csv

def get_enthalpy(file):
    with open(file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'Total Enthalpy' in line:
            enthalpy = re.search(r'[-+]?\d*\.\d+|\d+', line)
            if enthalpy:
                return float(enthalpy.group(0))
    return None

def get_gibbs(file):
    with open(file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'Final Gibbs free energy' in line:
            gibbs = re.search(r'[-+]?\d*\.\d+|\d+', line)
            if gibbs:
                return float(gibbs.group(0))
    return None

import os

def find_orca_output_files(directory):
    """
    1) Look first in subfolders whose names contain “re_opt” or “distorted” for .out files;
    2) If none found, look in subfolders whose names contain “opt” but not “re_opt”;
    3) Return a list of matching .out file paths (excluding any with “slurm” in the name),
       or None if no matches.
    """
    # Gather only the immediate subdirectories of `directory`
    subdirs = [
        os.path.join(directory, d)
        for d in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, d))
    ]
    print("All subdirs:", [os.path.basename(d) for d in subdirs])


    # Step 1: filter for “re_opt” or “distorted” in the folder name
    priority_dirs = [
        d for d in subdirs
        if any(kw in os.path.basename(d) for kw in ('reopt', 'distorted'))
    ]
    print("Priority (re_opt/distorted) dirs:", [os.path.basename(d) for d in priority_dirs])

    # Step 2: if none, fall back to plain “opt” (excluding “re_opt”)
    if not priority_dirs:
        priority_dirs = [
            d for d in subdirs
            if 'opt' in os.path.basename(d) and 're_opt' not in os.path.basename(d)
        ]
        print("Fallback (opt only) dirs:", [os.path.basename(d) for d in priority_dirs])


    # Now search those selected directories for .out files (skip slurm logs)
    matches = []
    for d in priority_dirs:
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.endswith('.out') and 'slurm' not in fn:
                    matches.append(os.path.join(root, fn))

    return matches if matches else None


    
def auto_enthalpy_and_gibbs(prefix, methyl=True):
    # 1) map ring-size → base name
    mappings = {
        3: 'cycloprop', 4: 'cyclobut', 5: 'cyclopent',
        6: 'cyclohex', 7: 'cyclohept', 8: 'cyclooct'
    }
    name = mappings[prefix]

    # 2) walk everything under '.', pick .out files whose parent folder
    #    matches our ring AND methyl filter
    candidates = []
    for root, _, files in os.walk('.'):
        base = os.path.basename(root)
        if name in base and (('meth' in base) if methyl else ('meth' not in base)):
            for fn in files:
                if fn.endswith('.out') and 'slurm' not in fn:
                    candidates.append(os.path.join(root, fn))

    if not candidates:
        raise FileNotFoundError(f"No .out files found for {name} methyl={methyl}")

    # 3) apply priority: re_opt/distorted → opt → first
    reopt = [f for f in candidates if 're_opt' in f or 'distorted' in f]
    if reopt:
        chosen = reopt[0]
    else:
        opt = [f for f in candidates if 'opt' in os.path.basename(f)]
        chosen = opt[0] if opt else candidates[0]

    # 4) parse that single file
    H = get_enthalpy(chosen)
    G = get_gibbs(chosen)
    return H, G

    
def main():
    energies = {}
    for n in range(4,9):
        energies[n] = {}
        alkane_enthalpy, alkane_gibbs = auto_enthalpy_and_gibbs(n, methyl=False)
        methylcycloalkane_enthalpy, methylcycloalkane_gibbs = auto_enthalpy_and_gibbs(n-1, methyl=True)
        energies[n]['H'] = (methylcycloalkane_enthalpy - alkane_enthalpy)*2625.5/4.184
        energies[n]['G'] = (methylcycloalkane_gibbs - alkane_gibbs)*2625.5/4.184

    print("cyclo-n-ane to methyl-cyclo-n-ane")
    # print the results
    for key, value in energies.items():
        print(f"{key} : {value['H']:.2f} {value['G']:.2f}")
        
    print("Ring strain wrt n=6")
    ref_dict = {n: {'H': 0, 'G': 0} for n in range(3, 9)}
    for n in range(8, 3, -1):
        ref_dict[n-1]['H'] = energies[n]['H'] + ref_dict[n]['H']
        ref_dict[n-1]['G'] = energies[n]['G'] + ref_dict[n]['G']
        
    reference_enthalpy = ref_dict[6]['H']
    reference_gibbs = ref_dict[6]['G']
    for n in range(3, 9):
        ref_dict[n]['H'] -= reference_enthalpy
        ref_dict[n]['G'] -= reference_gibbs
        
    for key, value in ref_dict.items():
        print(f"{key} : {value['H']:.2f} {value['G']:.2f}")

    with open("refrenced_data.csv", "w", newline="") as fout:
        writer = csv.writer(fout)
        writer.writerow(
            [
                "Ring Size",
                "Reaction ΔH (kcal/mol)",
                "Reaction ΔG (kcal/mol)",
                "Ring Strain ΔH (kcal/mol)",
                "Ring Strain ΔG (kcal/mol)",
            ]
        )
        for n in range(3, 9):
            if n == 3:
                writer.writerow(
                    [
                        n,
                        "N/A",
                        "N/A",
                        f"{ref_dict[n]['H']:.2f}",
                        f"{ref_dict[n]['G']:.2f}",
                    ]
                )
            else:
                writer.writerow(
                    [
                        n,
                        f"{energies[n]['H']:.2f}",
                        f"{energies[n]['G']:.2f}",
                        f"{ref_dict[n]['H']:.2f}",
                        f"{ref_dict[n]['G']:.2f}",
                    ]
                )
    
if __name__ == "__main__":
    main()
