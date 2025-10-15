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


def imaginary_freq_not_exist(text: str) -> bool:
    """True if *no* vibrational frequencies are negative (i.e., no imaginary modes)."""
    freqs, in_block = [], False
    for line in text.splitlines():
        if re.search(r"VIBRATIONAL\s+FREQUENCIES", line, re.I):
            in_block = True
            continue
        if in_block and not line.strip():
            break
        if in_block:
            freqs += [float(n) for n in re.findall(r"[-+]?\d+\.\d+", line)]
    # True only when all freqs >= 0
    return all(f >= 0 for f in freqs) if freqs else True


def check_output_opt(out_text: str) -> dict[str, str]:
    """Convenience wrapper to get OPT/FREQ-specific booleans in one shot."""
    return {
        "Geo opt converged?": "yes" if geo_opt_converged(out_text) else "no",
        "Imag freq not exist?": "yes" if imaginary_freq_not_exist(out_text) else "no",
    }
