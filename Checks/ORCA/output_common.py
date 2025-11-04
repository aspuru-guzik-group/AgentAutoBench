from __future__ import annotations
import re

__all__ = [
    "scf_converged",
]

def scf_converged(text: str) -> bool:
    """True if the output contains 'SCF converged' (case-insensitive)."""
    return bool(re.search(r"SCF converged", text, re.I))
