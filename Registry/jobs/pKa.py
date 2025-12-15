from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd

from Auto_benchmark.registry.base import BenchmarkJob
from Auto_benchmark.Grading.Rubrics.pKa import RUBRIC_PKA
from Auto_benchmark.Grading.Scorer.pKa import score_pka_case
from Auto_benchmark.Extractors.pKa import extract_pka_orca_core, extract_pka_from_md
from Auto_benchmark.io import readers, fs
from Auto_benchmark.Checks.ORCA import (
    input_checks as ic, 
    output_common as oc, 
    output_opt as oopt, 
    output_pKa as o_pka
)

class PKaJob(BenchmarkJob):
    """Benchmark job for pKa calculations."""

    def load_rubric(self) -> Dict[str, Any]:
        """
        Loads the pKa rubric.

        Returns:
            Dict[str, Any]: The pKa rubric.
        """
        return RUBRIC_PKA

    def scan_folders(self) -> List[Path]:
        """
        Scans for valid pKa folders, excluding 'proton' reference folders.

        Returns:
            List[Path]: A list of valid folder paths.
        """
        all_folders = fs.iter_child_folders(self.root)
        valid = []
        for f in all_folders:
            if fs.has_non_slurm_out(f) and not self._is_proton_folder(f):
                valid.append(f)
        return valid

    def _is_proton_folder(self, folder: Path) -> bool:
        """
        Determines if a folder represents a single proton calculation.

        Args:
            folder (Path): The folder to check.

        Returns:
            bool: True if it is a proton folder, False otherwise.
        """
        if "proton" in folder.name.lower(): return True
        # Check XYZ
        for xyz in folder.glob("*.xyz"):
            try:
                lines = xyz.read_text(errors="ignore").splitlines()
                lines = [l for l in lines if l.strip()]
                if not lines: continue
                # simple parser: first line num atoms, then atoms
                if len(lines) > 2 and lines[0].strip() == "1":
                    atom_line = lines[2].split()
                    if atom_line and atom_line[0].upper() == "H":
                        return True
            except Exception: pass
        return False

    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Processes a single folder for pKa booleans.

        Args:
            folder (Path): The folder to process.

        Returns:
            Dict[str, Any]: Extracted boolean checks.
        """
        inps = list(folder.glob("*.inp"))
        outp = fs.find_best_out_for_qc(folder)
        itexts = [readers.read_text_safe(p) for p in inps]
        otext = readers.read_text_safe(outp) if outp else ""

        # Booleans
        meth = all(ic.method_exist(t) for t in itexts) if itexts else False
        base = all(ic.basis_exist(t) for t in itexts) if itexts else False
        task = all(ic.tasks_exist(t) for t in itexts) if itexts else False
        chmu = all(ic.charge_mult_exist(t) for t in itexts) if itexts else False
        xyz  = all(ic.xyz_exist(t) for t in itexts) if itexts else False
        
        scf = oc.scf_converged(otext) if otext else False
        geo = oopt.geo_opt_converged(otext) if otext else False
        imag_exists = (not oopt.imaginary_freq_not_exist(otext)) if otext else False
        dg_exists = o_pka.deltaG_exists(otext) if otext else False

        bools = {
            "Method exist?": "yes" if meth else "no",
            "Basis set exist?": "yes" if base else "no",
            "Tasks exist?": "yes" if task else "no",
            "Charge & mult exist?": "yes" if chmu else "no",
            "XYZ file exist?": "yes" if xyz else "no",
            "SCF converged?": "yes" if scf else "no",
            "Geo opt converged?": "yes" if geo else "no",
            "Imag freq exist?": "yes" if imag_exists else "no",
            "deltaG_exist": "yes" if dg_exists else "no"
        }
        
        return {"Folder": folder.name, "booleans": bools}

    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        """
        Extracts pKa results from the agent's report.

        Args:
            report_path (Optional[Path]): The path to the report.

        Returns:
            Dict[str, Any]: The extracted data.
        """
        if not report_path: return {}
        return extract_pka_from_md(str(report_path))

    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregates booleans and scores the pKa prediction.

        Args:
            folder_results (List[Dict]): Per-folder booleans.
            agent_data (Dict): Extracted agent pKa value.

        Returns:
            Dict[str, Any]: The final score.
        """
        s1_rows = []
        deltag_items = []
        
        for res in folder_results:
            b = res["booleans"]
            # Section 1 rows (exclude deltaG)
            s1_row = {k: v for k, v in b.items() if k != "deltaG_exist"}
            s1_rows.append(s1_row)
            # Section 2 items
            deltag_items.append(b.get("deltaG_exist"))

        return score_pka_case(
            section1_rows=s1_rows,
            section2_deltag_items=deltag_items,
            md_extraction=agent_data
        )
