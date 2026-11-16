from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIX = Path(__file__).parent / "fixtures"


@pytest.fixture
def fix() -> Path:
    return FIX


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / "data"


@pytest.fixture
def sample_dir(tmp_path: Path) -> Path:
    """A copy of the fixtures so sidecar discovery doesn't depend on the repo layout."""
    d = tmp_path / "in"
    d.mkdir()
    for f in ("sample.mp3", "sample.zh.srt", "sample.en.srt"):
        shutil.copy(FIX / f, d / f)
    return d
