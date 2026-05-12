from __future__ import annotations

import json

from google.genai import types

from app import agent, gemini_client


def _tool_response() -> types.GenerateContentResponse:
    fc = types.FunctionCall(name="web_search", args={"query": "python jobs"})
    part = types.Part(function_call=fc)
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def _final_response() -> types.GenerateContentResponse:
    payload = {"jobs": [{"title": "A", "company": "B", "url": "https://x"}]}
    text = json.dumps(payload)
    part = types.Part(text=text)
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)], parsed=payload)


def test_tool_loop_then_final_json(monkeypatch):
    calls: list[types.GenerateContentConfig] = []

    def fake_generate(*, contents, config):
        calls.append(config)
        if config.tools:
            return _tool_response()
        return _final_response()

    monkeypatch.setattr(gemini_client, "generate_content", fake_generate)
    monkeypatch.setattr(agent, "tavily_search", lambda q, include_domains=None: [{"title": "r", "url": "u", "snippet": "s"}])
    jobs = agent.search_jobs("prefs", ["example.com"])
    assert len(jobs) == 1
    assert calls[-1].response_mime_type == "application/json"
    assert calls[-1].response_json_schema is not None
    assert calls[-1].max_output_tokens == agent.MAX_OUTPUT_TOKENS
    assert calls[-1].tools is None


def test_final_phase_has_structured_output(monkeypatch):
    calls: list[types.GenerateContentConfig] = []

    def fake_generate(*, contents, config):
        calls.append(config)
        if config.tools:
            return _tool_response()
        return types.GenerateContentResponse(
            candidates=[types.Candidate(content=types.Content(role="model", parts=[]))],
            parsed={"jobs": []},
        )

    monkeypatch.setattr(gemini_client, "generate_content", fake_generate)
    monkeypatch.setattr(agent, "tavily_search", lambda q, include_domains=None: [])
    agent.search_jobs("prefs", ["example.com"])
    assert any(c.response_mime_type == "application/json" for c in calls)
