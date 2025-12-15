# Auto_benchmark/Extractors/Fukui/Fukui_extract_from_md.py
from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional, List, Any
import re

from pydantic import BaseModel, Field
from ElAgente.Agent import StructureOutputAgent

# -------------------------------------------------------------------------
# Pydantic Schema for LLM Extraction
# -------------------------------------------------------------------------

class FukuiRow(BaseModel):
    """
    Represents a single row of data for an atom in a Fukui index table.
    """
    atom_index: int = Field(..., description="The numeric index of the carbon atom (e.g., 0 for C0, 1 for C1).")
    mulliken: float = Field(..., description="The value under the Mulliken column.")
    hirshfeld: float = Field(..., description="The value under the Hirshfeld column.")
    loewdin: float = Field(..., description="The value under the Loewdin column.")

class FukuiResult(BaseModel):
    """
    Schema for extracting condensed Fukui function tables from the report.
    """
    f_plus_rows: List[FukuiRow] = Field(
        ..., 
        description="Rows extracted from the f+ (Nucleophilic Attack) table."
    )
    f_minus_rows: List[FukuiRow] = Field(
        ..., 
        description="Rows extracted from the f- (Electrophilic Attack) table."
    )

# -------------------------------------------------------------------------
# LLM Interaction
# -------------------------------------------------------------------------

def _run_llm_extraction(text: str) -> Dict[str, Any]:
    """
    Uses the StructureOutputAgent to parse the markdown text into the FukuiResult schema.
    """
    agent = StructureOutputAgent(model="gpt-4o", agent_schema=FukuiResult)
    
    system_messages = [
        "You are a precise scientific parsing agent.",
        "You will be given a Markdown report containing Condensed Fukui Indices analysis.",
        "Your task is to extract the numerical values for f+ (Nucleophilic) and f- (Electrophilic) indices.",
        "There are two main tables: one for f+ and one for f-.",
        "Each row corresponds to an atom (C0, C1, etc.). Extract the Atom Index (integer) and the values for Mulliken, Hirshfeld, and Loewdin schemes.",
        "Ensure you extract data for all carbon atoms listed (C0 to C6)."
    ]
    
    for msg in system_messages:
        agent.append_system_message(msg)

    # Prompt with the context
    prompt = f"Extract the Fukui indices tables from the following report:\n\n{text}"
    
    try:
        result = agent.stream_return_graph_state(prompt)
        agent.clear_memory()
        return result.get("structure_output", {})
    except Exception as e:
        print(f"LLM Extraction failed: {e}")
        return {}

# -------------------------------------------------------------------------
# Logic / Formatting
# -------------------------------------------------------------------------

def _organize_data(llm_output: Dict[str, Any]) -> Dict[str, List[float]]:
    """
    Converts the row-based LLM output into the column-based dictionary of lists 
    expected by the scoring system (sorted by atom index 0-6).
    
    Expected keys in return:
      'f_plus_Mulliken', 'f_plus_Hirshfeld', 'f_plus_Loewdin',
      'f_minus_Mulliken', 'f_minus_Hirshfeld', 'f_minus_Loewdin'
    """
    # containers for sorting
    # f_plus_map: {atom_idx: {'mulliken': val, ...}}
    f_plus_map = {}
    f_minus_map = {}

    # Helper to parse rows
    def parse_rows(rows_data, target_map):
        if not rows_data:
            return
        for r in rows_data:
            # Pydantic model might be returned as dict or object depending on agent implementation
            # usually dict in 'structure_output'
            idx = r.get("atom_index")
            if idx is not None:
                target_map[int(idx)] = {
                    "mulliken": r.get("mulliken"),
                    "hirshfeld": r.get("hirshfeld"),
                    "loewdin": r.get("loewdin")
                }

    parse_rows(llm_output.get("f_plus_rows", []), f_plus_map)
    parse_rows(llm_output.get("f_minus_rows", []), f_minus_map)

    # Prepare final sorted lists (Indices 0 to 6)
    # If a value is missing for an index, we put None (or 0.0, but None is safer for scoring check)
    target_indices = range(7) # 0..6
    
    output = {
        "f_plus_Mulliken": [], "f_plus_Hirshfeld": [], "f_plus_Loewdin": [],
        "f_minus_Mulliken": [], "f_minus_Hirshfeld": [], "f_minus_Loewdin": []
    }

    for i in target_indices:
        # f+
        row = f_plus_map.get(i, {})
        output["f_plus_Mulliken"].append(row.get("mulliken"))
        output["f_plus_Hirshfeld"].append(row.get("hirshfeld"))
        output["f_plus_Loewdin"].append(row.get("loewdin"))
        
        # f-
        row = f_minus_map.get(i, {})
        output["f_minus_Mulliken"].append(row.get("mulliken"))
        output["f_minus_Hirshfeld"].append(row.get("hirshfeld"))
        output["f_minus_Loewdin"].append(row.get("loewdin"))

    return output

# -------------------------------------------------------------------------
# Public API
# -------------------------------------------------------------------------

def extract_fukui_from_md(md_path: str) -> Dict[str, List[float]]:
    """
    Read a Fukui Markdown report and return dictionaries of values sorted by atom index.
    
    Returns:
      {
        "f_plus_Mulliken": [v_c0, v_c1, ... v_c6],
        "f_plus_Hirshfeld": [...],
        ...
      }
    """
    try:
        md_text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
    except Exception:
        # Return empty structure with Nones if file read fails
        return {
            k: [None]*7 for k in [
                "f_plus_Mulliken", "f_plus_Hirshfeld", "f_plus_Loewdin",
                "f_minus_Mulliken", "f_minus_Hirshfeld", "f_minus_Loewdin"
            ]
        }

    # 1. Run LLM Extraction
    llm_data = _run_llm_extraction(md_text)
    
    # 2. Reformat to column vectors sorted by atom index
    structured_data = _organize_data(llm_data)
    
    return structured_data