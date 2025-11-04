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

# --- energy conversion ---
HARTREE_TO_KCAL = 627.5094740631

# --- regex patterns ---
RINGNUM_RE = re.compile(r"(?<!\d)(\d+)(?!\d)")
# tolerate 'methyl' prefix inside compound tokens
METHYL_RE = re.compile(r"(?i)methyl")
# token-only variant (avoid matching 'metal')
ME_TOKEN  = re.compile(r"(?i)\bme\b")

# --- mapping of name → ring size ---
RINGNAME_MAP = {
    "cyclopropane": 3,
    "cyclobutane": 4,
    "cyclopentane": 5,
    "cyclohexane": 6,
    "cycloheptane": 7,
    "cyclooctane": 8,
    # tolerate truncated variants (e.g. 'cyclohexan')
    "cyclopropan": 3,
    "cyclobutan": 4,
    "cyclopentan": 5,
    "cyclohexan": 6,
    "cycloheptan": 7,
    "cyclooctan": 8,
}

RE_FREQ_BLOCK = re.compile(r"VIBRATIONAL\s+FREQUENCIES", re.I)
RE_FREQ_VAL   = re.compile(r"([+-]?\d+\.\d+)\s*cm(?:\*\*\-?1|\-1)")

YES_VALUES = {"yes", "y", "true", "1", "t"}
NO_VALUES  = {"no", "n", "false", "0", "f"}

NUM = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")
