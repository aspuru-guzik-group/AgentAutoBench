# Auto_benchmark/io/fs.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional
import re
from Auto_benchmark.Config import defaults

# RDKit imports (wrapped to avoid crash if missing, though likely required)
try:
    from rdkit import Chem
    from rdkit.Chem import rdmolfiles, rdDetermineBonds
    from rdkit.Chem import inchi as rd_inchi
except ImportError:
    Chem = None

# ---------- Freq / Output Parsing Utilities ----------

def _extract_freqs(txt: str) -> List[float]:
    """
    Extract vibrational frequencies from ORCA output text.
    Searches first within the 'VIBRATIONAL FREQUENCIES' block, then globally.

    Args:
        txt (str): The output file content.

    Returns:
        List[float]: A list of extracted frequency values.
    """
    lines = txt.splitlines()
    block_start = None
    for i, line in enumerate(lines):
        if defaults.RE_FREQ_BLOCK.search(line):
            block_start = i
            break
    candidates: List[float] = []
    if block_start is not None:
        scan = "\n".join(lines[block_start:block_start + 400])
        candidates = [float(m.group(1)) for m in defaults.RE_FREQ_VAL.finditer(scan)]
    if not candidates:
        candidates = [float(m.group(1)) for m in defaults.RE_FREQ_VAL.finditer(txt)]
    return candidates

def _read_primary_out(folder: Path) -> Optional[Path]:
    """
    Find a primary .out file in a folder, preferring 'orca.out'.

    Args:
        folder (Path): The directory to search.

    Returns:
        Optional[Path]: The path to the selected output file, or None.
    """
    outs = [p for p in folder.glob(defaults.OUT_GLOB)
            if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    if not outs:
        return None
    # If explicit 'orca.out' exists, prefer it
    return next((p for p in outs if p.name.lower() == defaults.PRIMARY_OUT_FILENAME), outs[0])

def find_best_out_for_qc(folder: Path) -> Optional[Path]:
    """
    Find the best .out file for QC checks (e.g., frequencies).
    Prioritizes files with real frequencies over those with imaginary or no frequencies.

    Rank: 0=All Freqs Real, 1=No Freqs, 2=Imaginary Freqs, 3=Unreadable

    Args:
        folder (Path): The directory to search.

    Returns:
        Optional[Path]: The best candidate output file.
    """
    outs = [p for p in folder.glob(defaults.OUT_GLOB)
            if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    if not outs:
        return None

    def _rank(p: Path):
        try:
            txt = p.read_text(errors="ignore")
        except Exception:
            return (3, p.name.lower())
        freqs = _extract_freqs(txt)
        if not freqs:
            return (1, p.name.lower())
        return (0 if all(f >= 0.0 for f in freqs) else 2, p.name.lower())

    best = min(outs, key=_rank)
    # If the 'best' isn't perfect (rank 0), check if 'orca.out' exists and use it as fallback anchor
    if _rank(best)[0] != 0:
        prim = _read_primary_out(folder)
        return prim if prim else best
    return best

def folder_has_real_freqs(folder: Path) -> Optional[bool]:
    """
    Check if the primary output in the folder has only real frequencies.

    Args:
        folder (Path): The directory to check.

    Returns:
        Optional[bool]: True if real freqs exist, False if imaginary exists, None if unreadable.
    """
    outp = _read_primary_out(folder)
    if outp is None:
        return None
    try:
        txt = outp.read_text(errors="ignore")
    except Exception:
        return None
    freqs = _extract_freqs(txt)
    if not freqs:
        return None
    return all(f >= 0.0 for f in freqs)

def has_non_slurm_out(folder: Path) -> bool:
    """
    Check if folder contains any .out file that isn't a slurm log.

    Args:
        folder (Path): The directory to check.

    Returns:
        bool: True if a valid output file exists.
    """
    outs = [p for p in folder.glob(defaults.OUT_GLOB)]
    outs = [p for p in outs if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    return bool(outs)

# ---------- RDKit / Structure Helpers ----------

def inchikey_from_smiles(smiles: str) -> str:
    """
    Generate InChIKey from a SMILES string.

    Args:
        smiles (str): The SMILES string.

    Returns:
        str: The InChIKey.

    Raises:
        ImportError: If RDKit is not installed.
        ValueError: If SMILES parsing fails.
    """
    if Chem is None: raise ImportError("RDKit not installed.")
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError(f"Cannot parse SMILES: {smiles}")
    return rd_inchi.MolToInchiKey(m)

def inchikey_from_xyz(xyz_path: Path) -> str:
    """
    Generate InChIKey from an XYZ file.

    Args:
        xyz_path (Path): Path to the XYZ file.

    Returns:
        str: The InChIKey.

    Raises:
        ImportError: If RDKit is not installed.
        ValueError: If XYZ reading fails.
    """
    if Chem is None: raise ImportError("RDKit not installed.")
    m = None
    try:
        m = rdmolfiles.MolFromXYZFile(str(xyz_path))
    except Exception:
        m = None
    if m is None:
        txt = xyz_path.read_text(errors="ignore")
        m = rdmolfiles.MolFromXYZBlock(txt)
    if m is None:
        raise ValueError(f"Failed to read XYZ: {xyz_path}")
    rdDetermineBonds.DetermineBonds(m)
    try:
        Chem.SanitizeMol(m)
    except Exception:
        pass
    return rd_inchi.MolToInchiKey(m)

def _pick_primary_xyz(folder: Path) -> Optional[Path]:
    """
    Heuristic to pick the main XYZ file (skipping trajectories/initials).

    Args:
        folder (Path): The directory to search.

    Returns:
        Optional[Path]: The best candidate XYZ file.
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

# ---------- Folder Iteration & Selection ----------

def iter_child_folders(root: Path) -> List[Path]:
    """
    Return list of subdirectories, filtering out SKIP_DIRS.

    Args:
        root (Path): The root directory.

    Returns:
        List[Path]: A list of valid subdirectory paths.
    """
    root = Path(root)
    folders: List[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if any(skip.lower() in p.name.lower() for skip in defaults.SKIP_DIRS):
            continue
        folders.append(p)
    return folders

def select_unique_by_inchikey(root_dir: Path, *, prefer_real_freqs: bool = True) -> List[Path]:
    """
    Select one representative folder per unique structure (InChIKey).
    Falls back to folder name if XYZ parsing fails.

    Args:
        root_dir (Path): The root directory to scan.
        prefer_real_freqs (bool): If True, prefer folders with real frequencies when duplicates exist.

    Returns:
        List[Path]: A list of representative folder paths.
    """
    groups: Dict[str, List[Path]] = {}
    for folder in iter_child_folders(root_dir):
        key: Optional[str] = None
        xyz = _pick_primary_xyz(folder)
        if xyz:
            try:
                key = inchikey_from_xyz(xyz)
            except Exception:
                key = None
        if key is None:
            # Fallback to name-based key
            key = f"__name__:{folder.name.lower()}"
        groups.setdefault(key, []).append(folder)

    reps: List[Path] = []
    for _, flist in groups.items():
        with_out = [f for f in flist if has_non_slurm_out(f)]
        pool = with_out if with_out else flist

        chosen: Optional[Path] = None
        if prefer_real_freqs:
            for f in pool:
                ok = folder_has_real_freqs(f)
                if ok is True:
                    chosen = f
                    break
        if chosen is None:
            chosen = pool[0]
        reps.append(chosen)

    return reps
