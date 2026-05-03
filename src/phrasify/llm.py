from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


PROVIDER_DEFAULT_MODEL = {
    "openai": "gpt-4o",
    "anthropic": "claude-3-5-sonnet-latest",
}

PROVIDER_MODEL_ENV = {
    "openai": "PHRASIFY_OPENAI_MODEL",
    "anthropic": "PHRASIFY_ANTHROPIC_MODEL",
}


def extract_json_object(text: str) -> str:
    s = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", s, re.DOTALL)
    if fence:
        s = fence.group(1).strip()
    if s.startswith("{"):
        return s
    start = s.find("{")
    if start == -1:
        return s
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(s)):
        ch = s[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return s[start : i + 1]
    return s[start:]


def load_prompt(path: Path | None = None) -> str:
    if path is None:
        path = Path(__file__).resolve().parent / "prompts" / "extract.md"
    return path.read_text(encoding="utf-8")


def build_user_message(
    transcript: str,
    transcript_title: str,
    chunk_id: str,
    max_expressions: int,
) -> str:
    return (
        f"Transcript title: {transcript_title}\n"
        f"chunk_id: {chunk_id}\n"
        f"max_expressions = {max_expressions}\n\n"
        f"--- BEGIN TRANSCRIPT CHUNK ---\n{transcript}\n--- END TRANSCRIPT CHUNK ---"
    )


def require_provider_env(provider: str) -> None:
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set")
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set")


def get_default_model(provider: str) -> str:
    env_name = PROVIDER_MODEL_ENV.get(provider)
    if env_name:
        value = os.getenv(env_name)
        if value:
            return value
    try:
        return PROVIDER_DEFAULT_MODEL[provider]
    except KeyError as exc:
        raise ValueError(f"unknown provider: {provider}") from exc


def call_llm(
    provider: str,
    model: str,
    system_prompt: str,
    transcript: str,
    transcript_title: str,
    chunk_id: str,
    max_expressions: int,
) -> list[dict]:
    if provider == "openai":
        return _call_openai(
            model, system_prompt, transcript, transcript_title, chunk_id, max_expressions
        )
    if provider == "anthropic":
        return _call_anthropic(
            model, system_prompt, transcript, transcript_title, chunk_id, max_expressions
        )
    raise ValueError(f"unknown provider: {provider}")


def _parse_items(content: str) -> list[dict]:
    payload = extract_json_object(content)
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError(f"LLM returned non-object JSON: {type(data).__name__}")
    items = data.get("expressions", [])
    if not isinstance(items, list):
        raise ValueError(f"LLM returned non-list expressions: {type(items).__name__}")
    bad_indexes = [
        str(index) for index, item in enumerate(items) if not isinstance(item, dict)
    ]
    if bad_indexes:
        raise ValueError(
            "LLM returned malformed expression item(s) at index: "
            + ", ".join(bad_indexes)
        )
    return items


def _call_openai(
    model: str,
    system_prompt: str,
    transcript: str,
    transcript_title: str,
    chunk_id: str,
    max_expressions: int,
) -> list[dict]:
    from openai import OpenAI

    client = OpenAI()
    resp = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": build_user_message(
                    transcript, transcript_title, chunk_id, max_expressions
                ),
            },
        ],
        temperature=0.2,
        max_tokens=16_000,
    )
    choice = resp.choices[0]
    content = choice.message.content or "{}"
    finish_reason = getattr(choice, "finish_reason", None)
    if finish_reason != "stop":
        print(
            f"[warn] openai finish_reason={finish_reason!r}; output may be truncated",
            file=sys.stderr,
        )
    return _parse_items(content)


def _call_anthropic(
    model: str,
    system_prompt: str,
    transcript: str,
    transcript_title: str,
    chunk_id: str,
    max_expressions: int,
) -> list[dict]:
    from anthropic import Anthropic

    client = Anthropic()
    json_only_system = (
        system_prompt
        + "\n\n# Output discipline\n"
        "Return only a single JSON object with an `expressions` array. "
        "The first character must be `{` and the last character must be `}`."
    )
    msg = client.messages.create(
        model=model,
        max_tokens=16_000,
        system=json_only_system,
        messages=[
            {
                "role": "user",
                "content": build_user_message(
                    transcript, transcript_title, chunk_id, max_expressions
                ),
            }
        ],
    )
    content = "".join(
        block.text for block in msg.content if getattr(block, "type", None) == "text"
    )
    stop_reason = getattr(msg, "stop_reason", None)
    if stop_reason != "end_turn":
        print(
            f"[warn] anthropic stop_reason={stop_reason!r}; output may be truncated",
            file=sys.stderr,
        )
    return _parse_items(content)
