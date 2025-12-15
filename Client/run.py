from __future__ import annotations
import argparse
from pathlib import Path
import json
import sys
from typing import Dict, Any

from Auto_benchmark.registry.jobs import JOB_MAP

def run(job_name: str, root_dir: str, out_json: str = None, debug: bool = False) -> Dict[str, Any]:
    """
    Main entry point for running a benchmark job.

    Initializes the appropriate job class based on the job name,
    runs the benchmark workflow, and optionally saves the result.

    Args:
        job_name (str): The name of the job to run (e.g., 'tddft', 'pka').
        root_dir (str): The root directory containing the dataset to benchmark.
        out_json (str, optional): Path to save the result as a JSON file. Defaults to None.
        debug (bool): If True, enables debug logging to console. Defaults to False.

    Returns:
        Dict[str, Any]: The final benchmark result dictionary containing scores and details.

    Raises:
        SystemExit: If the job name is unknown or a critical error occurs during execution.
    """
    job_key = job_name.lower().strip()
    if job_key not in JOB_MAP:
        available = ", ".join(JOB_MAP.keys())
        print(f"Error: Unknown job '{job_name}'. Available jobs: {available}")
        sys.exit(1)

    print(f"Initializing job: {job_key}")
    JobClass = JOB_MAP[job_key]
    
    try:
        job_instance = JobClass(root_dir, debug=debug)
        result = job_instance.run()
    except Exception as e:
        print(f"Critical Error during execution: {e}")
        if debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)

    if out_json:
        out_path = Path(out_json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Results saved to {out_path}")
    
    return result

def main():
    """
    CLI entry point parsing command line arguments and calling run().
    """
    parser = argparse.ArgumentParser(description="Auto-benchmark Class-Based Runner")
    parser.add_argument("--job", required=True, help="Job type (e.g. tddft, pka, ringstrain, fukui)")
    parser.add_argument("--root", required=True, help="Root directory of the dataset")
    parser.add_argument("--out", help="Path to save output JSON")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    run(args.job, args.root, args.out, args.debug)

if __name__ == "__main__":
    main()
