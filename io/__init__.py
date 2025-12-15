# Auto_benchmark/io/__init__.py
"""
Auto_benchmark.io
-----------------
Generalized I/O and filesystem utilities shared across modules.

Exports:
    - fs: structure and file utilities (RDKit-based)
    - readers: safe file reading utilities
"""

from __future__ import annotations

# Public submodules
from . import fs
from . import readers

# Re-export commonly used helpers for convenience
from .fs import (
    _extract_freqs,
    _read_primary_out,
    find_best_out_for_qc,
    folder_has_real_freqs,
    has_non_slurm_out,
    inchikey_from_smiles,
    inchikey_from_xyz,
    _pick_primary_xyz,
    iter_child_folders,
    select_unique_by_inchikey,
)

from .readers import read_text_safe

__all__ = [
    # Submodules
    "fs",
    "readers",
    # fs helpers
    "_extract_freqs",
    "_read_primary_out",
    "find_best_out_for_qc",
    "folder_has_real_freqs",
    "has_non_slurm_out",
    "inchikey_from_smiles",
    "inchikey_from_xyz",
    "_pick_primary_xyz",
    "iter_child_folders", 
    "select_unique_by_inchikey",
    # readers helpers
    "read_text_safe",
]
