from __future__ import annotations
from pathlib import Path

# -------- File discovery patterns -------- #
INP_GLOB: str = "*.inp"
OUT_GLOB: str = "*.out"

# Exclude these directory names anywhere in the path (case-insensitive)
SKIP_DIRS: set[str] = {"results", "jobinfo", "logs", "reports"}

# Output files to skip by prefix (case-insensitive)
SKIP_OUTFILE_PREFIXES: tuple[str, ...] = ("slurm",)

# Default outputs
DEFAULT_OUTPUT_CSV: str = "auto_benchmark_boolean_report.csv"

# -------- Job detection & priority -------- #
TASK_PRIORITY: list[str] = [
    "FREQ",
    "OPT",
    "SP",
    "TDDFT",
    "CIS",
    "MD",
    "NEB",
    "NMR",
    "EPR",
]

# Composite methods that imply an internal compact basis in ORCA.
COMPOSITE_METHODS: set[str] = {"B97-3C", "R2SCAN-3C", "PBEH-3C", "HF-3C"}