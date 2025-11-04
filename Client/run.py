# Auto_benchmark/Client/run.py
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import json
import pandas as pd

# central router
from Auto_benchmark.registry.jobs import get_job

# shared IO (general, job-agnostic)
from Auto_benchmark.io import fs, readers
from Auto_benchmark.Config import defaults


# ---------------------------
# Local helpers (general)
# ---------------------------
def _allowed_path(p: Path) -> bool:
    """Path is allowed if none of its parts are in SKIP_DIRS (case-insensitive)."""
    return not any(part.lower() in defaults.SKIP_DIRS for part in p.parts)


def list_subdirs(root: Path) -> List[Path]:
    # Walk only valid molecule folders (skip jobinfo/logs/reports by config)
    return fs.iter_child_folders(root)


def find_files(folder: Path, pattern: str) -> List[Path]:
    """rglob files under folder that pass _allowed_path; skips slurm* .out."""
    files = [p for p in folder.rglob(pattern) if _allowed_path(p)]
    if pattern == "*.out":
        files = [p for p in files if not p.name.lower().startswith(defaults.SKIP_OUTFILE_PREFIXES)]
    return sorted(files)


# ---------------------------
# Runner
# ---------------------------
def run(job_type: str, root_dir: Union[str, Path], *,
        out_json: Optional[Union[str, Path]] = None,
        debug: bool = False) -> Dict[str, Any]:
    """
    General auto-benchmark runner.
    """
    root = Path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"Root path not found: {root}")

    job = get_job(job_type)

    bool_columns         = job["bool_columns"]
    compute_booleans     = job["compute_booleans"]
    extract_ground_truth = job["extract_ground_truth"]
    find_report          = job["find_report"]
    extract_agent        = job["extract_agent"]
    score                = job["score"]
    rubric               = job["rubric"]

    # Let the job decide how to locate a central report
    report_md: Optional[Path] = find_report(root)

    # fallback: use single .md if no report found
    if report_md is None:
        md_candidates = sorted(root.glob("*.md"))
        if len(md_candidates) == 1:
            report_md = md_candidates[0]
            if debug:
                print(f"[DEBUG] Using fallback report: {report_md}")
        elif len(md_candidates) > 1:
            preferred = {
                "Photophysical_Properties_Final_Report.md",
                "TDDFT_Report.md", "tddft_report.md",
                "pka_calculation_report.md", "pKa_calculation_report.md",
            }
            chosen = next((p for p in md_candidates if p.name in preferred), md_candidates[0])
            report_md = chosen if chosen else None

    # ---------------------------
    # Structural representative set
    # ---------------------------
    # One folder per unique InChIKey (structure-based), preferring real freqs
    representatives: List[Path] = fs.select_unique_by_inchikey(root, prefer_real_freqs=True)
    if debug:
        print(f"[DEBUG] Representatives selected: {len(representatives)} / {len(list_subdirs(root))} folders")

    # ==============================================================
    # AGGREGATE PATH (e.g., pKa, RingStrain)
    # ==============================================================
    aggregate = bool(job.get("aggregate_across_folders", False)
                     or job_type.strip().lower() == "pka")
    if aggregate:
        rows: List[Dict[str, Any]] = []
        gt_rows: List[Dict[str, Any]] = []  # <-- collect per-folder H/G totals here
        folder_filter = job.get("folder_filter")

        for folder in representatives:
            if folder.name.lower() in defaults.SKIP_DIRS or "jobinfo" in folder.name.lower():
                if debug:
                    print(f"[DEBUG] Skipping SKIP_DIR: {folder.name}")
                continue

            if folder_filter:
                if not folder_filter(folder):
                    if debug:
                        print(f"[DEBUG] Skipping by job filter: {folder.name}")
                    continue
            else:
                if not fs.has_non_slurm_out(folder):
                    if debug:
                        print(f"[DEBUG] Skipping no-usable-.out folder: {folder.name}")
                    continue

            inps = find_files(folder, "*.inp")
            primary_out = fs.find_best_out_for_qc(folder)  # ← prefer clean real-minimum
            outs   = [primary_out] if primary_out else []
            itexts = [readers.read_text_safe(p) for p in inps] if inps else []
            otexts = [readers.read_text_safe(primary_out)] if primary_out else []

            if debug:
                which = primary_out.name if primary_out else "None"
                print(f"[DEBUG] {folder.name}: qc_out = {which}")

            # QC booleans table row
            bools = compute_booleans(itexts, otexts, str(folder.resolve()))
            rows.append({"Folder": folder.name, **bools})

            # Ground-truth per-folder totals for aggregate scorers (e.g., RingStrain)
            try:
                gt = extract_ground_truth(otexts, outs)
            except Exception:
                gt = {}
            gt_rows.append({
                "Folder": folder.name,
                "FolderPath": str(folder.resolve()),  # ← include absolute path for structure mapping
                "H_total_au": gt.get("H_total_au"),
                "G_total_au": gt.get("G_total_au"),
            })

        if rows:
            all_df = pd.DataFrame(rows)
            for col in bool_columns:
                if col not in all_df.columns:
                    all_df[col] = ""
            booleans_df = all_df[bool_columns].copy()
        else:
            booleans_df = pd.DataFrame(columns=bool_columns)

        agent_numeric = extract_agent(report_md, root)

        # ---- pass aggregated ground-truth rows into the job scorer ----
        score_report  = score(
            booleans=booleans_df,
            gt_numeric=gt_rows,
            agent_numeric=agent_numeric,
            rubric=rubric,
        )

        payload = {
            "job_type": job_type,
            "root": str(root.resolve()),
            "aggregated": True,
            "representatives": [str(p) for p in representatives],
            "booleans_rows": rows,
            "agent_numeric": agent_numeric,
            "score": score_report,
        }

        if out_json:
            Path(out_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    # ==============================================================
    # DEFAULT PATH (e.g., TDDFT) — per-folder scoring
    # ==============================================================
    results: List[Dict[str, Any]] = []

    for folder in representatives:
        if folder.name.lower() in defaults.SKIP_DIRS or "jobinfo" in folder.name.lower():
            if debug:
                print(f"[DEBUG] Skipping non-molecule folder: {folder.name}")
            continue

        inps = find_files(folder, "*.inp")
        primary_out = fs.find_best_out_for_qc(folder)
        outs = [primary_out] if primary_out else []

        itexts = [readers.read_text_safe(p) for p in inps] if inps else []
        otexts = [readers.read_text_safe(primary_out)] if primary_out else []
        if debug:
            which = primary_out.name if primary_out else "None"
            print(f"[DEBUG] {folder.name}: qc_out = {which}")

        bools = compute_booleans(itexts, otexts, str(folder.resolve()))

        row = {"Folder": folder.name, **bools}
        boolean_df = pd.DataFrame([[row.get(c, "") for c in bool_columns]], columns=bool_columns)

        gt_numeric    = extract_ground_truth(otexts, outs)
        agent_numeric = extract_agent(report_md, folder)

        if debug:
            def _fmt_num(v):
                return None if v is None else (float(v) if isinstance(v, (int, float)) else v)
            print(f"[DEBUG] {folder.name} → agent_numeric = "
                  f"S1={_fmt_num(agent_numeric.get('S1_energy_eV'))}, "
                  f"f={_fmt_num(agent_numeric.get('S1_oscillator_strength'))}, "
                  f"T1={_fmt_num(agent_numeric.get('T1_energy_eV'))}, "
                  f"Gap={_fmt_num(agent_numeric.get('S1_T1_gap_eV'))}")

        score_report = score(
            booleans=boolean_df,
            gt_numeric=gt_numeric,
            agent_numeric=agent_numeric,
            rubric=rubric,
        )

        results.append({
            "folder": folder.name,
            "booleans": row,
            "numeric_gt": gt_numeric,
            "numeric_agent": agent_numeric,
            "score": score_report,
        })

    totals = [
        r["score"]["total_points"]
        for r in results
        if isinstance(r.get("score", {}), dict) and "total_points" in r["score"]
    ]
    summary = {
        "count": len(results),
        "mean_total": float(sum(totals) / len(totals)) if totals else 0.0,
    }

    payload = {
        "job_type": job_type,
        "root": str(root.resolve()),
        "representatives": [str(p) for p in representatives],
        "results": results,
        "summary": summary,
    }

    if out_json:
        Path(out_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def main():
    ap = argparse.ArgumentParser(description="Auto-benchmark runner")
    ap.add_argument("--job", required=True)
    ap.add_argument("--root", required=True)
    ap.add_argument("--out", default=None)
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    run(args.job, args.root, out_json=args.out, debug=args.debug)


if __name__ == "__main__":
    main()
