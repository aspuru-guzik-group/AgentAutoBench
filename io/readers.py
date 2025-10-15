from __future__ import annotations
from pathlib import Path

def read_text_safe(p: Path) -> str:
    """Read UTF-8 text with errors ignored; return empty string on failure.

    Keeps the callers free from try/except noise while safely reading a wide
    range of ORCA outputs with mixed encodings.
    """
    try:
        return p.read_text(errors="ignore")
    except Exception:
        return ""