# 🧪 Auto_benchmark

Following the architecture of automated scientific workflows, **Auto_benchmark** provides a modular and extensible system for running, grading, and verifying computational chemistry benchmarks.

The system handles input discovery, output parsing, data extraction, grading logic, and final report generation.  
Each benchmark case can be executed automatically and summarized into standardized tables or JSON reports.

---

## Overview

Auto_benchmark is designed to streamline and standardize computational benchmarking tasks such as molecular property prediction, thermochemical validation, or spectroscopic calibration.

The system consists of several modular components:

| Module | Role |
|--------|------|
| **Checks** | Perform validation and consistency checks on computed results |
| **Client** | Command-line interface and execution controller |
| **Config** | Environment defaults, regex patterns, and path configuration |
| **Extractors** | Parse output files and extract target quantities |
| **Grading** | Benchmark grading and reference comparison |
| **io** | Input/output management, file handling, and serialization |
| **registry** | Registry of available benchmark cases |
| **Verify** | Final verification and report consolidation |

---

## Use Case

Typical applications include:
- Automated quantum chemistry benchmarking  
- Workflow validation for research pipelines  
- Batch evaluation of computational methods or parameters  

Each case runs independently and outputs structured JSON and CSV summaries suitable for downstream analysis.
