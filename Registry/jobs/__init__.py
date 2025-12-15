# Auto_benchmark/registry/jobs/__init__.py
from __future__ import annotations
from .TDDFT import TDDFTJob
from .pKa import PKaJob
from .RingStrain import RingStrainJob
from .Fukui import FukuiJob

# Map friendly names to Job Classes
JOB_MAP = {
    "tddft": TDDFTJob,
    "tddft_sp": TDDFTJob,
    "pka": PKaJob,
    "ringstrain": RingStrainJob,
    "ring_strain": RingStrainJob,
    "fukui": FukuiJob
}
