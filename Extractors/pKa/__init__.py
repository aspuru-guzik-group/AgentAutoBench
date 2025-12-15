# Extractors/pKa/__init__.py

from .pKa_extract_from_md import (
    Result,
    test_expert,
    extract_pka_from_md,
)

from .extractor_pKa import (
    extract_pka_orca_core,
    extract_pka_orca_core_from_folder,
    parse_gibbs_free_energy,
    imaginary_freq_exist,
    scf_converged,
    opt_converged,
    pick_latest_orca_out,
)

# Optional alias if you prefer a shorter name in callers
extract_pka_core = extract_pka_orca_core  # backwards-friendly alias

__all__ = [
    # MD extractor (LLM-backed)
    "Result",
    "test_expert",
    "extract_pka_from_md",

    # ORCA .out extractor
    "extract_pka_orca_core",
    "extract_pka_orca_core_from_folder",
    "parse_gibbs_free_energy",
    "imaginary_freq_exist",
    "scf_converged",
    "opt_converged",
    "pick_latest_orca_out",

    # alias
    "extract_pka_core",
]
