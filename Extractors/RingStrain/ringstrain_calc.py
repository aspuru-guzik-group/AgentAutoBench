# Auto_benchmark/Extractors/RingStrain/ringstrain_calc.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from .extractor_RS import extract_rs_core
from Auto_benchmark.io import fs
from Auto_benchmark.Config.defaults import (
    HARTREE_TO_KCAL as _HARTREE_TO_KCAL,
    SKIP_DIRS,
    OUT_GLOB,
    SKIP_OUTFILE_PREFIXES,
)

from rdkit import Chem
from rdkit.Chem import rdmolfiles, rdDetermineBonds

# ===============================================================
# XYZ loaders (unchanged)
# ===============================================================
def _load_xyz_text_sanitized(xyz_path: Path) -> str:
    lines = xyz_path.read_text(errors="ignore").splitlines()
    if len(lines) < 3:
        return "\n".join(lines)
    header = lines[:2]
    atoms = lines[2:]
    sanitized: List[str] = []
    for line in atoms:
        if not line.strip():
            sanitized.append(line)
            continue
        parts = line.split()
        if len(parts) >= 4:
            sym = parts[0]
            coords = parts[1:4]
            try:
                _ = float(coords[0]); _ = float(coords[1]); _ = float(coords[2])
                sanitized.append(" ".join([sym] + coords))
            except Exception:
                sanitized.append(line)
        else:
            sanitized.append(line)
    return "\n".join(header + sanitized)


def _load_mol_from_xyz(xyz_path: Path) -> Optional[Chem.Mol]:
    try:
        block = _load_xyz_text_sanitized(xyz_path)
    except Exception:
        try:
            block = xyz_path.read_text(errors="ignore")
        except Exception:
            return None
    m = None
    try:
        m = rdmolfiles.MolFromXYZBlock(block)
    except Exception:
        m = None
    if m is None:
        return None
    try:
        rdDetermineBonds.DetermineBonds(m)
        Chem.SanitizeMol(m)
    except Exception:
        pass
    return m


def _primary_xyz(folder: Path) -> Optional[Path]:
    try:
        return fs._pick_primary_xyz(folder)  # type: ignore[attr-defined]
    except Exception:
        xyzs = sorted(folder.glob("*.xyz"))
        return xyzs[0] if xyzs else None

# ===============================================================
# .out discovery + energy extraction
# ===============================================================
def _read_primary_out(folder: Path) -> Optional[Path]:
    try:
        p = fs._read_primary_out(folder)  # type: ignore[attr-defined]
        if p:
            return p
    except Exception:
        pass
    for child in sorted(folder.iterdir()):
        if not child.is_dir():
            continue
        if any(skip.lower() in child.name.lower() for skip in SKIP_DIRS):
            continue
        outs = [q for q in child.glob(OUT_GLOB)]
        outs = [q for q in outs if not q.name.lower().startswith(SKIP_OUTFILE_PREFIXES)]
        if outs:
            exact = [q for q in outs if q.name.lower() == "orca.out"]
            return exact[0] if exact else outs[0]
    return None


def _extract_HG_from_folder(folder: Path) -> Tuple[Optional[float], Optional[float]]:
    outp = _read_primary_out(folder)
    if not outp:
        return (None, None)
    try:
        txt = outp.read_text(errors="ignore")
    except Exception:
        return (None, None)
    core = extract_rs_core(txt)
    return core.get("H_total_au"), core.get("G_total_au")

# ===============================================================
# RDKit topology helpers (unchanged)
# ===============================================================
def _sssr_rings(m: Chem.Mol) -> List[List[int]]:
    try:
        sssr = Chem.GetSymmSSSR(m)
        return [list(map(int, r)) for r in sssr]
    except Exception:
        return []

def _is_single_ring_allC_all_single(m: Chem.Mol) -> Optional[List[int]]:
    rings = _sssr_rings(m)
    if len(rings) != 1:
        return None
    ring = rings[0]
    for aidx in ring:
        if m.GetAtomWithIdx(aidx).GetAtomicNum() != 6:
            return None
    for aidx in ring:
        a = m.GetAtomWithIdx(aidx)
        for n in a.GetNeighbors():
            if n.GetIdx() in ring:
                b = m.GetBondBetweenAtoms(aidx, n.GetIdx())
                if not b or b.GetBondType() != Chem.rdchem.BondType.SINGLE:
                    return None
    return ring

def _ring_heavy_neighbors(m: Chem.Mol, ring: List[int], aidx: int) -> List[Chem.Atom]:
    a = m.GetAtomWithIdx(aidx)
    return [n for n in a.GetNeighbors() if n.GetAtomicNum() > 1]

def _is_cycloalkane_single_ring(m: Chem.Mol) -> Optional[int]:
    ring = _is_single_ring_allC_all_single(m)
    if ring is None:
        return None
    for aidx in ring:
        heavy_nbrs = _ring_heavy_neighbors(m, ring, aidx)
        ring_nbrs = [n for n in heavy_nbrs if n.GetIdx() in ring]
        if len(heavy_nbrs) != 2 or len(ring_nbrs) != 2:
            return None
    return len(ring)

def _is_terminal_carbon(m: Chem.Mol, a: Chem.Atom) -> bool:
    if a.GetAtomicNum() != 6:
        return False
    heavy_deg = sum(1 for nn in a.GetNeighbors() if nn.GetAtomicNum() > 1)
    return heavy_deg == 1

def _is_methylcyclo_single_ring(m: Chem.Mol) -> Optional[int]:
    ring = _is_single_ring_allC_all_single(m)
    if ring is None:
        return None
    methyl_anchor_count = 0
    for aidx in ring:
        exo_heavy = [n for n in m.GetAtomWithIdx(aidx).GetNeighbors()
                     if (n.GetIdx() not in ring and n.GetAtomicNum() > 1)]
        if not exo_heavy:
            continue
        for ex in exo_heavy:
            if _is_terminal_carbon(m, ex):
                methyl_anchor_count += 1
            else:
                return None
    if methyl_anchor_count == 1:
        return len(ring)
    return None

# ===============================================================
# NEW: name-based fallback
# ===============================================================
_FORMULA_RE = re.compile(r"C(\d+)H\d+", re.I)
def _infer_ring_from_name(folder: Path) -> Optional[Dict[str, Any]]:
    name = folder.name.lower()
    m = _FORMULA_RE.search(name)
    if not m:
        return None
    try:
        n = int(m.group(1))
    except Exception:
        return None
    H, G = _extract_HG_from_folder(folder)
    if "_ch3" in name or "methyl" in name:
        return {"kind": "methyl", "ring_size": n - 1, "H_total_au": H, "G_total_au": G, "folder": folder}
    return {"kind": "cyclo", "ring_size": n, "H_total_au": H, "G_total_au": G, "folder": folder}

# ===============================================================
# Classification + map builder (patched)
# ===============================================================
def _classify_folder(folder: Path) -> Optional[Dict[str, Any]]:
    xyz = _primary_xyz(folder)
    mol = _load_mol_from_xyz(xyz) if xyz else None
    if mol:
        n = _is_cycloalkane_single_ring(mol)
        if n is not None:
            H, G = _extract_HG_from_folder(folder)
            return {"kind": "cyclo", "ring_size": int(n), "H_total_au": H, "G_total_au": G, "folder": folder}
        m = _is_methylcyclo_single_ring(mol)
        if m is not None:
            H, G = _extract_HG_from_folder(folder)
            return {"kind": "methyl", "ring_size": int(m), "H_total_au": H, "G_total_au": G, "folder": folder}

    # RDKit failed → use fallback
    return _infer_ring_from_name(folder)


def build_structure_energy_maps(root: Path) -> Tuple[Dict[int, Dict[str, Any]], Dict[int, Dict[str, Any]]]:
    root = Path(root)
    cyclo: Dict[int, Dict[str, Any]] = {}
    methyl: Dict[int, Dict[str, Any]] = {}
    try:
        rep_folders = fs.select_unique_by_inchikey(root, prefer_real_freqs=True)
    except Exception:
        rep_folders = fs.iter_child_folders(root)

    for folder in rep_folders:
        info = _classify_folder(folder)
        if not info:
            continue
        rec = {"folder": folder, "H_au": info["H_total_au"], "G_au": info["G_total_au"]}
        if info["kind"] == "cyclo":
            cyclo.setdefault(int(info["ring_size"]), rec)
        elif info["kind"] == "methyl":
            methyl.setdefault(int(info["ring_size"]), rec)

    return cyclo, methyl

def compute_ringstrain_rows(
    root: Path,
    *,
    unit_transfer_constant: float = _HARTREE_TO_KCAL,
    zero_at_n6: bool = True,   # kept for API compatibility; strain is anchored at n=6
    **_ignore,                 # accept future extras without breaking callers
) -> Dict[str, Any]:
    """
    Agent-compatible strain construction (structure-based).

    Step 1: build structure maps (cyclo[n], methyl[m]) and read total H/G (a.u.)
    Step 2: compute adjacent reaction energies (kcal/mol):
            ΔX_n = X[methyl-cyclo(n−1)] − X[cyclo(n)],  X ∈ {H,G}
    Step 3: convert adjacent Δ to *strain* S_n anchored at n=6 via cumulative sums:
            S_6 := 0
            for n > 6:  S_n = S_{n-1} + ΔX_n
            for n < 6:  S_n = S_{n+1} − ΔX_{n+1}

    Returns:
      {
        "delta_rows": [ {ring_size, metric, gt, pred, abs_err, points, reason}, ... ],  # pred = S_n
        "rows_by_ring": { n: {"ring_size": n, "strain_delta_H_kcal_mol": S_n(H), "strain_delta_G_kcal_mol": S_n(G)} },
        "raw": {
            "cyclo": {...}, "methyl": {...},
            "adjacent_reaction": { n: {"dH_kcal": ΔH_n or None, "dG_kcal": ΔG_n or None} }
        }
      }
    """
    root = Path(root)
    cyclo, methyl = build_structure_energy_maps(root)

    # ---------- Adjacent reaction energies (kcal/mol) ----------
    dH_by_n: Dict[int, Optional[float]] = {}
    dG_by_n: Dict[int, Optional[float]] = {}

    # n is valid when cyclo(n) exists and methyl(n-1) exists
    candidate_ns = sorted({(m + 1) for m in methyl.keys()} | set(cyclo.keys()))
    for n in candidate_ns:
        m = n - 1
        dH = dG = None
        if (m in methyl) and (n in cyclo):
            Hm = methyl[m].get("H_au")
            Hc = cyclo[n].get("H_au")
            Gm = methyl[m].get("G_au")
            Gc = cyclo[n].get("G_au")
            if (Hm is not None) and (Hc is not None):
                dH = (Hm - Hc) * unit_transfer_constant
            if (Gm is not None) and (Gc is not None):
                dG = (Gm - Gc) * unit_transfer_constant
        dH_by_n[int(n)] = dH
        dG_by_n[int(n)] = dG

    # ---------- Strain series S_n (anchored at n=6) ----------
    rows_by_ring: Dict[int, Dict[str, Optional[float]]] = {}
    # fixed rubric domain 3–8 (works even if some Δ are missing)
    all_ns = sorted(set(candidate_ns) | {3, 4, 5, 6, 7, 8})

    S_H: Dict[int, Optional[float]] = {6: 0.0}
    S_G: Dict[int, Optional[float]] = {6: 0.0}

    # Upward: n = 7..max,   S_n = S_{n-1} + Δ_n
    for n in sorted([k for k in all_ns if k > 6]):
        prev = n - 1
        dH = dH_by_n.get(n)
        dG = dG_by_n.get(n)
        S_H[n] = (S_H.get(prev) + dH) if (S_H.get(prev) is not None and dH is not None) else None
        S_G[n] = (S_G.get(prev) + dG) if (S_G.get(prev) is not None and dG is not None) else None

    # Downward: n = 5..3,   S_n = S_{n+1} − Δ_{n+1}
    for n in sorted([k for k in all_ns if k < 6], reverse=True):
        nxt = n + 1
        dH = dH_by_n.get(nxt)  # Δ_{n+1}
        dG = dG_by_n.get(nxt)
        S_H[n] = (S_H.get(nxt) - dH) if (S_H.get(nxt) is not None and dH is not None) else None
        S_G[n] = (S_G.get(nxt) - dG) if (S_G.get(nxt) is not None and dG is not None) else None

    # ---------- Package ----------
    for n in all_ns:
        rows_by_ring[int(n)] = {
            "ring_size": int(n),
            "strain_delta_H_kcal_mol": None if S_H.get(n) is None else float(S_H[n]),
            "strain_delta_G_kcal_mol": None if S_G.get(n) is None else float(S_G[n]),
        }

    delta_rows: List[Dict[str, Any]] = []
    for n in sorted(rows_by_ring.keys()):
        rec = rows_by_ring[n]
        # H metric row
        delta_rows.append({
            "ring_size": int(n),
            "metric": "strain_delta_H_kcal_mol",
            "gt": None,
            "pred": None if rec["strain_delta_H_kcal_mol"] is None else round(float(rec["strain_delta_H_kcal_mol"]), 2),
            "abs_err": None,
            "points": 0.0,
            "reason": "missing",
        })
        # G metric row
        delta_rows.append({
            "ring_size": int(n),
            "metric": "strain_delta_G_kcal_mol",
            "gt": None,
            "pred": None if rec["strain_delta_G_kcal_mol"] is None else round(float(rec["strain_delta_G_kcal_mol"]), 2),
            "abs_err": None,
            "points": 0.0,
            "reason": "missing",
        })

    adj = {int(n): {"dH_kcal": dH_by_n.get(n), "dG_kcal": dG_by_n.get(n)} for n in sorted(dH_by_n.keys())}

    return {
        "delta_rows": delta_rows,       # scoring-style list (pred = S_n)
        "rows_by_ring": rows_by_ring,   # convenience: ring-keyed view
        "raw": {
            "cyclo": {int(k): {"folder": str(v["folder"]), "H_au": v["H_au"], "G_au": v["G_au"]}
                      for k, v in cyclo.items()},
            "methyl": {int(k): {"folder": str(v["folder"]), "H_au": v["H_au"], "G_au": v["G_au"]}
                       for k, v in methyl.items()},
            "adjacent_reaction": adj,
        }
    }
