from __future__ import annotations
import os
from pathlib import Path
from typing import Iterator

from Auto_benchmark.config.defaults import (
    INP_GLOB,
    OUT_GLOB,
    SKIP_DIRS,
    SKIP_OUTFILE_PREFIXES,
)

def _not_forbidden(p: Path) -> bool:
    """True if no path component is in SKIP_DIRS (case-insensitive)."""
    return not any(part.lower() in SKIP_DIRS for part in p.parts)

def walk_job_folders(root: Path | str) -> Iterator[Path]:
    """Yield immediate subdirectories of *root* that are candidate job folders."""
    root = Path(root)
    for child in sorted(root.iterdir()):
        if child.is_dir() and _not_forbidden(child):
            yield child

def _collect_by_stem(folder: Path) -> tuple[dict[str, list[Path]], dict[str, list[Path]]]:
    """Collect inputs and outputs under *folder* (recursively) keyed by stem."""
    inps: dict[str, list[Path]] = {}
    outs: dict[str, list[Path]] = {}

    for p in folder.rglob(INP_GLOB):
        if _not_forbidden(p):
            inps.setdefault(p.stem, []).append(p)

    for p in folder.rglob(OUT_GLOB):
        if _not_forbidden(p):
            if p.name.lower().startswith(SKIP_OUTFILE_PREFIXES):
                continue
            outs.setdefault(p.stem, []).append(p)

    return inps, outs

def _pick_output_for_input(inp_path: Path, outs_for_stem: list[Path]) -> Path | None:
    """Prefer an output in the same directory as *inp_path*; else newest by mtime."""
    if not outs_for_stem:
        return None
    same_dir = [op for op in outs_for_stem if op.parent == inp_path.parent]
    if same_dir:
        return max(same_dir, key=lambda x: os.path.getmtime(x))
    return max(outs_for_stem, key=lambda x: os.path.getmtime(x))

def map_pairs_in_folder(folder: Path) -> list[tuple[Path, Path, str]]:
    """Return list of (inp_path, out_path, stem) for stems that have both files.

    - Pairs by identical stem: `foo.inp` ↔ `foo.out`.
    - Recurses within *folder* using glob patterns from config.
    - Skips forbidden directories and excluded output prefixes (e.g., slurm).
    - If multiple outputs exist, prefer same-dir as input, else newest by mtime.
    """
    inps, outs = _collect_by_stem(folder)

    pairs: list[tuple[Path, Path, str]] = []
    for stem in sorted(set(inps) & set(outs)):
        # choose one (inp, out) per stem; if multiple inputs exist, pick deterministically
        for ip in sorted(inps[stem], key=lambda x: (x.parent.as_posix(), x.as_posix())):
            op = _pick_output_for_input(ip, outs[stem])
            if op is None:
                continue
            pairs.append((ip, op, stem))
            break

    return pairs