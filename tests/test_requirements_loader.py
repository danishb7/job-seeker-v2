from __future__ import annotations

from app import requirements_loader


def test_read_write_round_trip(tmp_path):
    path = tmp_path / "prefs.md"
    content = "# Job Search Preferences\n\n## Job Titles\n\nEngineer\n"
    requirements_loader.write_preferences(content, path)
    assert requirements_loader.read_preferences(path) == content


def test_read_for_agent_is_verbatim(tmp_path):
    path = tmp_path / "prefs.md"
    content = (
        "# Job Search Preferences\n\n"
        "> Intro line\n\n"
        "## Location\n\n"
        "- Charlotte NC\n"
    )
    path.write_text(content, encoding="utf-8")
    assert requirements_loader.read_for_agent(path) == content


def test_parse_search_domains_bullets():
    md = """## Search domains

- linkedin.com
- indeed.com
"""
    assert requirements_loader.parse_search_domains(md) == ["linkedin.com", "indeed.com"]


def test_parse_search_domains_inline():
    md = "## Search domains\n\nidealist.org, higheredjobs.com\n"
    assert set(requirements_loader.parse_search_domains(md)) == {"idealist.org", "higheredjobs.com"}


def test_parse_search_domains_missing_uses_defaults():
    md = "## Job Titles\n\nEngineer\n"
    assert requirements_loader.parse_search_domains(md) == list(requirements_loader.DEFAULT_SEARCH_DOMAINS)
