"""Gemini tool-calling agent for job search (Tavily-backed web_search)."""
from __future__ import annotations

import json
from typing import Any

from google.genai import types

from .config import (
    MAX_JOBS,
    MAX_OUTPUT_TOKENS,
    MAX_SEARCH_CALLS,
    WHY_MATCH_MAX_CHARS,
)
from . import gemini_client
from .search_provider import tavily_search

# DO NOT EDIT casually: stable prefix helps provider-side prompt caching behavior.
SYSTEM_PROMPT = (
    "You find currently-open US job postings matching the user's preferences (Markdown).\n"
    "Rules:\n"
    f"- Call web_search at most {MAX_SEARCH_CALLS} times; combine keywords per query.\n"
    "- The USER PREFERENCES block is authoritative: follow Location, Search domains, "
    "Visa requirements, Work mode, Salary, Company type, Must-Have, Nice-to-Have, and Exclude exactly.\n"
    "- Honor Must-Have / Exclude strictly.\n"
    f"- Return up to {MAX_JOBS} matches, best-ranked first. Use null for unknown fields.\n"
    f'- "why_match": one sentence, <= {WHY_MATCH_MAX_CHARS} chars.\n'
    "- Web search results are already restricted to the hostnames listed under ## Search domains."
)

_WEB_SEARCH_DECLARATION = types.FunctionDeclaration(
    name="web_search",
    description="Search the live web for job postings (results are limited to domains in user preferences).",
    parameters_json_schema={
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
        "additionalProperties": False,
    },
)

_TOOL = types.Tool(function_declarations=[_WEB_SEARCH_DECLARATION])

# Gemini JSON schema subset: avoid OpenAI-only wrappers; nullable via anyOf where needed.
JOB_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "jobs": {
            "type": "array",
            "maxItems": MAX_JOBS,
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "company": {"type": "string"},
                    "location": {"type": "string"},
                    "work_mode": {"type": "string"},
                    "salary": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "is_nonprofit_or_h1b_cap_exempt": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                    "why_match": {"type": "string", "maxLength": WHY_MATCH_MAX_CHARS},
                    "posted": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                    "url": {"type": "string"},
                    "source": {"type": "string"},
                },
                "required": ["title", "company", "url"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["jobs"],
    "additionalProperties": False,
}


def _normalise_jobs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = payload.get("jobs", [])
    if not isinstance(jobs, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for job in jobs[:MAX_JOBS]:
        if not isinstance(job, dict):
            continue
        cleaned.append(
            {
                "title": str(job.get("title", "")),
                "company": str(job.get("company", "")),
                "location": str(job.get("location", "")),
                "work_mode": str(job.get("work_mode", "")),
                "salary": job.get("salary"),
                "is_nonprofit_or_h1b_cap_exempt": job.get("is_nonprofit_or_h1b_cap_exempt"),
                "why_match": str(job.get("why_match", ""))[:WHY_MATCH_MAX_CHARS],
                "posted": job.get("posted"),
                "url": str(job.get("url", "")),
                "source": str(job.get("source", "")),
            }
        )
    return cleaned


def _tool_phase_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[_TOOL],
        max_output_tokens=MAX_OUTPUT_TOKENS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _final_phase_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        response_json_schema=JOB_JSON_SCHEMA,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _parse_job_payload(resp: Any) -> dict[str, Any] | None:
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    text = getattr(resp, "text", None) or ""
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def search_jobs(prefs_md_for_agent: str, include_domains: list[str]) -> list[dict[str, Any]]:
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"USER PREFERENCES:\n\n{prefs_md_for_agent}")],
        )
    ]
    searches_used = 0
    nudged_without_tools = False

    for _ in range(MAX_SEARCH_CALLS + 3):
        if searches_used >= MAX_SEARCH_CALLS:
            break
        resp = gemini_client.generate_content(contents=contents, config=_tool_phase_config())
        if not resp.candidates or not resp.candidates[0].content:
            break
        calls = resp.function_calls
        if calls:
            contents.append(resp.candidates[0].content)
            response_parts: list[types.Part] = []
            for fc in calls:
                if fc.name != "web_search" or searches_used >= MAX_SEARCH_CALLS:
                    continue
                args = fc.args or {}
                query = str(args.get("query", "")).strip()
                results = tavily_search(query, include_domains=include_domains) if query else []
                fr = types.FunctionResponse(
                    id=fc.id,
                    name="web_search",
                    response={"results": results},
                )
                response_parts.append(types.Part(function_response=fr))
                searches_used += 1
            if not response_parts:
                break
            contents.append(types.Content(role="user", parts=response_parts))
            continue
        if not nudged_without_tools:
            nudged_without_tools = True
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=(
                                "You must call the web_search tool with a single combined query "
                                f"(you may still use at most {MAX_SEARCH_CALLS} total searches)."
                            )
                        )
                    ],
                )
            )
            continue
        break

    final = gemini_client.generate_content(contents=contents, config=_final_phase_config())
    payload = _parse_job_payload(final)
    if not payload:
        return []
    return _normalise_jobs(payload)
