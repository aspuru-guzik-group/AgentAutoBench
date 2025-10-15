"""
Configuration package for auto_bench.


Keep package-level settings and defaults in `defaults.py`. Import from there in
client code as:


from auto_bench.config.defaults import (
INP_GLOB, OUT_GLOB, SKIP_DIRS, SKIP_OUTFILE_PREFIXES,
TASK_PRIORITY, COMPOSITE_METHODS, DEFAULT_OUTPUT_CSV,
)
"""


# Export common names for convenience

from .defaults import ( # noqa: F401
INP_GLOB,
OUT_GLOB,
SKIP_DIRS,
SKIP_OUTFILE_PREFIXES,
TASK_PRIORITY,
COMPOSITE_METHODS,
DEFAULT_OUTPUT_CSV,
)
