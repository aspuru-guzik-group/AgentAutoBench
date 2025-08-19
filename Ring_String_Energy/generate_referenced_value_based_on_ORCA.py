import os
import sys
import re
import csv
from typing import Optional, List, Tuple

def get_enthalpy(file: str) -> Optional[float]:
    """
    Extracts the total enthalpy value from an ORCA output file.

    Scans the file for a line containing the exact (case-sensitive) phrase
    "Total Enthalpy" and parses the first numeric value on that line.

    Args:
        file (str): Path to the ORCA .out file.

    Returns:
        Optional[float]: Parsed enthalpy as a float if found; otherwise None.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be opened/read.
        UnicodeDecodeError: If the file cannot be decoded as text.
    """
    with open(file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'Total Enthalpy' in line:
            enthalpy = re.search(r'[-+]?\d*\.\d+|\d+', line)
            if enthalpy:
                return float(enthalpy.group(0))
    return None


def get_gibbs(file: str) -> Optional[float]:
    """
    Extracts the final Gibbs free energy value from an ORCA output file.

    Scans the file for a line containing the exact (case-sensitive) phrase
    "Final Gibbs free energy" and parses the first numeric value on that line.

    Args:
        file (str): Path to the ORCA .out file.

    Returns:
        Optional[float]: Parsed Gibbs free energy as a float if found; otherwise None.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: If the file cannot be opened/read.
        UnicodeDecodeError: If the file cannot be decoded as text.
    """
    with open(file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        if 'Final Gibbs free energy' in line:
            gibbs = re.search(r'[-+]?\d*\.\d+|\d+', line)
            if gibbs:
                return float(gibbs.group(0))
    return None


def find_orca_output_files(directory: str) -> Optional[List[str]]:
    """
    Finds ORCA .out files in prioritized subdirectories under a root folder.

    Priority order for scanning immediate subdirectories of `directory`:
      1) Subfolders whose names contain "reopt" or "distorted".
      2) If none found, subfolders whose names contain "opt" but not "re_opt".
    Matches exclude files whose names contain "slurm". All matches under the
    selected subfolders are returned.

    Args:
        directory (str): Root directory containing job subfolders.

    Returns:
        Optional[List[str]]: List of matched .out file paths, or None if no matches.

    Raises:
        FileNotFoundError: If `directory` does not exist.
        NotADirectoryError: If `directory` is not a directory.
        OSError: On OS-level listing or traversal errors.
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(directory)
    if not os.path.isdir(directory):
        raise NotADirectoryError(directory)

    # Gather only the immediate subdirectories of `directory`
    subdirs = [
        os.path.join(directory, d)
        for d in os.listdir(directory)
        if os.path.isdir(os.path.join(directory, d))
    ]
    print("All subdirs:", [os.path.basename(d) for d in subdirs])

    # Step 1: filter for “reopt” or “distorted” in the folder name
    priority_dirs = [
        d for d in subdirs
        if any(kw in os.path.basename(d) for kw in ('reopt', 'distorted'))
    ]
    print("Priority (reopt/distorted) dirs:", [os.path.basename(d) for d in priority_dirs])

    # Step 2: if none, fall back to plain “opt” (excluding “re_opt”)
    if not priority_dirs:
        priority_dirs = [
            d for d in subdirs
            if 'opt' in os.path.basename(d) and 're_opt' not in os.path.basename(d)
        ]
        print("Fallback (opt only) dirs:", [os.path.basename(d) for d in priority_dirs])

    # Now search those selected directories for .out files (skip slurm logs)
    matches: List[str] = []
    for d in priority_dirs:
        for root, _, files in os.walk(d):
            for fn in files:
                if fn.endswith('.out') and 'slurm' not in fn:
                    matches.append(os.path.join(root, fn))

    return matches if matches else None


def auto_enthalpy_and_gibbs(prefix: int, methyl: bool = True) -> Tuple[Optional[float], Optional[float]]:
    """
    Auto-selects a representative ORCA .out file for a ring family and extracts H/G.

    The procedure:
      1) Map the ring-size prefix to a base substring:
         {3:'cycloprop', 4:'cyclobut', 5:'cyclopent', 6:'cyclohex', 7:'cyclohept', 8:'cyclooct'}.
      2) Walk the current directory tree ('.'); collect .out files whose parent
         folder name contains that base substring and (for methyl=True) contains
         "meth" (else excludes "meth"). Files with "slurm" in the name are ignored.
      3) Choose a single file to parse by priority:
           a) Prefer files whose path contains "re_opt" or "distorted".
           b) Otherwise, prefer files whose basename contains "opt".
           c) Otherwise, take the first candidate.
      4) Parse the chosen file with `get_enthalpy` and `get_gibbs`.

    Args:
        prefix (int): Ring-size selector used for the name mapping (3–8).
        methyl (bool, optional): If True, select methyl-substituted ring folders;
            if False, select unsubstituted ring folders. Defaults to True.

    Returns:
        Tuple[Optional[float], Optional[float]]: (enthalpy, gibbs) in the native
            units as parsed from the output (or None for either if not found).

    Raises:
        KeyError: If `prefix` is not in the supported mapping (3–8).
        FileNotFoundError: If no matching .out files are found for the selection.
        OSError: On OS-level traversal or read errors.
        UnicodeDecodeError: If the chosen file cannot be decoded as text.
    """
    mappings = {
        3: 'cycloprop', 4: 'cyclobut', 5: 'cyclopent',
        6: 'cyclohex', 7: 'cyclohept', 8: 'cyclooct'
    }
    name = mappings[prefix]

    candidates: List[str] = []
    for root, _, files in os.walk('.'):
        base = os.path.basename(root)
        if name in base and (('meth' in base) if methyl else ('meth' not in base)):
            for fn in files:
                if fn.endswith('.out') and 'slurm' not in fn:
                    candidates.append(os.path.join(root, fn))

    if not candidates:
        raise FileNotFoundError(f"No .out files found for {name} methyl={methyl}")

    reopt = [f for f in candidates if 're_opt' in f or 'distorted' in f]
    if reopt:
        chosen = reopt[0]
    else:
        opt = [f for f in candidates if 'opt' in os.path.basename(f)]
        chosen = opt[0] if opt else candidates[0]

    H = get_enthalpy(chosen)
    G = get_gibbs(chosen)
    return H, G


def main() -> None:
    """
    Computes reaction energies and ring strain series, prints them, and writes CSV.

    For n = 4..8, computes reaction ΔH/ΔG (kcal/mol) for:
      cyclo-n-ane → methyl-cyclo-(n-1)-ane
    using values parsed by `auto_enthalpy_and_gibbs`, converted with the factor
    2625.5/4.184 (Hartree → kcal/mol). Then accumulates ring strain relative to
    n = 6 and normalizes all strains so that the n = 6 reference is (0, 0).

    Side Effects:
        - Prints two tables to stdout:
            * "cyclo-n-ane to methyl-cyclo-n-ane" reaction energies.
            * "Ring strain wrt n=6" values for n = 3..8.
        - Writes a CSV named "refrenced_data.csv" with the following columns:
            ["Ring Size",
             "Reaction ΔH (kcal/mol)",
             "Reaction ΔG (kcal/mol)",
             "Ring Strain ΔH (kcal/mol)",
             "Ring Strain ΔG (kcal/mol)"]

    Args:
        None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If required .out files are not found for any n.
        KeyError: If an unexpected ring-size prefix is requested internally.
        OSError: On OS-level traversal/read/write errors.
        UnicodeDecodeError: If an output file cannot be decoded as text.
        ValueError: If parsed numeric conversions to float fail.
    """
    energies = {}
    for n in range(4,9):
        energies[n] = {}
        alkane_enthalpy, alkane_gibbs = auto_enthalpy_and_gibbs(n, methyl=False)
        methylcycloalkane_enthalpy, methylcycloalkane_gibbs = auto_enthalpy_and_gibbs(n-1, methyl=True)
        energies[n]['H'] = (methylcycloalkane_enthalpy - alkane_enthalpy)*2625.5/4.184
        energies[n]['G'] = (methylcycloalkane_gibbs - alkane_gibbs)*2625.5/4.184

    print("cyclo-n-ane to methyl-cyclo-n-ane")
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
                writer.writerow([n, "N/A", "N/A",
                                 f"{ref_dict[n]['H']:.2f}",
                                 f"{ref_dict[n]['G']:.2f}"])
            else:
                writer.writerow([n,
                                 f"{energies[n]['H']:.2f}",
                                 f"{energies[n]['G']:.2f}",
                                 f"{ref_dict[n]['H']:.2f}",
                                 f"{ref_dict[n]['G']:.2f}"])


if __name__ == "__main__":
    main()
