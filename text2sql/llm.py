"""The single place that talks to the Claude API: model choice, caching, fallbacks and JSON parsing."""
import functools
import json

import anthropic
from dotenv import load_dotenv

load_dotenv()  # reads ANTHROPIC_API_KEY from .env, which is git-ignored

MODEL = "claude-opus-5-5"


@functools.cache
def client() -> anthropic.Anthropic:
    # Created lazily so tests and the DB script run without an API key
    return anthropic.Anthropic()


def create(system: str, messages: list, schema: dict, effort: str = "medium", max_tokens: int = 32000):
    """One Messages API call whose final text block is JSON matching `schema` (structured outputs)."""
    with client().beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        # The system prompt (schema + examples) is identical on every call: cache it so repeat calls read it at ~10% cost
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=messages,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        # If a safety classifier declines, the API reruns the request on Anthropic's recommended fallback model
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        return stream.get_final_message()


def parse_json(response) -> dict:
    """Return the JSON answer, failing loudly on refusals and truncated output."""
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined the request: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("The response was cut off by max_tokens.")
    return json.loads([b.text for b in response.content if b.type == "text"][-1])
