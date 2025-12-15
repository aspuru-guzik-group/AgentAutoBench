"""Convenience imports for the checks package.

This module re-exports the most commonly used input and output checks so you
can import them succinctly, e.g.::

    from auto_bench.checks import (
        method_exist, basis_exist, tasks_exist, charge_mult_exist, xyz_exist,
        scf_converged,
        check_output_opt,
        tddft_block_executed, excitation_energy_exist, oscillator_strengths_available,
        check_output_tddft,
        extract_orca_task,
        mulliken_exist, hirshfeld_exist, loewdin_exist,
    )

If you prefer per-module imports, you can always import from the concrete
modules (input_checks, output_common, output_opt, output_tddft, fukui_input, fukui_output).
"""

# Input checks
from .input_checks import (  # noqa: F401
    method_exist,
    basis_exist,
    tasks_exist,
    charge_mult_exist,
    xyz_exist,
)

# Input checks for el agente_v2 (The Standard Trio)
from .input_checks_v2 import (  # noqa: F401
    check_input_exists,
    extract_orca_task,
    verify_structure,
)

# Output common (applies to all job types)
from .output_common import (  # noqa: F401
    scf_converged,
)

# Geometry optimization–specific outputs (wrapper only, per latest design)
from .output_opt import (  # noqa: F401
    check_output_opt,
)

# TDDFT-specific outputs
from .output_TDDFT import (  # noqa: F401
    tddft_block_executed,
    excitation_energy_exist,
    oscillator_strengths_available,
    check_output_tddft,
)

# Fukui-specific checks
from .output_fukui import (  # noqa: F401
    mulliken_exist,
    hirshfeld_exist,
    loewdin_exist,
)
