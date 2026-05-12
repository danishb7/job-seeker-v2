from __future__ import annotations

from fastapi.testclient import TestClient

from app import main


def test_get_root():
    client = TestClient(main.app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Job Seeker" in resp.text


def test_preferences_round_trip(tmp_path, monkeypatch):
    prefs = tmp_path / "job_requirements.md"
    monkeypatch.setattr(main.requirements_loader, "PREFERENCES_PATH", prefs, raising=False)
    client = TestClient(main.app)
    put = client.put("/api/preferences", json={"content": "## Job Titles\n\nEngineer\n"})
    assert put.status_code == 200
    get = client.get("/api/preferences")
    assert "Engineer" in get.json()["content"]


def test_search_endpoint(monkeypatch, tmp_path):
    client = TestClient(main.app)
    monkeypatch.setattr(main.requirements_loader, "read_for_agent", lambda: "prefs")
    monkeypatch.setattr(main.agent, "search_jobs", lambda _prefs, _domains: [{"title": "x", "company": "y", "url": "https://z"}])
    monkeypatch.setattr(main.csv_writer, "write_csv", lambda jobs: tmp_path / "jobs_20260101_010101.csv")
    resp = client.post("/api/search")
    assert resp.status_code == 200
    assert resp.json()["csv_filename"].endswith(".csv")


def test_csv_download_path_traversal_rejected():
    client = TestClient(main.app)
    resp = client.get("/api/results/..%5Csecrets.csv")
    assert resp.status_code == 400
