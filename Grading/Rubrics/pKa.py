# Auto_benchmark/Grading/Rubrics/pKa.py

RUBRIC_PKA = {
    "metadata": {
        "name": "pKa",
        "version": "2.0",
        "n_molecules": 8,
        "total_max_points": 100.0,  # 76 (boolean) + 24 (numerical)
    },

    # -------------------------------------------
    # BOOLEAN (Inputs/QC per molecule + ΔG flags)
    # -------------------------------------------
    "boolean": {
        "label": "Inputs & QC + ΔG availability",
        "sections": {
            # 8 molecules × 8 checks = 64
            "input_qc": {
                "columns": [
                    "Method exist?",
                    "Basis set exist?",
                    "Tasks exist?",
                    "Charge & mult exist?",
                    "XYZ file exist?",
                    "SCF converged?",
                    "Geo opt converged?",
                    "Imag freq exist?",         # award on "no"
                ],
                # scoring rules
                "yes_score": 1.0,              # first 7 columns → award on YES
                "imag_no_score": 1.0,          # 8th column → award on NO
                "max_points": 64.0,
            },

            # 8 ΔG booleans × 1.5 = 12
            "delta_g": {
                "n_items": 8,                  # cap rows at 8
                "per_yes": 1.5,                # points per truthy ΔG row
                "max_points": 12.0,
            },
        },
        "total": 76.0,  # 64 + 12
    },

    # -------------------------------------------
    # NUMERICAL (Model + pKa windowing)
    # -------------------------------------------
    "numerical": {
        "label": "pKa model & result",
        "criteria": {
            # Presence of linear regression model
            "linear_regression": {
                "type": "presence",
                "weight": 12.0,               # full credit if present
            },
            # pKa windowing (mutually exclusive)
            "pka_value": {
                "type": "window",
                "full": {"min": 1.4, "max": 1.6, "award": 12.0},
                "half": {"min": 1.2, "max": 1.8, "award": 6.0},
            },
        },
        "total": 24.0,
    },
}

# Back-compat export name used elsewhere in the codebase
RUBRIC = RUBRIC_PKA
