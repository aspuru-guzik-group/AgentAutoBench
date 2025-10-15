# Auto_benchmark/Client/run.py
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
import json
import pandas as pd

# central router
from Auto_benchmark.registry.jobs import get_job

# shared IO
from Auto_benchmark.io.fs import walk_job_folders
from Auto_benchmark.config.defaults import SKIP_DIRS, SKIP_OUTFILE_PREFIXES
from Auto_benchmark.io.readers import read_text_safe


def _allowed_path(p: Path) -> bool:
    return not any(part.lower() in SKIP_DIRS for part in p.parts)


def list_subdirs(root: Path) -> List[Path]:
    # Walk only valid molecule folders (skip jobinfo/logs/reports by config)
    subdirs = list(walk_job_folders(root))
    filtered = [p for p in subdirs if p.name.lower() not in SKIP_DIRS]
    return filtered


def find_files(folder: Path, pattern: str) -> List[Path]:
    files = [p for p in folder.rglob(pattern) if _allowed_path(p)]
    if pattern == "*.out":
        files = [p for p in files if not p.name.lower().startswith(SKIP_OUTFILE_PREFIXES)]
    return sorted(files)


def run(job_type: str, root_dir: Union[str, Path], *, out_json: Optional[Union[str, Path]] = None, debug: bool = False) -> Dict[str, Any]:
    """
    General auto-benchmark runner.

    Delegates all job-specific logic (booleans, ground-truth extraction,
    agent extraction, scoring, rubric) to the job object returned by
    `get_job(job_type)`.
    """
    root = Path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"Root path not found: {root}")

    job = get_job(job_type)

    # ---- required job hooks ----
    bool_columns: List[str] = job["bool_columns"]
    compute_booleans       = job["compute_booleans"]
    extract_ground_truth   = job["extract_ground_truth"]
    find_report            = job["find_report"]
    extract_agent          = job["extract_agent"]
    score                  = job["score"]
    rubric                 = job["rubric"]

    results: List[Dict[str, Any]] = []

    # Let the job decide how to locate a central report (if any)
    report_md: Optional[Path] = find_report(root)

    # --- Fallback: if the job doesn't find a report, try a simple single-report pick like test.py ---
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
            }
            chosen = next((p for p in md_candidates if p.name in preferred), md_candidates[0])
            report_md = chosen if chosen else None

    for folder in list_subdirs(root):
        # Skip administrative or utility folders (safety double-check)
        if folder.name.lower() in SKIP_DIRS or "jobinfo" in folder.name.lower():
            if debug:
                print(f"[DEBUG] Skipping non-molecule folder: {folder.name}")
            continue

        inps = find_files(folder, "*.inp")
        outs = find_files(folder, "*.out")

        itexts = [read_text_safe(p) for p in inps] if inps else []
        otexts = [read_text_safe(p) for p in outs] if outs else []

        bools = compute_booleans(itexts, otexts, folder.name)
        row = {"Folder": folder.name, **bools}

        boolean_df = pd.DataFrame([[row.get(c, "") for c in bool_columns]], columns=bool_columns)

        gt_numeric     = extract_ground_truth(otexts, outs)
        agent_numeric  = extract_agent(report_md, folder)

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

    totals = [r["score"]["total_points"] for r in results]
    summary = {
        "count": len(results),
        "mean_total": float(sum(totals) / len(totals)) if totals else 0.0,
    }

    payload = {
        "job_type": job_type,
        "root": str(root.resolve()),
        "results": results,
        "summary": summary,
    }

    if out_json:
        Path(out_json).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return payload


def main():
    ap = argparse.ArgumentParser(description="Auto-benchmark runner")
    ap.add_argument("--job", required=True, help="job type (e.g., TDDFT, PKA, OPT, FREQ)")
    ap.add_argument("--root", required=True, help="root directory containing per-molecule folders")
    ap.add_argument("--out", default=None, help="optional path to write JSON summary")
    ap.add_argument("--debug", action="store_true", help="print debug info about agent extraction")
    args = ap.parse_args()

    run(args.job, args.root, out_json=args.out, debug=args.debug)


if __name__ == "__main__":
    main()
