"""Thin wrapper around the Anthropic SDK used by every builder stage."""
from __future__ import annotations

import os
from typing import Type, TypeVar

import anthropic
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

# Builder-side reasoning (extraction, compilation, optimisation) — the most capable default.
BUILDER_MODEL = os.getenv("BUILDER_MODEL", "claude-opus-5-5")
# Cheap, fast model for simulated customers and bulk judging.
SIM_MODEL = os.getenv("SIM_MODEL", "claude-sonnet-5-5")

_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(max_retries=4)
    return _client


def parse(
    schema: Type[T],
    system: str,
    user: str,
    *,
    model: str = BUILDER_MODEL,
    effort: str = "high",
    max_tokens: int = 32000,
) -> T:
    """Structured call: returns a validated pydantic instance."""
    resp = client().messages.parse(
        model=model,
        max_tokens=max_tokens,
        thinking={"type": "adaptive"},
        output_config={"effort": effort},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {resp.stop_details}")
    if resp.parsed_output is None:
        raise RuntimeError(f"no parsed output (stop_reason={resp.stop_reason})")
    return resp.parsed_output


def chat(
    system: str,
    messages: list[dict],
    *,
    model: str = SIM_MODEL,
    effort: str = "low",
    max_tokens: int = 2000,
) -> str:
    """Plain text turn (used for simulated customer / local agent stand-in)."""
    resp = client().messages.create(
        model=model,
        max_tokens=max_tokens,
        output_config={"effort": effort},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
    )
    if resp.stop_reason == "refusal":
        return "[refused]"
    return "".join(b.text for b in resp.content if b.type == "text").strip()
