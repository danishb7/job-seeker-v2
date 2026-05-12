"""Google Gen AI client wrapper (test seam + retries)."""
from __future__ import annotations

import time
from typing import Any

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from . import config as app_config

_client: genai.Client | None = None


def get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=app_config.GEMINI_API_KEY or "missing-key")
    return _client


def generate_content(
    *,
    contents: list[types.Content],
    config: types.GenerateContentConfig,
) -> Any:
    """Call Gemini generate_content with one retry on transient API errors."""
    client = get_client()
    last_exc: BaseException | None = None
    for attempt in range(2):
        try:
            return client.models.generate_content(
                model=app_config.GEMINI_MODEL, contents=contents, config=config
            )
        except (genai_errors.ClientError, genai_errors.ServerError) as exc:
            last_exc = exc
            if attempt == 1:
                raise
            time.sleep(0.5 * (2**attempt))
    raise last_exc or RuntimeError("Unreachable")
