from pathlib import Path

import pytest

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


@pytest.fixture
def raw_pdfs() -> list[Path]:
    """Real statements on the developer machine; skipped everywhere else."""
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        pytest.skip("no statements in data/raw")
    return pdfs
