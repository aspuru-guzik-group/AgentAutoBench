"""
Rubric configuration for the Fukui Index benchmark job.

Defines the scoring criteria for boolean checks (Input/Output validity)
and numerical accuracy (Condensed Fukui Functions).
"""

RUBRIC_FUKUI = {
    "metadata": {
        "name": "Fukui",
        "version": "1.0",
        "level": "Medium",
        "description": "Condensed Fukui functions (f+, f-) for Toluene using Finite Difference (N, N+1, N-1).",
        "total_max_points": 100.0,
    },

    # ============================================================
    # BOOLEAN CHECKS (60% Total)
    # ============================================================
    "boolean": {
        "label": "Input & Output Configuration",
        "sections": {
            # --------------------------------------------------------
            # 1. Checking Input (30%)
            # - 4 files (OPT, Anion, Neutral, Cation)
            # - 3 checks per file (Exist, Task Match, Structure Valid)
            # - Total 12 checks. 30 pts / 12 = 2.5 pts each.
            # --------------------------------------------------------
            "input_files": {
                "columns": [
                    "OPT_input_exist?",
                    "OPT_task_match?",
                    "OPT_structure_valid?",
                    "Anion_input_exist?",
                    "Anion_task_match?",
                    "Anion_structure_valid?",
                    "Neutral_input_exist?",
                    "Neutral_task_match?",
                    "Neutral_structure_valid?",
                    "Cation_input_exist?",
                    "Cation_task_match?",
                    "Cation_structure_valid?",
                ],
                "yes_score": 2.5,
                "max_points": 30.0,
            },

            # --------------------------------------------------------
            # 2. Checking Output (30%)
            # A) OPT Output (3%)
            #    - SCF converged, Geo converged, No imag freq. (1 pt each)
            # --------------------------------------------------------
            "opt_output": {
                "columns": [
                    "OPT_SCF_converged?",
                    "OPT_geo_opt_converged?",
                    "OPT_imag_freq_not_exist?",  # Award on "Yes"
                ],
                "yes_score": 1.0,
                "max_points": 3.0,
            },

            # --------------------------------------------------------
            # 2. Checking Output (30%)
            # B) SP Outputs (27%)
            #    - 3 files (Anion, Neutral, Cation)
            #    - 4 checks each (SCF + 3 populations)
            #    - Total 12 checks. 27 pts / 12 = 2.25 pts each.
            # --------------------------------------------------------
            "sp_populations": {
                "columns": [
                    # Neutral
                    "Neutral_SCF_converged?",
                    "Neutral_Mulliken_exist?",
                    "Neutral_Hirshfeld_exist?",
                    "Neutral_Loewdin_exist?",
                    # Anion
                    "Anion_SCF_converged?",
                    "Anion_Mulliken_exist?",
                    "Anion_Hirshfeld_exist?",
                    "Anion_Loewdin_exist?",
                    # Cation
                    "Cation_SCF_converged?",
                    "Cation_Mulliken_exist?",
                    "Cation_Hirshfeld_exist?",
                    "Cation_Loewdin_exist?",
                ],
                "yes_score": 2.25,
                "max_points": 27.0,
            },
        },
        "total": 60.0,
    },

    # ============================================================
    # NUMERICAL CHECKS (40% Total)
    # ============================================================
    "numerical": {
        "label": "Condensed Fukui Indices Accuracy",
        "criteria": {
            # --- Mulliken ---
            "f_plus_Mulliken": {
                "weight": 6.67,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
            "f_minus_Mulliken": {
                "weight": 6.67,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
            # --- Hirshfeld ---
            "f_plus_Hirshfeld": {
                "weight": 6.67,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
            "f_minus_Hirshfeld": {
                "weight": 6.67,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
            # --- Loewdin ---
            "f_plus_Loewdin": {
                "weight": 6.66,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
            "f_minus_Loewdin": {
                "weight": 6.66,
                "full_rel": 0.10,
                "half_rel": 0.20,
            },
        },
        "total": 40.0,
    },
}

RUBRIC = RUBRIC_FUKUI