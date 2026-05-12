from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_prefs_file(tmp_path: Path) -> Path:
    path = tmp_path / "job_requirements.md"
    path.write_text("# Job Search Preferences\n\n## Job Titles\n\nBackend Engineer\n", encoding="utf-8")
    return path
