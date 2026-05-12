from __future__ import annotations

import importlib

from app import config


def test_env_defaults(monkeypatch):
    monkeypatch.delenv("MAX_SEARCH_CALLS", raising=False)
    monkeypatch.delenv("MAX_OUTPUT_TOKENS", raising=False)
    monkeypatch.delenv("WHY_MATCH_MAX_CHARS", raising=False)
    importlib.reload(config)
    assert config.MAX_SEARCH_CALLS == 2
    assert config.MAX_OUTPUT_TOKENS == 4096
    assert config.WHY_MATCH_MAX_CHARS == 100


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("MAX_SEARCH_CALLS", "5")
    monkeypatch.setenv("MAX_OUTPUT_TOKENS", "3000")
    monkeypatch.setenv("WHY_MATCH_MAX_CHARS", "80")
    importlib.reload(config)
    assert config.MAX_SEARCH_CALLS == 5
    assert config.MAX_OUTPUT_TOKENS == 3000
    assert config.WHY_MATCH_MAX_CHARS == 80


def test_gemini_model_default(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-2.5-flash"


def test_gemini_model_override(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-2.0-flash")
    importlib.reload(config)
    assert config.GEMINI_MODEL == "gemini-2.0-flash"
