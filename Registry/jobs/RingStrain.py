from __future__ import annotations
from typing import Dict, Any, List, Optional
from pathlib import Path
import pandas as pd
import os

from Auto_benchmark.registry.base import BenchmarkJob
from Auto_benchmark.Grading.Rubrics.RingStrain import RUBRIC_RINGSTRAIN
from Auto_benchmark.Grading.Scorer.RingStrain import score_ringstrain
from Auto_benchmark.Extractors.RingStrain import extract_rs_core, extract_ringstrain_from_md, ringstrain_calc
from Auto_benchmark.io import readers, fs
from Auto_benchmark.Checks.ORCA import input_checks as ic, output_common as oc, output_opt as oopt
from Auto_benchmark.Config.defaults import HARTREE_TO_KCAL

class RingStrainJob(BenchmarkJob):
    """Benchmark job for Ring Strain calculations."""

    def load_rubric(self) -> Dict[str, Any]:
        """
        Loads the Ring Strain rubric.

        Returns:
            Dict[str, Any]: The rubric.
        """
        return RUBRIC_RINGSTRAIN

    def process_folder(self, folder: Path) -> Dict[str, Any]:
        """
        Processes a single folder to extract energies and booleans.

        Args:
            folder (Path): The folder to process.

        Returns:
            Dict[str, Any]: Extracted data including 'H_total_au' and 'G_total_au'.
        """
        inps = list(folder.glob("*.inp"))
        outp = fs.find_best_out_for_qc(folder)
        itexts = [readers.read_text_safe(p) for p in inps]
        otext = readers.read_text_safe(outp) if outp else ""

        meth = all(ic.method_exist(t) for t in itexts) if itexts else False
        base = all(ic.basis_exist(t) for t in itexts) if itexts else False
        task = all(ic.tasks_exist(t) for t in itexts) if itexts else False
        chmu = all(ic.charge_mult_exist(t) for t in itexts) if itexts else False
        xyz  = all(ic.xyz_exist(t) for t in itexts) if itexts else False
        scf = oc.scf_converged(otext) if otext else False
        geo = oopt.geo_opt_converged(otext) if otext else False
        imag = (not oopt.imaginary_freq_not_exist(otext)) if otext else False

        bools = {
            "Method exist?": "yes" if meth else "no",
            "Basis set exist?": "yes" if base else "no",
            "Tasks exist?": "yes" if task else "no",
            "Charge & mult exist?": "yes" if chmu else "no",
            "XYZ file exist?": "yes" if xyz else "no",
            "SCF converged?": "yes" if scf else "no",
            "Geo opt converged?": "yes" if geo else "no",
            "Imag freq exist?": "yes" if imag else "no",
        }

        # GT Extraction
        gt = {}
        if otext:
            gt = extract_rs_core(otext)
        
        return {
            "Folder": folder.name,
            "FolderPath": str(folder.resolve()),
            "booleans": bools,
            "ground_truth": gt
        }

    def extract_agent_data(self, report_path: Optional[Path]) -> Dict[str, Any]:
        """
        Extracts ring strain values from the report.

        Args:
            report_path (Optional[Path]): The path to the report.

        Returns:
            Dict[str, Any]: Extracted agent rows.
        """
        if not report_path: 
            return {"rows": {}, "reference_is_cyclohexane": False}
        return extract_ringstrain_from_md(str(report_path))

    def score_all(self, folder_results: List[Dict[str, Any]], agent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Aggregates energies, calculates strain, and scores against agent data.

        Args:
            folder_results (List[Dict]): Per-folder extracted energies.
            agent_data (Dict): Extracted agent strain values.

        Returns:
            Dict[str, Any]: Final score.
        """
        # 1. Build Reaction Maps (Cyclo vs Methyl)
        cyclo, methyl = ringstrain_calc.build_structure_energy_maps(self.root)
        
        # 2. Overlay Extracted H/G Values
        gt_by_path = {}
        for res in folder_results:
            p = os.path.normpath(res["FolderPath"])
            H = res["ground_truth"].get("H_total_au")
            G = res["ground_truth"].get("G_total_au")
            gt_by_path[p] = (H, G)
        
        for d in (cyclo, methyl):
            for rec in d.values():
                p = os.path.normpath(str(rec["folder"].resolve()))
                if p in gt_by_path:
                    rec["H_au"], rec["G_au"] = gt_by_path[p]

        # 3. Calculate Deltas (n vs n-1)
        dH_by_n, dG_by_n = {}, {}
        candidate_ns = sorted(set(cyclo.keys()) | {m + 1 for m in methyl.keys()})
        
        for n in candidate_ns:
            m = n - 1
            if m in methyl and n in cyclo:
                Hc, Gc = cyclo[n].get("H_au"), cyclo[n].get("G_au")
                Hm, Gm = methyl[m].get("H_au"), methyl[m].get("G_au")
                
                if Hc is not None and Hm is not None:
                    dH_by_n[n] = (float(Hm) - float(Hc)) * HARTREE_TO_KCAL
                if Gc is not None and Gm is not None:
                    dG_by_n[n] = (float(Gm) - float(Gc)) * HARTREE_TO_KCAL

        # 4. Cumulative Strain S_n (Anchored at n=6)
        all_ns = sorted(set(candidate_ns) | {3,4,5,6,7,8})
        S_H = {6: 0.0}; S_G = {6: 0.0}
        
        for n in [k for k in all_ns if k > 6]:
            prev = n - 1
            if prev in S_H and n in dH_by_n: 
                S_H[n] = S_H[prev] + dH_by_n[n]
            if prev in S_G and n in dG_by_n: 
                S_G[n] = S_G[prev] + dG_by_n[n]
            
        for n in sorted([k for k in all_ns if k < 6], reverse=True):
            nxt = n + 1
            if nxt in S_H and nxt in dH_by_n: 
                S_H[n] = S_H[nxt] - dH_by_n[nxt]
            if nxt in S_G and nxt in dG_by_n: 
                S_G[n] = S_G[nxt] - dG_by_n[nxt]

        # 5. Final GT Rows for Scorer
        final_gt = {}
        for n in [3,4,5,6,7,8]:
            final_gt[n] = {
                "ring_size": n,
                "strain_delta_H_kcal_mol": S_H.get(n),
                "strain_delta_G_kcal_mol": S_G.get(n)
            }

        # 6. Prepare Agent Rows
        raw_agent = agent_data.get("rows", {})
        final_agent = {}
        for k, v in raw_agent.items():
            try: final_agent[int(k)] = v
            except: pass

        # 7. Final Scoring
        bool_df = pd.DataFrame([r["booleans"] for r in folder_results])

        return score_ringstrain(
            booleans=bool_df,
            ground_truth_rows=final_gt,
            agent_rows=final_agent,
            reference_is_cyclohexane=agent_data.get("reference_is_cyclohexane", False),
            rubric=self.rubric
        )
