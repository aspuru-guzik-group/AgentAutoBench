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
    iter_child_folders,
    folder_has_real_freqs,
    inchikey_from_smiles,
    inchikey_from_xyz,
    build_structure_index,
    select_unique_by_inchikey,
    has_non_slurm_out,
)

from .readers import read_text_safe

__all__ = [
    # Submodules
    "fs",
    "readers",
    # fs helpers
    "iter_child_folders",
    "folder_has_real_freqs",
    "inchikey_from_smiles",
    "inchikey_from_xyz",
    "build_structure_index",
    "select_unique_by_inchikey",
    "has_non_slurm_out",
    # readers helpers
    "read_text_safe",
]
