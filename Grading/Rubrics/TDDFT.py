RUBRIC_TDDFT = {
    # Boolean sections = 51 pts total
    "boolean": {
        # 1) Input (5 checks × 3 pts × 2 inputs = 30)
        "input": {
            "columns": [
                "Method exist?",
                "Basis set exist?",
                "Tasks exist?",
                "Charge & mult exist?",
                "XYZ file exist?",
            ],
            "yes_score": 3.0,
            "multiplicity": 2,          # two input files per folder
            "max_points": 30.0,
        },
        # 2) Common output (SCF × 2 outputs = 6)
        "common_output": {
            "columns": ["SCF converged?"],
            "yes_score": 3.0,
            "multiplicity": 2,          # SCF checked on OPT + TDDFT outputs
            "max_points": 6.0,
        },
        # 3) Optimization output (Geo opt + Imag freq = 6)
        "opt_output": {
            "columns_yes": ["Geo opt converged?"],  # award on "yes"
            "columns_no":  ["Imag freq exist?"],    # award when value == "no"
            "yes_score": 3.0,
            "no_score":  3.0,
            "max_points": 6.0,
        },
        # 4) TDDFT output (block + energy + f = 9)
        "tddft_output": {
            "columns": [
                "TDDFT block executed?",
                "Excitation energy exist?",
                "Oscillator strengths available?",
            ],
            "yes_score": 3.0,
            "max_points": 9.0,
        },
        "total": 51.0,
    },

    # Numerical section = 49 pts total, tiered by relative error
    "numerical": {
        "criteria": {
            "S1_energy_eV": {
                "weight": 15.0,
                "full_rel": 0.10,   # <=10% → full
                "half_rel": 0.20,   # <=20% → half
                "require_json_proof": False,
            },
            "S1_T1_gap_eV": {
                "weight": 15.0,
                "full_rel": 0.10,
                "half_rel": 0.20,
                "require_json_proof": True,  # gate on agent’s JSON showing calc was done
            },
            "S1_oscillator_strength": {
                "weight": 19.0,
                "full_rel": 0.10,
                "half_rel": 0.20,
                "require_json_proof": False,
            },
        },
        "total": 49.0,
    },

    # overall
    "total_points": 100.0,
}
