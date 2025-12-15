from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd

from Auto_benchmark.registry.base import BenchmarkJob
from Auto_benchmark.Grading.Rubrics.Fukui import RUBRIC_FUKUI
from Auto_benchmark.Grading.Scorer.Fukui import score_fukui_case
from Auto_benchmark.Extractors.Fukui import calculate_fukui_indices, extract_fukui_from_md
from Auto_benchmark.io import readers
from Auto_benchmark.Checks.ORCA import (
    input_checks_v2 as ic, 
    output_common as oc, 
    output_opt as oopt, 
    output_fukui as foc
)

class FukuiJob(BenchmarkJob):
    """Benchmark job for Fukui Index calculations."""

    def load_rubric(self) -> Dict[str, Any]:
        """
        Loads the Fukui rubric.

        Returns:
            Dict[str, Any]: The rubric.
        """
        return RUBRIC_FUKUI

    def scan_folders(self) -> List[Path]:
        """
        Fukui uses the root directory as the single 'folder' context.

        Returns:
            List[Path]: A list containing just the root directory.
        """
        return [self.root] 

    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Processes the Fukui calculation set (Anion, Cation, Neutral, OPT).

        Args:
            folder (Path): The root folder.

        Returns:
            Dict[str, Any]: Extracted booleans and ground truth.
        """
        all_files = list(folder.rglob("*"))
        files_map = {
            "OPT": {"inp": None, "out": None},
            "Anion": {"inp": None, "out": None},
            "Neutral": {"inp": None, "out": None},
            "Cation": {"inp": None, "out": None},
        }
        
        # Heuristic assignment of files to roles
        for f in all_files:
            if not f.is_file(): continue
            name = f.name.lower()
            role = None
            if "cation" in name: role = "Cation"
            elif "anion" in name: role = "Anion"
            elif "neutral" in name: role = "OPT" if "opt" in name else "Neutral"
            elif "opt" in name: role = "OPT"
            
            if role:
                if name.endswith(".inp"): files_map[role]["inp"] = f
                elif name.endswith(".out"): files_map[role]["out"] = f

        # Booleans
        bools = {}
        
        # 1. Input Checks (The Standard Trio V2)
        for role in ["OPT", "Anion", "Neutral", "Cation"]:
            inp_path = files_map[role]["inp"]
            
            # Check 1: Input Exists
            bools[f"{role}_input_exist?"] = ic.check_input_exists(inp_path)

            # Prepare for content-based checks
            task_match = "no"
            struct_valid = "no"

            if inp_path and inp_path.exists():
                # Read content safely
                inp_text = readers.read_text_safe(inp_path)
                
                # Check 2: Task Match
                target = "OPT" if role == "OPT" else "SP"
                detected_task = ic.extract_orca_task(inp_text)
                if detected_task == target:
                    task_match = "yes"
                
                # Check 3: Structure Validity (New V2 Check)
                # Pass inp_path.parent to check for external .xyz files
                struct_valid = ic.verify_structure(inp_text, inp_path.parent)

            bools[f"{role}_task_match?"] = task_match
            bools[f"{role}_structure_valid?"] = struct_valid

        # 2. OPT Output Checks
        opt_out = files_map["OPT"]["out"]
        opt_txt = readers.read_text_safe(opt_out) if opt_out else ""
        bools["OPT_SCF_converged?"] = "yes" if oc.scf_converged(opt_txt) else "no"
        bools["OPT_geo_opt_converged?"] = "yes" if oopt.geo_opt_converged(opt_txt) else "no"
        bools["OPT_imag_freq_not_exist?"] = "yes" if oopt.imaginary_freq_not_exist(opt_txt) else "no"

        # 3. SP Output Checks (Neutral, Anion, Cation)
        for role in ["Neutral", "Anion", "Cation"]:
            p = files_map[role]["out"]
            txt = readers.read_text_safe(p) if p else ""
            bools[f"{role}_SCF_converged?"] = "yes" if oc.scf_converged(txt) else "no"
            bools[f"{role}_Mulliken_exist?"] = "yes" if foc.mulliken_exist(txt) else "no"
            bools[f"{role}_Hirshfeld_exist?"] = "yes" if foc.hirshfeld_exist(txt) else "no"
            bools[f"{role}_Loewdin_exist?"] = "yes" if foc.loewdin_exist(txt) else "no"

        # Ground Truth Calculation
        outs = [files_map[r]["out"] for r in ["Anion", "Neutral", "Cation"] if files_map[r]["out"]]
        gt = calculate_fukui_indices(outs)

        return {"Folder": folder.name, "booleans": bools, "ground_truth": gt}

    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        """
        Extracts Fukui results from the report.

        Args:
            report_path (Optional[Path]): The path to the report.

        Returns:
            Dict[str, Any]: Extracted data.
        """
        if not report_path: return {}
        return extract_fukui_from_md(str(report_path))

    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores the Fukui job.

        Args:
            folder_results (List[Dict]): Results (expected length 1).
            agent_data (Dict): Extracted agent data.

        Returns:
            Dict[str, Any]: The score.
        """
        if not folder_results:
            return {"error": "No results processed"}
        
        res = folder_results[0]
        
        score = score_fukui_case(
            booleans=res["booleans"],
            gt_numeric=res["ground_truth"],
            agent_numeric=agent_data,
            rubric=self.rubric
        )
        return score