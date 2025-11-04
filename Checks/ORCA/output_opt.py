from __future__ import annotations
import re

__all__ = [
    "geo_opt_converged",
    "imaginary_freq_not_exist",
    "check_output_opt",
]


def geo_opt_converged(text: str) -> bool:
    """True if the classic HURRAY / OPTIMIZATION HAS CONVERGED banner is present."""
    return bool(re.search(r"\*+\s*HURRAY\s*\*+.*OPTIMIZATION HAS CONVERGED", text, re.I | re.S))


def imaginary_freq_not_exist(txt: str) -> bool:
    """
    True  → freqs present and all ≥ 0 (no imaginary)
    False → freqs present and at least one < 0 (imaginary)
    If no freqs found, return True (keeps the existing 'literal column' behavior).
    """
    try:
        freqs = fs._extract_freqs(txt)  # handles cm-1 and cm**-1, and searches inside or outside the block
    except Exception:
        freqs = []

    if not freqs:
        return True

    return all(f >= 0.0 for f in freqs)


def check_output_opt(out_text: str) -> dict[str, str]:
    """Convenience wrapper to get OPT/FREQ-specific booleans in one shot."""
    return {
        "Geo opt converged?": "yes" if geo_opt_converged(out_text) else "no",
        "Imag freq not exist?": "yes" if imaginary_freq_not_exist(out_text) else "no",
    }
