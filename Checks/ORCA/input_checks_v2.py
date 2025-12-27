from __future__ import annotations
import re
from pathlib import Path
from typing import Optional, Union, List

def check_input_exists(filepath: Optional[Path]) -> bool:
    """
    Simple check if the input file exists.
    
    Args:
        filepath (Optional[Path]): The path to the input file.
        
    Returns:
        bool: True if file exists, False otherwise.
    """
    return filepath is not None and filepath.exists()

def check_orca_task(input_text: str, task_to_check: Union[str, List[str]]) -> bool:
    """
    Checks if a specific task keyword (e.g., 'OPT', 'FREQ') exists in the ORCA input method line.
    
    Args:
        input_text (str): The content of the input file.
        task_to_check (str | List[str]): The task keyword(s) to look for. 
                                         If a list is provided, returns True if ANY of them are found.
        
    Returns:
        bool: True if the specified task is found, False otherwise.
    """
    if isinstance(task_to_check, str):
        target_keywords = {task_to_check.lower()}
    else:
        target_keywords = {t.lower() for t in task_to_check}
    
    keyword_lines = re.findall(r"^!\s*(.+)", input_text, re.MULTILINE)
    
    for line in keyword_lines:
        lower_line = line.lower()
        
        for target in target_keywords:
            if target in lower_line:
                return True
            
    return False

def verify_structure(input_text: str, folder_path: Path) -> str:
    """
    Verifies that the chemical structure definition in the input is valid.
    
    Checks for two cases:
    1. External File: `* xyzfile charge mult filename.xyz`
       - Returns "yes" ONLY if 'filename.xyz' exists in 'folder_path'.
    2. Inline Coordinates: `* xyz charge mult ... *`
       - Returns "yes" if the block contains data.
       
    Args:
        input_text (str): The content of the input file.
        folder_path (Path): The folder containing the input file (to check for external xyz).
        
    Returns:
        str: "yes" if valid, "no" if invalid or missing.
    """
    # 1. Check for External File Reference
    # Pattern: * xyzfile charge mult filename
    # Example: * xyzfile 0 1 benzene.xyz
    file_match = re.search(r"\*\s*xyzfile\s+[-+]?\d+\s+[-+]?\d+\s+(['\"]?)([^\"'\s]+)\1", input_text, re.IGNORECASE)
    
    if file_match:
        filename = file_match.group(2)
        # Check specific file
        if (folder_path / filename).exists():
            return "yes"
        # Common agent error: referencing file without extension, or wrong extension case
        # Try finding it with .xyz appended if not present
        if not filename.lower().endswith(".xyz"):
            if (folder_path / f"{filename}.xyz").exists():
                return "yes"
        return "no" # Referenced file does not exist

    # 2. Check for Inline Coordinates
    # Pattern: * xyz charge mult ... [coordinates] ... *
    # We look for the opening block and ensure it's not empty
    inline_match = re.search(r"\*\s*xyz\s+[-+]?\d+\s+[-+]?\d+\s+([\s\S]+?)\*", input_text, re.IGNORECASE)
    
    if inline_match:
        content = inline_match.group(1).strip()
        # Basic validation: are there lines?
        if len(content.splitlines()) > 0:
            return "yes"
            
    # 3. Check for Internal Coordinates (rare but possible: * int)
    int_match = re.search(r"\*\s*int\s+[-+]?\d+\s+[-+]?\d+\s+([\s\S]+?)\*", input_text, re.IGNORECASE)
    if int_match:
        return "yes"

    # If no valid structure block found
    return "no"
