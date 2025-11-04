"""
Configuration package for auto_bench.

This package centralizes configuration constants, regex patterns, and mappings
used across the auto_bench system. Default values live in `defaults.py`.

Typical usage:

    from auto_bench.config import (
        INP_GLOB, OUT_GLOB, SKIP_DIRS, SKIP_OUTFILE_PREFIXES,
        TASK_PRIORITY, COMPOSITE_METHODS, DEFAULT_OUTPUT_CSV,
    )

If you need more advanced configuration, import directly from
`auto_bench.config.defaults`.
"""

from __future__ import annotations

# Re-export commonly used names for convenience
from .defaults import (  # noqa: F401
    INP_GLOB,
    OUT_GLOB,
    SKIP_DIRS,
    SKIP_OUTFILE_PREFIXES,
    TASK_PRIORITY,
    COMPOSITE_METHODS,
    DEFAULT_OUTPUT_CSV,
)

# Optionally expose other useful constants or regexes if frequently used elsewhere
from .defaults import (  # noqa: F401
    HARTREE_TO_KCAL,
    RINGNUM_RE,
    METHYL_RE,
    ME_TOKEN,
    RINGNAME_MAP,
    RE_FREQ_BLOCK,
    RE_FREQ_VAL,
    YES_VALUES,
    NO_VALUES,
    NUM,
)

__all__ = [
    # file patterns
    "INP_GLOB", "OUT_GLOB",
    "SKIP_DIRS", "SKIP_OUTFILE_PREFIXES",
    # task priority & methods
    "TASK_PRIORITY", "COMPOSITE_METHODS",
    # outputs
    "DEFAULT_OUTPUT_CSV",
    # energy & regex patterns
    "HARTREE_TO_KCAL", "RINGNUM_RE", "METHYL_RE", "ME_TOKEN",
    "RINGNAME_MAP", "RE_FREQ_BLOCK", "RE_FREQ_VAL",
    "YES_VALUES", "NO_VALUES", "NUM",
]

