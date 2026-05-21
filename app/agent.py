"""Gemini tool-calling agent for job search (Tavily-backed web_search)."""
from __future__ import annotations

import json
import logging
import re
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

logger = logging.getLogger(__name__)

# DO NOT EDIT casually: stable prefix helps provider-side prompt caching behavior.
_SYSTEM_PROMPT_BASE = (
    "You find currently-open US job postings matching the user's preferences (Markdown).\n"
    "Rules:\n"
    f"- Call web_search at most {MAX_SEARCH_CALLS} times; combine keywords per query.\n"
    "- Keep each web_search query SHORT (under 350 characters): job keywords + location + one constraint.\n"
    "- The USER PREFERENCES block is authoritative: follow Location, Search domains, "
    "Visa requirements, Work mode, Salary, Company type, Must-Have, Nice-to-Have, and Exclude exactly.\n"
    "- Honor Must-Have / Exclude strictly.\n"
    "- If web_search snippets list plausible postings, include them when they fit Must-Have / Exclude. "
    "Use snippet URLs as posting links when they point at job pages.\n"
    f"- Return up to {MAX_JOBS} matches, best-ranked first. Use null for unknown fields.\n"
    f'- "why_match": one sentence, <= {WHY_MATCH_MAX_CHARS} chars.\n'
)


def _system_instruction(include_domains: list[str] | None) -> str:
    if include_domains:
        suffix = (
            "- Web search results are limited to these hostnames (from ## Search domains): "
            + ", ".join(include_domains)
            + "."
        )
    else:
        suffix = (
            "- Web search is not limited to specific sites (no hostname filter). Prefer reputable job boards "
            "and employer career sites when choosing URLs."
        )
    return _SYSTEM_PROMPT_BASE + suffix

_FALLBACK_NUDGE = (
    "Produce the final answer now as JSON only. "
    'Use the web_search snippets above; each job must include "title", "company", and "url" from those results '
    "when possible. If no snippet plausibly matches Must-Have and Exclude, return {\"jobs\": []}."
)

_WEB_SEARCH_DECLARATION = types.FunctionDeclaration(
    name="web_search",
    description=(
        "Search the live web for job postings via Tavily. "
        "If USER PREFERENCES list hostnames under ## Search domains, results are filtered to those sites; "
        "otherwise search is unrestricted."
    ),
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
                    "why_match": {"type": "string"},
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


def _tool_phase_config(include_domains: list[str] | None) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=_system_instruction(include_domains),
        tools=[_TOOL],
        max_output_tokens=MAX_OUTPUT_TOKENS,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _final_phase_config(include_domains: list[str] | None) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=_system_instruction(include_domains),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        response_json_schema=JOB_JSON_SCHEMA,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _final_fallback_config(include_domains: list[str] | None) -> types.GenerateContentConfig:
    """Looser JSON mode when strict schema parse fails (no json_schema — MIME JSON only)."""
    return types.GenerateContentConfig(
        system_instruction=_system_instruction(include_domains),
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def _extract_json_object(text: str) -> dict[str, Any] | None:
    raw = (text or "").strip()
    if not raw:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw)
    if fence:
        raw = fence.group(1).strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        pass
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(raw)):
        if raw[i] == "{":
            depth += 1
        elif raw[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(raw[start : i + 1])
                    return obj if isinstance(obj, dict) else None
                except json.JSONDecodeError:
                    return None
    return None


def _parse_job_payload(resp: Any) -> dict[str, Any] | None:
    parsed = getattr(resp, "parsed", None)
    if isinstance(parsed, dict):
        return parsed
    text = getattr(resp, "text", None) or ""
    extracted = _extract_json_object(text)
    if extracted is not None:
        return extracted
    return None


def _log_response_issue(where: str, resp: Any) -> None:
    try:
        pf = getattr(resp, "prompt_feedback", None)
        if pf is not None:
            logger.warning("%s prompt_feedback=%s", where, pf)
        cands = getattr(resp, "candidates", None) or []
        if not cands:
            logger.warning("%s no candidates", where)
            return
        fr = getattr(cands[0], "finish_reason", None)
        if fr is not None:
            logger.warning("%s finish_reason=%s", where, fr)
    except Exception:
        logger.warning("%s could not inspect response", where)


def search_jobs(prefs_md_for_agent: str, include_domains: list[str] | None) -> list[dict[str, Any]]:
    contents: list[types.Content] = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"USER PREFERENCES:\n\n{prefs_md_for_agent}")],
        )
    ]
    searches_used = 0
    nudged_without_tools = False
    tool_empty_retries = 0

    for _ in range(MAX_SEARCH_CALLS + 5):
        if searches_used >= MAX_SEARCH_CALLS:
            break
        resp = gemini_client.generate_content(contents=contents, config=_tool_phase_config(include_domains))
        if not resp.candidates or not resp.candidates[0].content:
            _log_response_issue("tool_phase", resp)
            if tool_empty_retries >= 1:
                break
            tool_empty_retries += 1
            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text="Your previous reply had no usable content. "
                            "Call web_search once with one short query string for job postings."
                        )
                    ],
                )
            )
            continue
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

    final = gemini_client.generate_content(contents=contents, config=_final_phase_config(include_domains))
    payload = _parse_job_payload(final)
    if payload is None:
        _log_response_issue("final_strict", final)
        contents.append(types.Content(role="user", parts=[types.Part.from_text(text=_FALLBACK_NUDGE)]))
        final = gemini_client.generate_content(contents=contents, config=_final_fallback_config(include_domains))
        payload = _parse_job_payload(final)
        if payload is None:
            _log_response_issue("final_fallback", final)

    if not payload:
        return []
    return _normalise_jobs(payload)
