# Auto_benchmark/registry/jobs/__init__.py
from __future__ import annotations
from typing import Dict, Any

# import per-case job specs (each defines a JOB dict)
from .TDDFT import JOB as _JOB_TDDFT
from .pKa import JOB as _JOB_PKA
from .RingStrain import JOB as _JOB_RINGSTRAIN

# central registry
_JOBS: Dict[str, Dict[str, Any]] = {
    "tddft": _JOB_TDDFT,
    "tddft_sp": _JOB_TDDFT,       # alias
    "pka": _JOB_PKA,
    "ringstrain": _JOB_RINGSTRAIN,
    "ring_strain": _JOB_RINGSTRAIN,  # optional alias for convenience
}

def get_job(job_type: str) -> Dict[str, Any]:
    key = (job_type or "").strip().lower()
    if key not in _JOBS:
        available = ", ".join(sorted(_JOBS.keys()))
        raise KeyError(f"Unknown job '{job_type}'. Available: {available}")
    return _JOBS[key]

