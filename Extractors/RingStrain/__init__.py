# Auto_benchmark/Extractors/RingStrain/__init__.py
from __future__ import annotations

# ============================================================
#   RingStrain Extractor Package Initialization
# ============================================================
# Provides:
#   1. ORCA .out parser for total H/G energies (extract_rs_core)
#   2. Structure-based energy map + strain calculator (ringstrain_calc)
#   3. LLM-based extractor from Markdown reports (RS_extractor_from_md)
# ============================================================

# --- 1. ORCA .out core energy extractor ---
from .extractor_RS import extract_rs_core

# --- 2. Structure-based strain calculator ---
from .ringstrain_calc import (
    build_structure_energy_maps,
    compute_ringstrain_rows,
)

# --- 3. Agent / Markdown extractor ---
from .RS_extractor_from_md import extract_ringstrain_from_md

__all__ = [
    # ORCA .out energy parser
    "extract_rs_core",
    # Structure-based mapping + cumulative ΔH/ΔG strain calculator
    "build_structure_energy_maps",
    "compute_ringstrain_rows",
    # Agent Markdown extractor
    "extract_ringstrain_from_md",
]
