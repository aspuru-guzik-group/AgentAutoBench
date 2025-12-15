from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd

from Auto_benchmark.registry.base import BenchmarkJob
from Auto_benchmark.Grading.Rubrics.TDDFT import RUBRIC_TDDFT
from Auto_benchmark.Grading.Scorer.TDDFT import score_tddft_case
from Auto_benchmark.Extractors.TDDFT import extract_tddft_core, extract_tddft_from_md
from Auto_benchmark.io import readers, fs
from Auto_benchmark.Checks.ORCA import (
    input_checks as ic, 
    output_common as oc, 
    output_opt as oopt, 
    output_TDDFT as otd
)

class TDDFTJob(BenchmarkJob):
    """Benchmark job for TDDFT calculations."""

    def load_rubric(self) -> Dict[str, Any]:
        """
        Loads the TDDFT rubric.

        Returns:
            Dict[str, Any]: The TDDFT rubric.
        """
        return RUBRIC_TDDFT

    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        """
        Prepares agent data extraction.
        
        TDDFT extraction is context-dependent (per molecule). 
        This method passes the report path so scoring can extract per-folder later.

        Args:
            report_path (Optional[Path]): The path to the report file.

        Returns:
            Dict[str, Any]: A dictionary containing the report path.
        """
        return {"report_path": str(report_path) if report_path else None}

    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Processes a single folder for TDDFT data.

        Args:
            folder (Path): The folder to process.

        Returns:
            Dict[str, Any]: Extracted booleans and ground truth data.
        """
        inps = list(folder.glob("*.inp"))
        primary_out = fs.find_best_out_for_qc(folder)
        
        itexts = [readers.read_text_safe(p) for p in inps]
        otext = readers.read_text_safe(primary_out) if primary_out else ""

        # Booleans
        meth = all(ic.method_exist(t) for t in itexts) if itexts else False
        base = all(ic.basis_exist(t) for t in itexts) if itexts else False
        task = all(ic.tasks_exist(t) for t in itexts) if itexts else False
        chmu = all(ic.charge_mult_exist(t) for t in itexts) if itexts else False
        xyz  = all(ic.xyz_exist(t) for t in itexts) if itexts else False
        
        # New V2 Check (Structure Validity) - Optional addition for robustness
        # struct_valid = all(ic2.verify_structure(t, folder) == "yes" for t in itexts) if itexts else False

        scf = oc.scf_converged(otext) if otext else False
        geo = oopt.geo_opt_converged(otext) if otext else False
        imag_exists = False
        if otext:
            imag_exists = not oopt.imaginary_freq_not_exist(otext)

        tddft_b = otd.tddft_block_executed(otext) if otext else False
        tddft_e = otd.excitation_energy_exist(otext) if otext else False
        tddft_f = otd.oscillator_strengths_available(otext) if otext else False

        bools = {
            "Method exist?": "yes" if meth else "no",
            "Basis set exist?": "yes" if base else "no",
            "Tasks exist?": "yes" if task else "no",
            "Charge & mult exist?": "yes" if chmu else "no",
            "XYZ file exist?": "yes" if xyz else "no",
            "SCF converged?": "yes" if scf else "no",
            "Geo opt converged?": "yes" if geo else "no",
            "Imag freq exist?": "yes" if imag_exists else "no",
            "TDDFT block executed?": "yes" if tddft_b else "no",
            "Excitation energy exist?": "yes" if tddft_e else "no",
            "Oscillator strengths available?": "yes" if tddft_f else "no",
        }

        # GT Extraction
        gt = {}
        if otext and tddft_b:
            gt = extract_tddft_core(otext)

        return {"Folder": folder.name, "booleans": bools, "ground_truth": gt}

    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scores all TDDFT folders independently and calculates the average.

        Args:
            folder_results (List[Dict[str, Any]]): Results from process_folder.
            agent_data (Dict[str, Any]): Data containing the report path.

        Returns:
            Dict[str, Any]: Final aggregated scores.
        """
        report_path_str = agent_data.get("report_path")
        per_folder_scores = []
        total_points = []

        for res in folder_results:
            folder_name = res["Folder"]
            
            # Re-extract for specific molecule (TDDFT specific logic)
            agent_ans = {}
            if report_path_str:
                # Heuristic: pass folder name as molecule hint (e.g. "mol3")
                agent_ans = extract_tddft_from_md(report_path_str, molecule=folder_name)

            bool_df = pd.DataFrame([res["booleans"]])
            score = score_tddft_case(
                booleans=bool_df,
                gt_numeric=res["ground_truth"],
                agent_numeric=agent_ans,
                rubric=self.rubric,
                json_proof=True
            )
            
            per_folder_scores.append({
                "folder": folder_name,
                "score": score
            })
            total_points.append(score["total_points"])

        avg_score = sum(total_points) / len(total_points) if total_points else 0.0
        return {
            "mean_total_points": avg_score,
            "per_folder_details": per_folder_scores
        }