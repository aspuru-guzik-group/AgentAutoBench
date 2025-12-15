import re

def deltaG_exists(text: str) -> bool:
    """
    Checks whether a Gibbs free energy value is reported in the output.

    Looks for several common headings that ORCA (and related tools) print when
    reporting Gibbs free energy, in a case-insensitive manner.

    Args:
        text (str): Full text of the ORCA output file.

    Returns:
        bool: True if a recognized Gibbs free-energy label is found; otherwise False.

    Raises:
        None.
    """
    pats = [
        r"Final\s+Gibbs\s+free\s+energy",
        r"GIBBS\s+FREE\s+ENERGY",
        r"Total\s+Gibbs\s+free\s+energy",
    ]
    return any(re.search(p, text, re.I) for p in pats)
