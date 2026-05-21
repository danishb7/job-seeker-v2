"""FastAPI application entrypoint and routes."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from . import agent, csv_writer, requirements_loader
from .config import GEMINI_MODEL, PREFERENCES_PATH, RESULTS_DIR, STATIC_DIR, TEMPLATES_DIR
from .schemas import PreferencesPayload

app = FastAPI(title="Job Seeker")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"model": GEMINI_MODEL, "preferences_path": str(PREFERENCES_PATH)},
    )


@app.get("/favicon.ico")
def favicon() -> RedirectResponse:
    return RedirectResponse(url="/static/favicon.svg", status_code=307)


@app.get("/api/preferences")
def get_preferences() -> dict[str, str]:
    return {"content": requirements_loader.read_preferences()}


@app.put("/api/preferences")
def put_preferences(payload: PreferencesPayload) -> dict[str, str]:
    requirements_loader.write_preferences(payload.content)
    return {"status": "ok"}


@app.post("/api/preferences/reload")
def reload_preferences() -> dict[str, str]:
    return {"content": requirements_loader.read_preferences()}


@app.post("/api/search")
def search() -> dict[str, object]:
    start = time.perf_counter()
    raw_prefs = requirements_loader.read_preferences()
    prefs_for_agent = requirements_loader.read_for_agent()
    include_domains = requirements_loader.parse_search_domains(raw_prefs)
    jobs = agent.search_jobs(prefs_for_agent, include_domains)
    csv_path = csv_writer.write_csv(jobs)
    elapsed = round(time.perf_counter() - start, 2)
    return {
        "jobs": jobs,
        "csv_filename": csv_path.name,
        "model": GEMINI_MODEL,
        "elapsed_seconds": elapsed,
    }


@app.get("/api/results")
def get_results() -> dict[str, object]:
    return {"results": csv_writer.list_results()}


@app.get("/api/results/{filename}")
def download_result(filename: str):
    if not filename or filename != Path(filename).name:
        raise HTTPException(status_code=400, detail="Invalid path.")
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid path.")
    if not filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed.")
    candidate = (RESULTS_DIR / filename).resolve()
    results_root = RESULTS_DIR.resolve()
    if candidate != results_root and results_root not in candidate.parents:
        raise HTTPException(status_code=400, detail="Invalid path.")
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(path=str(candidate), media_type="text/csv", filename=Path(filename).name)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": GEMINI_MODEL}
