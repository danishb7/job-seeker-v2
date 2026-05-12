"""Centralized configuration: environment and filesystem paths."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR: Path = Path(__file__).resolve().parent.parent
APP_DIR: Path = BASE_DIR / "app"
TEMPLATES_DIR: Path = APP_DIR / "templates"
STATIC_DIR: Path = APP_DIR / "static"
RESULTS_DIR: Path = BASE_DIR / "results"
PREFERENCES_PATH: Path = BASE_DIR / "job_requirements.md"


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")
TAVILY_SEARCH_DEPTH: str = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
TAVILY_MAX_RESULTS: int = _int_env("TAVILY_MAX_RESULTS", 6, 1)

MAX_OUTPUT_TOKENS: int = _int_env("MAX_OUTPUT_TOKENS", 4096, 256)
MAX_SEARCH_CALLS: int = _int_env("MAX_SEARCH_CALLS", 2, 1)
MAX_JOBS: int = _int_env("MAX_JOBS", 10, 1)
WHY_MATCH_MAX_CHARS: int = _int_env("WHY_MATCH_MAX_CHARS", 100, 20)

RESULTS_DIR.mkdir(parents=True, exist_ok=True)
