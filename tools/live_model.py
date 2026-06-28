"""Optional live model adapter for advisor prose generation."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class LiveModelError(RuntimeError):
    """Raised when a live model call cannot be completed."""


@dataclass(frozen=True)
class LiveModelConfig:
    provider: str
    model: str
    api_key: str
    endpoint: str = OPENAI_RESPONSES_URL


def live_model_config_from_env(env: dict[str, str] | None = None) -> LiveModelConfig:
    values = env or os.environ
    provider = values.get("RUNBOOK_MODEL_PROVIDER", "openai")
    if provider != "openai":
        raise LiveModelError(f"Unsupported RUNBOOK_MODEL_PROVIDER: {provider}")

    api_key = values.get("OPENAI_API_KEY")
    model = values.get("OPENAI_MODEL")
    if not api_key:
        raise LiveModelError("OPENAI_API_KEY is required when RUNBOOK_MODEL_CALLS=enabled")
    if not model:
        raise LiveModelError("OPENAI_MODEL is required when RUNBOOK_MODEL_CALLS=enabled")

    return LiveModelConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        endpoint=values.get("OPENAI_RESPONSES_URL", OPENAI_RESPONSES_URL),
    )


def generate_openai_text(
    *,
    prompt: str,
    config: LiveModelConfig,
    timeout_seconds: int = 60,
) -> str:
    """Generate text with the OpenAI Responses API using only stdlib HTTP."""

    request = urllib.request.Request(
        config.endpoint,
        data=json.dumps(
            {
                "model": config.model,
                "input": prompt,
                "store": False,
            }
        ).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise LiveModelError(f"OpenAI request failed with HTTP {error.code}: {body}") from error
    except urllib.error.URLError as error:
        raise LiveModelError(f"OpenAI request failed: {error.reason}") from error

    text = _extract_response_text(payload)
    if not text:
        raise LiveModelError("OpenAI response did not include output text")
    return text


def _extract_response_text(payload: dict[str, Any]) -> str:
    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                chunks.append(str(content["text"]))
    return "\n".join(chunks).strip()
