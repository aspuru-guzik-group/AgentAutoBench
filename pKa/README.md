Save these scripts into the final result folder that is generated from elagenteworkdir, and make sure to replace the root_dir into the corresponding root directory for the result folder

Run everything in the virtual environment to make sure that the MongoDB connection is successful. 

the rubric is like: 
'RUBRIC = {
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
}'

1. Run the General_Boolean.py first, to extract the 8 key properties from the ORCA input file and ORCA output file for each molecule, and save into a .csv file.

2. Run the pKa_deltaG_Boolean.py, to check the existence of the delta-G value in each molecule. 

3. Run the action&trace.py, which the extract_context.py is used as a helper funtion, to etract and generate the workflow, which would be used to verify the existence of calculation. 

4. Run the LLM_for_extraction.py, which use LLM to generate needed value from the final_report.md file, and save the context into a .csv file. 

5. Run the pKa_score_generator.py, which type following in the terminal:
     python pKa_score_generator.py \
  --booleans /absolute/path/booleans_8x8.csv \
  --deltag /absolute/path/deltag.csv \
  --trace /absolute/path/agent_trace.json \
  --report /absolute/path/pka_report.csv \
  --out /absolute/path/grading_report.csv
(make sure to replace the absolute file path in the corrsponding sections), and it will generate the final score for the benchmarking. 
