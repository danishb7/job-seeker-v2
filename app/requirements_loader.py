"""Read and write the user-editable job_requirements.md file."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from .config import PREFERENCES_PATH

# Used when ## Search domains is missing or empty (Tavily include_domains).
DEFAULT_SEARCH_DOMAINS: list[str] = [
    "linkedin.com",
    "indeed.com",
    "idealist.org",
    "higheredjobs.com",
]

_SEARCH_DOMAINS_SECTION = re.compile(
    r"(?ms)^##\s+Search domains\s*$(.*?)(?=^##\s|\Z)",
)


def read_preferences(path: Path = PREFERENCES_PATH) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_for_agent(path: Path = PREFERENCES_PATH) -> str:
    """Return preferences verbatim for the model (no stripping)."""
    return read_preferences(path)


def parse_search_domains(content: str) -> list[str]:
    """Parse hostnames from the ## Search domains section; bullets or comma-separated."""
    text = content.replace("\r\n", "\n")
    match = _SEARCH_DOMAINS_SECTION.search(text)
    if not match:
        return list(DEFAULT_SEARCH_DOMAINS)
    body = match.group(1).strip()
    if not body:
        return list(DEFAULT_SEARCH_DOMAINS)
    found: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        elif line.startswith("* "):
            line = line[2:].strip()
        if not line or line.lower().startswith("tavily"):
            continue
        for token in re.split(r"[\s,;]+", line):
            token = token.strip().lower().rstrip("/")
            if not token:
                continue
            token = re.sub(r"^https?://", "", token)
            token = token.split("/")[0].split(":")[0]
            if "." in token and " " not in token:
                found.append(token)
    return found or list(DEFAULT_SEARCH_DOMAINS)


def write_preferences(content: str, path: Path = PREFERENCES_PATH) -> None:
    stripped = content.strip()
    if not stripped:
        raise ValueError("Refusing to save empty preferences.")

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix=".job_requirements_", suffix=".md.tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content if content.endswith("\n") else content + "\n")
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
