# Auto_benchmark/registry/jobs/Fukui.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path

from Auto_benchmark.registry.base import BenchmarkJob
from Auto_benchmark.Grading.Rubrics.Fukui import RUBRIC_FUKUI
from Auto_benchmark.Grading.Scorer.Fukui import score_fukui_case
from Auto_benchmark.Extractors.Fukui.Fukui_calc import calculate_fukui_indices
from Auto_benchmark.Extractors.Fukui.Fukui_extract_from_md import extract_fukui_from_md
from Auto_benchmark.io import readers
from Auto_benchmark.Checks.ORCA import (
    input_checks_v2 as input_checks, 
    output_common as output_checks, 
    output_opt as opt_output_checks, 
    output_fukui as fukui_output_checks
)

class FukuiJob(BenchmarkJob):
    """Benchmark job for Fukui Index calculations."""

    def load_rubric(self) -> Dict[str, Any]:
        return RUBRIC_FUKUI

    def scan_folders(self) -> List[Path]:
        # Fukui typically treats the entire root as one calculation context
        return [self.root] 

    def _identify_files(self, folder: Path) -> Dict[str, Dict[str, Optional[Path]]]:
        """Helper to map files to roles (OPT, Anion, Neutral, Cation)."""
        all_files = list(folder.rglob("*"))
        files_map = {
            "OPT": {"inp": None, "out": None},
            "Anion": {"inp": None, "out": None},
            "Neutral": {"inp": None, "out": None},
            "Cation": {"inp": None, "out": None},
        }
        
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
        return files_map

    def check_inputs(self, context: Dict[str, Any]) -> Dict[str, str]:
        files_map = context
        bools = {}
        for role in ["OPT", "Anion", "Neutral", "Cation"]:
            inp_path = files_map[role]["inp"]
            
            # Check 1: Input Exists
            # input_checks.check_input_exists returns bool -> convert to "yes"/"no"
            exists = input_checks.check_input_exists(inp_path)
            bools[f"{role}_input_exist?"] = "yes" if exists else "no"

            task_match = "no"
            struct_valid = "no"

            if exists:
                # Safe to read because exists check passed
                inp_text = readers.read_text_safe(inp_path)
                
                # Check 2: Task Match
                # Target depends on role: "OPT" for OPT, "SP" for others.
                target_task = "OPT" if role == "OPT" else "SP"
                
                # input_checks.check_orca_task returns bool -> update flag if True
                if input_checks.check_orca_task(inp_text, target_task):
                    task_match = "yes"
                
                # Check 3: Structure Validity
                # input_checks.verify_structure returns "yes"/"no" string directly
                struct_valid = input_checks.verify_structure(inp_text, inp_path.parent)

            bools[f"{role}_task_match?"] = task_match
            bools[f"{role}_structure_valid?"] = struct_valid
        return bools

    def check_outputs(self, context: Dict[str, Any]) -> Dict[str, str]:
        files_map = context
        bools = {}
        
        # 1. OPT Output Checks
        opt_out = files_map["OPT"]["out"]
        opt_txt = readers.read_text_safe(opt_out) if opt_out else ""
        bools["OPT_SCF_converged?"] = "yes" if output_checks.scf_converged(opt_txt) else "no"
        bools["OPT_geo_opt_converged?"] = "yes" if opt_output_checks.geo_opt_converged(opt_txt) else "no"
        bools["OPT_imag_freq_not_exist?"] = "yes" if opt_output_checks.imaginary_freq_not_exist(opt_txt) else "no"

        # 2. SP Output Checks (Neutral, Anion, Cation)
        for role in ["Neutral", "Anion", "Cation"]:
            p = files_map[role]["out"]
            txt = readers.read_text_safe(p) if p else ""
            bools[f"{role}_SCF_converged?"] = "yes" if output_checks.scf_converged(txt) else "no"
            bools[f"{role}_Mulliken_exist?"] = "yes" if fukui_output_checks.mulliken_exist(txt) else "no"
            bools[f"{role}_Hirshfeld_exist?"] = "yes" if fukui_output_checks.hirshfeld_exist(txt) else "no"
            bools[f"{role}_Loewdin_exist?"] = "yes" if fukui_output_checks.loewdin_exist(txt) else "no"
            
        return bools

    def calculate_ground_truth(self, context: Dict[str, Any]) -> Dict[str, Any]:
        files_map = context
        outs = [files_map[r]["out"] for r in ["Anion", "Neutral", "Cation"] if files_map[r]["out"]]
        return calculate_fukui_indices(outs)

    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Orchestrates the processing of a single folder.
        """
        # 1. Identify files
        files_map = self._identify_files(folder)

        # 2. Run separated checks
        inputs_res = self.check_inputs(files_map)
        outputs_res = self.check_outputs(files_map)
        gt_res = self.calculate_ground_truth(files_map)

        return {
            "Folder": folder.name, 
            "booleans": {**inputs_res, **outputs_res}, 
            "ground_truth": gt_res
        }

    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        if not report_path: return {}
        return extract_fukui_from_md(str(report_path))

    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
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

    def run(self) -> Dict[str, Any]:
        folders = self.scan_folders()
        
        folder_results = []
        for folder in folders:
            folder_results.append(self.process_folder(folder))
            
        report_path = self.find_report()
        agent_data = self.extract_agent_data(report_path)
        
        return self.score_all(folder_results, agent_data)
