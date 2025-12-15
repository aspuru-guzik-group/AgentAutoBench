"""
Registry package initialization.

Exposes the Base Benchmark Class and the Job Registry Map.
"""
from .base import BenchmarkJob
from .jobs import JOB_MAP

__all__ = ["BenchmarkJob", "JOB_MAP"]
