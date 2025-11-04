from __future__ import annotations
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re
import os
import pandas as pd

from Auto_benchmark.Config import defaults

from rdkit import Chem
from rdkit.Chem import rdmolfiles, rdDetermineBonds
from rdkit.Chem import inchi as rd_inchi

# ---------- freq parsing ----------
def _extract_freqs(txt: str) -> List[float]:
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
    outs = [p for p in folder.glob(defaults.OUT_GLOB)
            if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    if not outs:
        return None
    return next((p for p in outs if p.name.lower() == "orca.out"), outs[0])

def find_best_out_for_qc(folder: Path) -> Optional[Path]:
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
            return (1, p.name.lower())  # no freq block → neutral
        return (0 if all(f >= 0.0 for f in freqs) else 2, p.name.lower())

    best = min(outs, key=_rank)
    if _rank(best)[0] != 0:
        prim = _read_primary_out(folder)
        return prim if prim else best
    return best

def folder_has_real_freqs(folder: Path) -> Optional[bool]:
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

# ---------- RDKit helpers ----------
def inchikey_from_smiles(smiles: str) -> str:
    m = Chem.MolFromSmiles(smiles)
    if m is None:
        raise ValueError(f"Cannot parse SMILES: {smiles}")
    return rd_inchi.MolToInchiKey(m)

def inchikey_from_xyz(xyz_path: Path) -> str:
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

def has_non_slurm_out(folder: Path) -> bool:
    outs = [p for p in folder.glob(defaults.OUT_GLOB)]
    outs = [p for p in outs if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    return bool(outs)

# ---------- listing ----------
def iter_child_folders(root: Path) -> List[Path]:
    root = Path(root)
    folders: List[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if any(skip.lower() in p.name.lower() for skip in defaults.SKIP_DIRS):
            continue
        folders.append(p)
    return folders

# ---------- structure index + representatives (with robust fallback) ----------
def build_structure_index(root_dir: Path) -> Dict[str, Dict[str, object]]:
    """
    Key: structure key (InChIKey when possible; else a name-based fallback)
    """
    idx: Dict[str, Dict[str, object]] = {}
    for folder in iter_child_folders(root_dir):
        key: Optional[str] = None
        xyz = _pick_primary_xyz(folder)
        if xyz:
            try:
                key = inchikey_from_xyz(xyz)
            except Exception:
                key = None
        if key is None:
            # Fallback so folders like C4H8 (bad XYZ) still participate
            key = f"__name__:{folder.name.lower()}"
        # first occurrence wins
        idx.setdefault(key, {"folder": folder, "xyz": xyz})
    return idx

def select_unique_by_inchikey(root_dir: Path, *, prefer_real_freqs: bool = True) -> List[Path]:
    """
    One representative per structure. If XYZ→InChIKey fails, we use a
    name-based fallback key so the folder is not dropped.
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
            key = f"__name__:{folder.name.lower()}"  # ← fallback to include folder
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

# ---------- scorer common helpers ----------
def _norm_str(x: Any) -> str:
    return str(x).strip().lower()

def _is_yes(x: Any) -> bool:
    if isinstance(x, bool):
        return x
    if x is None:
        return False
    return _norm_str(x) in defaults.YES_VALUES

def _is_no(x: Any) -> bool:
    if isinstance(x, bool):
        return not x
    if x is None:
        return False
    return _norm_str(x) in defaults.NO_VALUES


def _abs_err(gt: Optional[float], pred: Optional[float]) -> Optional[float]:
    """
    Compute absolute error between ground truth and prediction.
    Returns None if any value is invalid or missing.
    """
    if gt is None or pred is None:
        return None
    try:
        gt = float(gt)
        pred = float(pred)
        return abs(pred - gt)
    except Exception:
        return None


def _rel_err(gt: Optional[float], pred: Optional[float]) -> Optional[float]:
    """
    Compute relative error between ground truth and prediction.
    Returns None if ground truth is 0 or any value is invalid.
    """
    abs_err = _abs_err(gt, pred)
    if abs_err is None:
        return None

    try:
        gt = float(gt)
        if gt == 0:
            return None
        return abs_err / abs(gt)
    except Exception:
        return None
    

def _find_column(df: pd.DataFrame, name: str) -> str:
    """Robust header matching: exact (case-insensitive), then alnum-only fuzzy."""
    norm = {str(c): c for c in df.columns}
    want = name.strip().lower()
    for k, v in norm.items():
        if k.strip().lower() == want:
            return v
    want_alnum = re.sub(r"[^a-z0-9]+", "", want)
    for k, v in norm.items():
        if re.sub(r"[^a-z0-9]+", "", k.strip().lower()) == want_alnum:
            return v
    raise KeyError(f"Column not found: {name}")
