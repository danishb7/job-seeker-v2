"""Pydantic models for API payloads."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Job(BaseModel):
    title: str = ""
    company: str = ""
    location: str = ""
    work_mode: str = ""
    salary: Optional[str] = None
    is_nonprofit_or_h1b_cap_exempt: Optional[bool] = None
    why_match: str = ""
    posted: Optional[str] = None
    url: str = ""
    source: str = ""


class SearchResponse(BaseModel):
    jobs: list[Job] = Field(default_factory=list)
    csv_filename: Optional[str] = None
    model: str = ""
    elapsed_seconds: float = 0.0


class PreferencesPayload(BaseModel):
    content: str


class ResultFileInfo(BaseModel):
    filename: str
    created_at: str
    rows: int
    size_bytes: int
