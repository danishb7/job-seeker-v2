"""Read and write the user-editable job_requirements.md file."""
from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from .config import PREFERENCES_PATH

_SEARCH_DOMAINS_SECTION = re.compile(
    r"(?ms)^##\s+Search domains\s*$(.*?)(?=^##\s|\Z)",
)

# Whole line is comma/semicolon-separated hostnames only (legacy inline format).
_DOMAIN_ONLY_LINE = re.compile(
    r"^\s*(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.)+[a-z]{2,}"
    r"(?:\s*[,;]+\s*(?:[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.)+[a-z]{2,})*\s*$",
    re.I,
)

_UNRESTRICTED_MARKERS = frozenset({"unrestricted", "unlimited", "full web", "all"})


def read_preferences(path: Path = PREFERENCES_PATH) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def read_for_agent(path: Path = PREFERENCES_PATH) -> str:
    """Return preferences verbatim for the model (no stripping)."""
    return read_preferences(path)


def parse_search_domains(content: str) -> list[str] | None:
    """Parse Tavily ``include_domains`` from ``## Search domains``.

    Returns ``None`` when no hostname filter should be applied (broad search, closest to
    OpenAI web_search). Returns a non-empty list when the section lists hostnames.

    Hostnames are taken only from bullet lines (``-`` / ``*``) or from a legacy
    single line of comma-separated domains—not from free prose (so examples in sentences
    are not treated as filters).
    """
    text = content.replace("\r\n", "\n")
    match = _SEARCH_DOMAINS_SECTION.search(text)
    if not match:
        return None
    body = match.group(1).strip()
    if not body:
        return None

    found: list[str] = []

    def _consume_tokens(source: str) -> None:
        for token in re.split(r"[\s,;]+", source):
            token = token.strip("`\"'").strip().lower().rstrip("/")
            if not token:
                continue
            token = re.sub(r"^https?://", "", token)
            token = token.split("/")[0].split(":")[0]
            if "." in token and " " not in token:
                found.append(token)

    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- ") or line.startswith("* "):
            rest = line[2:].strip()
            low = rest.lower()
            if low in _UNRESTRICTED_MARKERS or low == "*":
                return None
            if low.startswith("tavily"):
                continue
            _consume_tokens(rest)
            continue

        if line.lower().startswith("tavily"):
            continue
        if not _DOMAIN_ONLY_LINE.match(line):
            continue
        _consume_tokens(line)

    return found if found else None


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
