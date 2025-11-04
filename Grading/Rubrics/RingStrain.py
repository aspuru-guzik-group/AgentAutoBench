# Auto_benchmark/Grading/Rubrics/RingStrain.py

RUBRIC_RINGSTRAIN = {
    "metadata": {
        "name": "RingStrain",
        "version": "1.1",
        "n_molecules": 11,
        "total_max_points": 100.0,  # 44 (boolean) + 8 (reference) + 48 (numerical)
    },

    # ---------------------------------------------------------------
    # BOOLEAN (Inputs/QC per molecule)
    #  - 11 molecules × 8 checks × 0.5 pt = 44.0
    #  - Imaginary frequency check awards on "NO" (no imag freqs)
    # ---------------------------------------------------------------
    "boolean": {
        "label": "Inputs & QC per molecule",
        "sections": {
            "input_qc": {
                "columns": [
                    "Method exist?",
                    "Basis set exist?",
                    "Tasks exist?",
                    "Charge & mult exist?",
                    "XYZ file exist?",
                    "SCF converged?",
                    "Geo opt converged?",
                    "Imag freq exist?",           # award on NO
                ],
                "yes_score": 0.5,                # first 7 columns → award on YES
                "imag_no_score": 0.5,            # 8th column → award on NO
                "n_molecules": 11,
                "max_points": 44.0,
            },
        },
        "total": 44.0,
    },

    # ---------------------------------------------------------------
    # REFERENCE POINT (from report.md)
    #  - Full credit only when cyclohexane is the stated reference
    # ---------------------------------------------------------------
    "reference_point": {
        "label": "Reference point correctness",
        "rule": {
            "key": "reference_is_cyclohexane",  # boolean from LLM extractor
            "true_award": 8.0,
            "false_award": 0.0,
        },
        "total": 8.0,
    },

    # ---------------------------------------------------------------
    # NUMERICAL (Ring strain ΔH and ΔG in kcal/mol)
    #  - 12 total values: 6 ΔH + 6 ΔG
    #  - 4 points each = 48 points total
    #  - Scoring: full if |error| ≤ abs_tol_full; half if ≤ abs_tol_half; else 0
    # ---------------------------------------------------------------
    "numerical": {
        "label": "Strain energies (kcal/mol)",
        "config": {
            # Which ring sizes to score (must match ground-truth/tool output)
            "ring_sizes_for_scoring": [3, 4, 5, 6, 7, 8],

            # Absolute tolerances
            "abs_tol_full": 0.20,   # full credit if |err| ≤ 0.20 kcal/mol
            "abs_tol_half": 0.50,   # half credit if 0.20 < |err| ≤ 0.50

            # Points per item
            "per_item_points": 4.0,

            # Keys expected in ground-truth vs LLM outputs
            "keys": {
                "delta_h": "strain_delta_H_kcal_mol",
                "delta_g": "strain_delta_G_kcal_mol",
            },
        },
        "total": 48.0,
    },
}

# Back-compat export name used elsewhere in the codebase
RUBRIC = RUBRIC_RINGSTRAIN
