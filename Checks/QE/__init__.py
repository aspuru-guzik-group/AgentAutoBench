# ---------------- QE solid-state input checks ----------------
from .solido_Q1_input import (  # noqa: F401
    calculation_is_scf,
    a_exists,
    nat_exists,
    ecutwfc_matches_target,
    occupation_is_smearing,
    smearing_is_mv,
    degauss_is_0p01,
    starting_magnetization_is_5,
    cell_parameters_exist,
    atomic_species_exist,
    atomic_positions_match_nat,
    kpoints_automatic_valid,
    valid_namelists_exist,
)

# ---------------- QE solid-state output checks ----------------
from .solido_Q1_output import (  # noqa: F401
    job_done,
    scf_converged,
    final_total_energy_present,
)
