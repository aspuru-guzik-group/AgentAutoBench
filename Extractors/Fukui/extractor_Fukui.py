# Auto_benchmark/Extractors/Fukui/extractor_Fukui.py
from __future__ import annotations
import re
from typing import Dict, Optional

__all__ = ["extract_fukui_charges"]

# -----------------------------------------------------------------------------
# Regex Patterns
# -----------------------------------------------------------------------------

# 1. Mulliken
# Header: MULLIKEN ATOMIC CHARGES AND SPIN POPULATIONS
# Format: "   0 C :   -0.334850    0.001531"
RE_MULLIKEN_BLOCK = re.compile(r"MULLIKEN\s+ATOMIC\s+CHARGES", re.IGNORECASE)
# Captures: Group 1 (Index), Group 2 (Element), Group 3 (Charge)
RE_MULLIKEN_LINE = re.compile(r"^\s*(\d+)\s+([A-Z][a-z]?)\s*:\s*([-+]?\d+\.\d+)", re.IGNORECASE)

# 2. Hirshfeld
# Header: HIRSHFELD ANALYSIS
# Format: "   0 C   -0.029551    0.039617"
RE_HIRSHFELD_BLOCK = re.compile(r"HIRSHFELD\s+ANALYSIS", re.IGNORECASE)
# Captures: Group 1 (Index), Group 2 (Element), Group 3 (Charge)
RE_HIRSHFELD_LINE = re.compile(r"^\s*(\d+)\s+([A-Z][a-z]?)\s+([-+]?\d+\.\d+)", re.IGNORECASE)

# 3. Loewdin
# Header: LOEWDIN ATOMIC CHARGES AND SPIN POPULATIONS
# Format: "   0 C :   -0.192525    0.043461"
RE_LOEWDIN_BLOCK = re.compile(r"LOEWDIN\s+ATOMIC\s+CHARGES", re.IGNORECASE)
# Captures: Group 1 (Index), Group 2 (Element), Group 3 (Charge)
RE_LOEWDIN_LINE = re.compile(r"^\s*(\d+)\s+([A-Z][a-z]?)\s*:\s*([-+]?\d+\.\d+)", re.IGNORECASE)


def _extract_block_charges(
    lines: list[str], 
    start_idx: int, 
    line_regex: re.Pattern, 
    target_indices: set[int]
) -> Dict[int, float]:
    """
    Helper to iterate lines starting from a header and extract charges for specific atoms.
    Stops when it hits a line that doesn't match the atom format or is empty/dashed.
    """
    charges = {}
    # ORCA usually has a few header lines (dashes etc) before data. 
    # We'll search forward a bit to find the first atom line.
    
    # Simple state machine: scan until we find data, keep reading until we don't.
    found_data = False
    
    # Look ahead up to 100 lines (plenty for header skips)
    for i in range(start_idx + 1, min(start_idx + 100, len(lines))):
        line = lines[i].strip()
        if not line:
            if found_data: break # End of block
            continue
        
        # Check for divider lines like "---------"
        if set(line) == {'-'}:
            continue

        m = line_regex.search(line)
        if m:
            found_data = True
            idx = int(m.group(1))
            
            # Optimization: only store what we need (Carbons 0-6)
            if idx in target_indices:
                try:
                    val = float(m.group(3))
                    charges[idx] = val
                except ValueError:
                    pass
        else:
            # If we were reading data and hit a non-matching line, stop
            if found_data:
                break
                
    return charges


def extract_fukui_charges(text: str) -> Dict[str, Dict[int, float]]:
    """
    Extracts atomic partial charges for Carbon atoms (indices 0-6) 
    using Mulliken, Hirshfeld, and Loewdin schemes.

    Args:
        text (str): Content of an ORCA output file.

    Returns:
        Dict with keys 'mulliken', 'hirshfeld', 'loewdin'.
        Each value is a Dict[int, float] mapping Atom Index -> Charge.
        Example:
        {
            'mulliken': {0: -0.334, 1: 0.203, ...},
            ...
        }
    """
    lines = text.splitlines()
    results = {
        "mulliken": {},
        "hirshfeld": {},
        "loewdin": {}
    }
    
    # We specifically want the 7 carbons of Toluene (indices 0 to 6)
    target_atom_indices = {0, 1, 2, 3, 4, 5, 6}

    for i, line in enumerate(lines):
        # Check headers
        if RE_MULLIKEN_BLOCK.search(line):
            # Only parse if we haven't found it yet (or take the last one found)
            data = _extract_block_charges(lines, i, RE_MULLIKEN_LINE, target_atom_indices)
            if data: results["mulliken"] = data
            
        elif RE_HIRSHFELD_BLOCK.search(line):
            data = _extract_block_charges(lines, i, RE_HIRSHFELD_LINE, target_atom_indices)
            if data: results["hirshfeld"] = data
            
        elif RE_LOEWDIN_BLOCK.search(line):
            data = _extract_block_charges(lines, i, RE_LOEWDIN_LINE, target_atom_indices)
            if data: results["loewdin"] = data

    return results