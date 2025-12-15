# Auto_benchmark/Checks/ORCA/fukui_output.py
from __future__ import annotations
import re

__all__ = [
    "mulliken_exist",
    "hirshfeld_exist",
    "loewdin_exist",
]

def mulliken_exist(text: str) -> bool:
    """
    Checks if Mulliken Population Analysis was performed.
    
    Reference in example file:
    * MULLIKEN POPULATION ANALYSIS *
    """
    return bool(re.search(r"\*\s*MULLIKEN\s+POPULATION\s+ANALYSIS\s*\*", text, re.IGNORECASE))


def hirshfeld_exist(text: str) -> bool:
    """
    Checks if Hirshfeld Analysis was performed.
    
    Reference in example file:
    HIRSHFELD ANALYSIS
    """
    return bool(re.search(r"HIRSHFELD\s+ANALYSIS", text, re.IGNORECASE))


def loewdin_exist(text: str) -> bool:
    """
    Checks if Loewdin Population Analysis was performed.
    
    Reference in example file:
    * LOEWDIN POPULATION ANALYSIS *
    """
    return bool(re.search(r"\*\s*LOEWDIN\s+POPULATION\s+ANALYSIS\s*\*", text, re.IGNORECASE))
