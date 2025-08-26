#!/usr/bin/env python3
# grade_pka.py
# Scoring: 64 (8×8 booleans) + 12 (8 ΔG booleans ×1.5) + 12 (linear model) + 12 (pKa window) = 100

import argparse, json, re, sys
from pathlib import Path
import pandas as pd

# ---------- Rubric (edit here if you ever adjust weights) ----------
RUBRIC = {
    "section1": {  # 8 molecules × 8 checks = 64
        "columns": [
            "Method exist?",
            "Basis set exist?",
            "Tasks exist?",
            "Charge & mult exist?",
            "XYZ file exist?",
            "SCF converged?",
            "Geo opt converged?",
            # For imaginary frequencies, "no" means correct (true minimum)
            "Imag freq exist?",
        ],
        "yes_score": 1.0,  # for first 7 columns
        "imag_freq_score": 1.0,  # award when value == "no"
        "max_points": 64.0,
    },
    "section2": {  # 8 ΔG booleans = 12 points (1.5 each)
        "per_yes": 1.5,
        "max_points": 12.0,
    },
    "section3": {  # gate on JSON proof of calculation
        "linear_regression": 12.0,      # if model exists
        "pka_exact_window": (1.4, 1.6), # full 12 pts
        "pka_wide_window": (1.2, 1.8),  # half 6 pts
        "pka_full": 12.0,
        "pka_half": 6.0,
        "max_points": 24.0,
    }
}

YES_VALUES = {"yes", "y", "true", "1", "t"}

def is_yes(x: object) -> bool:
    """
    Interprets an arbitrary value as a boolean “yes” using a predefined token set.

    Converts the input to a lowercase, stripped string and checks membership in
    `YES_VALUES` (e.g., {"yes", "y", "true", "1", "t"}). `None` is treated as False.

    Args:
        x (object): Any value to interpret (e.g., str, int, bool, None).

    Returns:
        bool: True if the normalized value is in `YES_VALUES`; otherwise False.

    Raises:
        NameError: If `YES_VALUES` is not defined in the calling scope.
        TypeError: If `x` cannot be converted to a string (rare).

    Notes:
        - Normalization is: `str(x).strip().lower()`.
        - Update `YES_VALUES` to tailor accepted “yes” tokens for your dataset.
    """
    if x is None:
        return False
    return str(x).strip().lower() in YES_VALUES


def read_csv(path: Path) -> pd.DataFrame:
    """
    Reads a CSV-like file by trying multiple common separators, with a fallback.

    Attempts to parse the file using separators in the order: [",", ";", "\\t", "|"].
    A parse is considered successful heuristically if the resulting DataFrame has
    more than one column. If all attempts fail this heuristic, falls back to
    `pandas.read_csv(path)` with pandas’ default delimiter detection.

    Args:
        path (Path): Path to the CSV (or delimited) file.

    Returns:
        pandas.DataFrame: The parsed table.

    Raises:
        FileNotFoundError: If the file does not exist.
        PermissionError: If the file cannot be read due to permissions.
        UnicodeDecodeError: If the file cannot be decoded as text.
        pd.errors.ParserError: If the fallback `read_csv` fails to parse.
        OSError: For other I/O-related errors.

    Notes:
        - The “>1 column” heuristic prevents falsely accepting single-column reads
          with the wrong delimiter.
        - If you expect single-column files as valid input, remove or adjust the
          heuristic accordingly.
    """
    # Try common separators
    for sep in [",", ";", "\t", "|"]:
        try:
            df = pd.read_csv(path, sep=sep, engine="python")
            # Heuristic: consider parse successful if >1 column
            if df.shape[1] > 1:
                return df
        except Exception:
            continue
    # Fallback to default
    return pd.read_csv(path)

# ---------- Section 1: 8×8 boolean checks ----------
def score_section1(booleans_csv: Path) -> tuple[float, dict]:
    """
    Scores Section 1 from a booleans CSV using the rubric-defined columns.

    The CSV is read with `read_csv`. Required columns are taken from
    `RUBRIC["section1"]["columns"]`. Column headers are matched robustly by:
      1) exact match after lowercasing/stripping, and
      2) a fuzzy fallback that removes non-alphanumerics.
    For each row:
      • The first 7 columns yield 1 point each when `is_yes(value)` is True.
      • The 8th column is the “imaginary frequency” flag and yields 1 point when
        the (string) value indicates “no” (one of {"no","0","false","n"}, case-insensitive).

    The total score is the sum across rows. A details dictionary is returned
    containing per-row points, total rows, the resolved column names used, and
    the rubric’s max points.

    Args:
        booleans_csv (Path): Path to the CSV file containing boolean-like fields
            used for Section 1 checks.

    Returns:
        tuple[float, dict]: A pair `(points, details)` where:
            - `points` (float): Sum of row scores across the file.
            - `details` (dict): Metadata with keys:
                * `per_row_points` (list[float]): Points awarded per row.
                * `total_rows` (int): Number of scored rows.
                * `columns_used` (list[str]): Original column headers resolved for scoring.
                * `max` (float | int): `RUBRIC["section1"]["max_points"]`.

    Raises:
        FileNotFoundError: If `booleans_csv` does not exist.
        PermissionError: If the file cannot be read.
        UnicodeDecodeError: If the file cannot be decoded as text.
        KeyError: If a required rubric column cannot be found in the CSV headers.
        NameError: If `RUBRIC` or `is_yes` is not defined in scope.
        Exception: Any other parsing errors from `read_csv`.

    Notes:
        - `is_yes` should normalize truthy tokens (e.g., "yes","y","true","1").
        - The imaginary-frequency column awards points on explicit “no/false”.
        - Header matching is case/space insensitive and tolerates punctuation differences.
    """
    df = read_csv(booleans_csv)
    cols = RUBRIC["section1"]["columns"]

    # Try to normalize header spaces/case
    norm_map = {c.lower().strip(): c for c in df.columns}
    def find_col(name: str) -> str:
        key = name.lower().strip()
        if key in norm_map: return norm_map[key]
        # fuzzy: remove punctuation/spaces
        de = re.sub(r"[^a-z0-9]+", "", key)
        for k, v in norm_map.items():
            if re.sub(r"[^a-z0-9]+", "", k) == de:
                return v
        raise KeyError(f"Column not found in booleans CSV: {name}")

    real_cols = [find_col(c) for c in cols]
    points = 0.0
    detail_rows = []

    for _, row in df.iterrows():
        row_pts = 0.0
        # first 7 yes->1
        for c in real_cols[:7]:
            row_pts += 1.0 if is_yes(row.get(c)) else 0.0
        # imaginary freq: award when "no"
        imag_col = real_cols[7]
        val = str(row.get(imag_col, "")).strip().lower()
        row_pts += 1.0 if val in {"no", "0", "false", "n"} else 0.0
        points += row_pts
        detail_rows.append(row_pts)

    return points, {
        "per_row_points": detail_rows,
        "total_rows": len(detail_rows),
        "columns_used": real_cols,
        "max": RUBRIC["section1"]["max_points"],
    }

# ---------- Section 2: ΔG booleans ----------
def score_section2(dg_csv: Path | None) -> tuple[float, dict]:
    """
    Scores Section 2 from a ΔG-related CSV using a yes/no heuristic and capping.

    Behavior:
      • If `dg_csv` is None or missing, returns 0.0 with a reason and the section max.
      • Reads the CSV via `read_csv`.
      • Detects boolean-like columns by sampling each column and computing the
        ratio of values matching yes/no tokens. Columns with ratio > 0.6 are
        treated as boolean flags. If none qualify, falls back to using all
        columns except the first.
      • For each row, counts it as a “yes” if **any** flagged column is truthy
        under `is_yes`.
      • Awards `per_yes` points per counted row, caps the count at 8 rows, and
        caps the total at `max_points`.

    Args:
        dg_csv (Path | None): Path to the ΔG CSV. If None or non-existent,
            the function returns early with 0.0 and a reason.

    Returns:
        tuple[float, dict]: `(points, details)` where:
            - `points` (float): Capped Section 2 score.
            - `details` (dict) with keys:
                * `rows_seen` (int): Number of rows in the CSV.
                * `yes_count_capped8` (int): Number of rows counted as “yes”,
                  capped at 8.
                * `bool_cols_used` (list[str]): Columns considered boolean-like.
                * `max` (float | int): `RUBRIC["section2"]["max_points"]`.

    Raises:
        FileNotFoundError: If `dg_csv` exists check passes but read later fails.
        PermissionError: If the file cannot be read.
        UnicodeDecodeError: If the file cannot be decoded as text.
        NameError: If `RUBRIC`, `YES_VALUES`, or `is_yes` is not defined.
        Exception: Any parsing errors propagated by `read_csv`.

    Notes:
        - Boolean detection uses tokens from `YES_VALUES` plus {"no","n","false","0"}.
        - Scoring caps: ≤ 8 rows × `per_yes`, then ≤ `max_points`.
        - If your data guarantees exactly one boolean column, the “any flag true”
          reduction is equivalent to checking that column alone.
    """
    if dg_csv is None or not dg_csv.exists():
        return 0.0, {"reason": "delta-G CSV not provided/found", "max": RUBRIC["section2"]["max_points"]}
    df = read_csv(dg_csv)

    # Heuristic: assume first column is label, booleans in remaining
    # If a single boolean column exists, we use that.
    bool_cols = []
    for c in df.columns:
        # Detect columns that look like yes/no flags
        sample = df[c].astype(str).str.lower().str.strip()
        yes_no_ratio = sample.isin(list(YES_VALUES) + ["no", "n", "false", "0"]).mean()
        if yes_no_ratio > 0.6:
            bool_cols.append(c)

    if not bool_cols:
        # fallback: assume any column (except the first) is boolean-ish
        bool_cols = df.columns[1:].tolist()

    yes_count = 0
    for _, row in df.iterrows():
        # reduce across flagged columns; if any 'yes' in the row, count it
        # (If your CSV has exactly one boolean per row, this is equivalent.)
        row_yes = any(is_yes(row[c]) for c in bool_cols)
        yes_count += 1 if row_yes else 0

    points = min(yes_count, 8) * RUBRIC["section2"]["per_yes"]
    points = min(points, RUBRIC["section2"]["max_points"])
    return points, {
        "rows_seen": len(df),
        "yes_count_capped8": min(yes_count, 8),
        "bool_cols_used": bool_cols,
        "max": RUBRIC["section2"]["max_points"],
    }

# ---------- JSON confirmation ----------
CALC_KEYWORDS = [
    "pka calculation", "predicted pka", "report saved", "pka of chlorofluoroacetic acid",
    "pka =", "b3lyp", "smd water", "calibration", "linear regression"
]

def calculation_happened(trace_json: Path) -> bool:
    """
    Determines whether a calculation likely occurred based on an action-trace JSON.

    Loads the JSON produced by `extract_action_trace_json` and scans each step’s
    tool-call `output` as well as `message_to_agent` text for any substring in
    `CALC_KEYWORDS` (case-insensitive). Returns True on the first match; returns
    False if the file is missing, cannot be parsed, or no keywords are found.

    Args:
        trace_json (Path): Path to an action-trace JSON file.

    Returns:
        bool: True if any calculation keyword is found in a tool output or agent
              message; otherwise False.

    Raises:
        NameError: If `CALC_KEYWORDS` is not defined in the calling scope.

    Notes:
        - The function expects a top-level key `"agent_trace"` containing a list
          of steps. Each step may include `"tool_calls"` (list of dicts with an
          `"output"` field) and `"message_to_agent"` (str).
        - JSON decoding errors are caught and treated as a non-calculation case
          (returns False).
    """
    if not trace_json.exists(): return False
    try:
        data = json.loads(Path(trace_json).read_text())
    except Exception:
        return False

    steps = data.get("agent_trace", [])
    for step in steps:
        for tc in step.get("tool_calls", []):
            out = str(tc.get("output", "")).lower()
            if out and any(k in out for k in CALC_KEYWORDS):
                return True
        # also scan the message_to_agent text just in case
        msg = str(step.get("message_to_agent", "")).lower()
        if msg and any(k in msg for k in CALC_KEYWORDS):
            return True
    return False

# ---------- Section 3: regression + pKa from CSV ----------
LINEAR_KEYS = [r"\blinear regression\b", r"\br\^?2\b", r"r²", r"\bslope\b", r"\bintercept\b", r"pka\s*=\s*.*Δ?g"]

def detect_linear_regression_model(md_text: str, debug: bool = False) -> bool:
    """
    Detects whether a markdown passage explicitly reports a linear regression model.

    Heuristics (any one is sufficient):
      • The exact phrase “linear regression” appears (case-insensitive), OR
      • An explicit equation of the rough form “pKa = <coef> (x|×|*) ΔG + <intercept>”
        (Δ is optional, i.e., ΔG or G) **and** at least one regression statistic is
        mentioned (any of: R², R-squared, R2, RMSE, p-value).

    Mentions like “calibration model” or generic “model” without the above signals
    should evaluate to False.

    Args:
        md_text (str): Markdown/plain-text content to analyze.
        debug (bool): If True, prints which internal triggers fired
            (e.g., "phrase: linear regression", "equation + stats"). Default: False.

    Returns:
        bool: True if the text meets the explicit linear-regression criteria;
              otherwise False.

    Raises:
        None.
    """
    triggers = []

    # 1) explicit phrase
    if re.search(r'\blinear\s+regression\b', md_text, re.IGNORECASE):
        triggers.append('phrase: linear regression')

    # 2) explicit equation form pKa = <coef> (x|×|*) ΔG + <intercept>
    eq = re.search(
        r'p\s*ka\s*=\s*[^=\n]{0,80}(?:x|×|\*)\s*Δ?\s*G',  # allow ΔG or G
        md_text, re.IGNORECASE
    )

    # 3) at least one regression statistic mentioned
    stats = any(re.search(pat, md_text, re.IGNORECASE) for pat in [
        r'R²', r'R-squared', r'\bR2\b',
        r'\bRMSE\b',
        r'\bp[-\s]?value\b'
    ])

    if eq and stats:
        triggers.append('equation + stats')

    if debug:
        print("Linear-regression detection triggers:", triggers)

    return bool(triggers)

PKA_PAT = re.compile(r"(?i)p\s*ka[^0-9\-]*(-?\d+(?:\.\d+)?)")

def extract_pka_from_csv(report_csv: Path) -> float | None:
    """
    Extracts a pKa value from a CSV using header and free-text heuristics.

    Procedure:
      1) If the file does not exist, return None.
      2) Read the CSV via `read_csv`.
      3) Prefer numeric values from columns whose header matches /p\s*ka/i; take
         the first non-NA numeric entry in range [0, 20].
      4) If none found, regex-scan all cell text with `PKA_PAT`; return the first
         match in range [0, 20].

    Args:
        report_csv (Path): Path to the CSV file that may contain a reported pKa.

    Returns:
        float | None: The detected pKa value (0 ≤ pKa ≤ 20) or None if not found.

    Raises:
        NameError: If `read_csv`, `pd`, or `PKA_PAT` is not defined in scope.
        UnicodeDecodeError: If the file cannot be decoded as text.
        pandas.errors.ParserError: If parsing fails inside `read_csv`.
        OSError: On other I/O errors (permissions, etc.).

    Notes:
        - Header matching uses a case-insensitive pattern `p\\s*ka`.
        - Text search relies on a precompiled `PKA_PAT` that must capture the
          numeric value in group(1).
        - The [0, 20] guard filters out obvious non-pKa numbers; adjust as needed.
    """
    if not report_csv.exists(): return None
    df = read_csv(report_csv)

    # 1) Look in numeric columns named like pKa
    for c in df.columns:
        if re.search(r"(?i)p\s*ka", str(c)):
            try:
                series = pd.to_numeric(df[c], errors="coerce").dropna()
                if not series.empty:
                    val = float(series.iloc[0])
                    if 0.0 <= val <= 20.0:
                        return val
            except Exception:
                pass

    # 2) Regex search across all text
    for _, row in df.iterrows():
        for v in row.values:
            m = PKA_PAT.search(str(v))
            if m:
                try:
                    val = float(m.group(1))
                    if 0.0 <= val <= 20.0:
                        return val
                except Exception:
                    continue
    return None

# --- NEW: gather text for linear-regression detection from JSON (+ referenced .md) ---
def gather_text_for_linear_detection(trace_json: Path) -> str:
    """
    Aggregates relevant text from an action-trace JSON (and a linked markdown report).

    Loads the JSON trace (as produced by `extract_action_trace_json`) and
    concatenates:
      • Each step `message_to_agent`
      • Each tool call `output`
    Additionally, if any tool output contains a filesystem path ending with
    `pka_calculation_report.md`, that markdown file is read and appended to the
    buffer. The result is a single text blob suitable for downstream detectors
    (e.g., linear-regression detection).

    Args:
        trace_json (Path): Path to the trace JSON file.

    Returns:
        str: Combined text of messages, tool outputs, and (if found/readable)
             the referenced markdown report. Returns an empty string if the JSON
             cannot be parsed.

    Raises:
        None. JSON and file I/O errors are caught and result in graceful fallback:
          - JSON decode failure → returns "".
          - Markdown read failure → markdown is skipped.

    Notes:
        - Expects a top-level `agent_trace` list. Each element may include:
            * `message_to_agent` (str)
            * `tool_calls` (list of dicts with an `output` field)
        - Markdown path detection uses the regex:
            `([/\\w\\-\\.\\~]+pka_calculation_report\\.md)` (case-insensitive).
    """
    buf = []
    try:
        data = json.loads(trace_json.read_text())
    except Exception:
        return ""

    steps = data.get("agent_trace", [])
    md_path = None

    for step in steps:
        msg = step.get("message_to_agent", "")
        if msg:
            buf.append(str(msg))
        for tc in step.get("tool_calls", []) or []:
            out = str(tc.get("output", ""))
            if out:
                buf.append(out)
                # try to find a saved markdown path in the output
                m = re.search(r"([/\w\-\.\~]+pka_calculation_report\.md)", out, re.IGNORECASE)
                if m:
                    md_path = m.group(1)

    if md_path:
        try:
            md_text = Path(md_path).read_text(encoding="utf-8", errors="ignore")
            buf.append(md_text)
        except Exception:
            pass

    return "\n\n".join(buf)

def score_section3(trace_json: Path, report_csv: Path | None) -> tuple[float, dict]:
    """
    Scores Section 3 using an action-trace JSON (for calculation + regression evidence)
    and an optional CSV (for pKa extraction).

    Behavior:
      • Calculation evidence gate:
          - Calls `calculation_happened(trace_json)`. If False, returns `(0.0, details)`
            with `details = {"did_calc": False, "reason": "...", "max": RUBRIC["section3"]["max_points"]}`.
      • Linear regression points:
          - Concatenates relevant text via `gather_text_for_linear_detection(trace_json)`,
            then checks `detect_linear_regression_model(...)`.
          - If True, adds `RUBRIC["section3"]["linear_regression"]` to the score and sets
            `details["linear_regression_found"] = True` (else False).
      • pKa points:
          - Attempts to get a pKa value from `report_csv` using `extract_pka_from_csv`.
          - If a value is found, awards:
              * `RUBRIC["section3"]["pka_full"]` if within `RUBRIC["section3"]["pka_exact_window"]` [lo_full, hi_full], or
              * `RUBRIC["section3"]["pka_half"]` if within `RUBRIC["section3"]["pka_wide_window"]`  [lo_wide, hi_wide],
              * otherwise 0.0.
            Records the numeric pKa in `details["pka_extracted"]` and the awarded points in `details["pka_points"]`.
          - If no pKa is found, sets `details["pka_extracted"] = None` and `details["pka_points"] = 0.0`.
      • Always includes `details["did_calc"]` and `details["max"] = RUBRIC["section3"]["max_points"]`.

    Args:
        trace_json (Path): Path to the JSON produced by `extract_action_trace_json`.
        report_csv (Path | None): Optional CSV that may contain a reported pKa value.

    Returns:
        tuple[float, dict]: `(points, details)` where:
            - `points` (float): Total Section 3 score after all rules above.
            - `details` (dict): Metadata including:
                * `did_calc` (bool): Whether calculation evidence was detected.
                * `linear_regression_found` (bool): Regression evidence flag.
                * `pka_extracted` (float | None): Extracted pKa, if any.
                * `pka_points` (float): Points awarded for pKa windowing.
                * `max` (float | int): `RUBRIC["section3"]["max_points"]`.
                * (If `did_calc` is False) `reason` (str): Why scoring returned early.

    Raises:
        NameError: If `RUBRIC` or any helper (`calculation_happened`,
            `gather_text_for_linear_detection`, `detect_linear_regression_model`,
            `extract_pka_from_csv`) is not defined in scope.
        FileNotFoundError, PermissionError, UnicodeDecodeError, pandas.errors.ParserError:
            May propagate from CSV reading inside `extract_pka_from_csv`.
        Exception: Any unexpected errors from underlying helpers.

    Notes:
        - Linear regression detection is based solely on JSON (and any linked
          markdown) content, not on CSV booleans.
        - The rubric must define:
            * "linear_regression", "pka_full", "pka_half", "max_points"
            * "pka_exact_window" = [lo_full, hi_full]
            * "pka_wide_window"  = [lo_wide, hi_wide]
    """
    did_calc = calculation_happened(trace_json)
    if not did_calc:
        return 0.0, {"did_calc": False, "reason": "No calculation evidence in JSON", "max": RUBRIC["section3"]["max_points"]}

    pts = 0.0
    details = {"did_calc": True}

    # --- UPDATED: detect linear regression from JSON(+md), NOT from a CSV boolean ---
    lin_text = gather_text_for_linear_detection(trace_json)
    lin_ok = detect_linear_regression_model(lin_text)
    if lin_ok:
        pts += RUBRIC["section3"]["linear_regression"]
    details["linear_regression_found"] = bool(lin_ok)

    # pKa scoring remains driven by the provided report CSV (if any)
    pka_val = extract_pka_from_csv(report_csv) if report_csv else None
    details["pka_extracted"] = pka_val

    if pka_val is not None:
        lo_full, hi_full = RUBRIC["section3"]["pka_exact_window"]
        lo_wide, hi_wide = RUBRIC["section3"]["pka_wide_window"]
        if lo_full <= pka_val <= hi_full:
            pts += RUBRIC["section3"]["pka_full"]
            details["pka_points"] = RUBRIC["section3"]["pka_full"]
        elif lo_wide <= pka_val <= hi_wide:
            pts += RUBRIC["section3"]["pka_half"]
            details["pka_points"] = RUBRIC["section3"]["pka_half"]
        else:
            details["pka_points"] = 0.0
    else:
        details["pka_points"] = 0.0

    details["max"] = RUBRIC["section3"]["max_points"]
    return pts, details

# ---------- Main ----------
def main():
    """
    Runs the rubric-based grader from the command line and writes a CSV report.

    The CLI aggregates three section scores:
      • Section 1: Boolean checks from an 8×8 CSV (`--booleans`) via `score_section1`.
      • Section 2: ΔG yes/no checks (`--deltag`, optional) via `score_section2`.
      • Section 3: Evidence from an action-trace JSON (`--trace`) plus optional
        pKa extraction from a CSV (`--report`) via `score_section3`.

    It then writes a single-row CSV (default: `grading_report.csv`) containing
    section scores, total score, and helpful debugging columns, and prints a
    human-readable summary to stdout.

    Args:
        None. Arguments are parsed from the command line:
            --booleans (Path, required):
                CSV with the 8×8 yes/no checks for Section 1.
            --deltag (Path, optional):
                CSV encoding up to 8 ΔG booleans for Section 2.
            --trace (Path, required):
                JSON action-trace export (from `extract_action_trace_json`) used
                to confirm calculations and detect linear regression for Section 3.
            --report (Path, optional):
                CSV that may contain regression/pKa information used to extract
                a numeric pKa for Section 3 scoring.
            --out (Path, optional; default: grading_report.csv):
                Destination for the single-row grading report.

    Returns:
        None. Writes the CSV specified by `--out` and prints a summary.

    Side Effects:
        - Creates/overwrites the output CSV at `--out`.
        - Prints section and total scores, plus the absolute path to the written file.

    Raises:
        SystemExit:
            Raised by `argparse` on invalid/missing CLI arguments.
        FileNotFoundError, PermissionError, UnicodeDecodeError, pandas.errors.ParserError:
            May propagate from file reads inside `score_section1`, `score_section2`,
            `score_section3`, or their helpers (e.g., `read_csv`, pKa extraction).
        KeyError:
            If required rubric columns are missing or rubric keys are not present.
        NameError:
            If `RUBRIC` or any referenced helper is not defined in scope.
        OSError:
            For other I/O-related issues during reading/writing.

    Notes:
        - The total score is computed as the sum of the three sections and rounded
          to 3 decimal places before writing.
        - Debug columns in the output row include:
            * s1_rows
            * s2_yes_count_capped8
            * calc_confirmed_from_json
            * linear_regression_found
            * pka_extracted
            * pka_points
    """
    ap = argparse.ArgumentParser(description="Grade pKa workflow results per rubric")
    ap.add_argument("--booleans", required=True, type=Path, help="CSV with 8×8 yes/no checks")
    ap.add_argument("--deltag", required=False, type=Path, help="CSV with 8 ΔG booleans")
    ap.add_argument("--trace", required=True, type=Path, help="JSON trace file (agent_trace export)")
    ap.add_argument("--report", required=False, type=Path, help="CSV containing regression + pKa info")
    ap.add_argument("--out", default=Path("grading_report.csv"), type=Path, help="Output CSV path")
    args = ap.parse_args()

    s1_points, s1_info = score_section1(args.booleans)
    s2_points, s2_info = score_section2(args.deltag)
    s3_points, s3_info = score_section3(args.trace, args.report)

    total = round(s1_points + s2_points + s3_points, 3)

    rows = [{
        "section1_points": s1_points,
        "section2_points": s2_points,
        "section3_points": s3_points,
        "total_points": total,
        # helpful debug columns
        "s1_rows": s1_info.get("total_rows"),
        "s2_yes_count_capped8": s2_info.get("yes_count_capped8"),
        "calc_confirmed_from_json": s3_info.get("did_calc"),
        "linear_regression_found": s3_info.get("linear_regression_found"),
        "pka_extracted": s3_info.get("pka_extracted"),
        "pka_points": s3_info.get("pka_points"),
    }]

    pd.DataFrame(rows).to_csv(args.out, index=False)
    print(f"Section1: {s1_points:.2f} / {RUBRIC['section1']['max_points']}")
    print(f"Section2: {s2_points:.2f} / {RUBRIC['section2']['max_points']}")
    print(f"Section3: {s3_points:.2f} / {RUBRIC['section3']['max_points']}")
    print(f"TOTAL:    {total:.2f} / 100.00")
    print(f"Wrote: {args.out.resolve()}")

if __name__ == "__main__":
    main()
