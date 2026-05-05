from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ExtractionProfile:
    name: str = "japanese_business"
    role: str = "expert English learning material designer"
    learner: str = (
        "a native Japanese speaker working around venture capital, startups, "
        "finance, MBA interviews, and business discussions"
    )
    level: str = "CEFR B2+"
    explanation_language: str = "Japanese"
    domains: list[str] = field(
        default_factory=lambda: [
            "venture capital",
            "startups",
            "finance",
            "MBA interviews",
            "business discussions",
        ]
    )
    situations: list[str] = field(
        default_factory=lambda: [
            "meetings",
            "interviews",
            "founder calls",
            "investment discussions",
            "business writing",
        ]
    )
    focus: list[str] = field(
        default_factory=lambda: [
            "meeting expressions",
            "opinion / framing expressions",
            "disagreement / hedging expressions",
            "summary / synthesis expressions",
            "negotiation / proposal expressions",
            "news comprehension expressions",
            "VC / startup / finance / product expressions",
            "natural casual native expressions",
            "high-frequency phrasal verbs",
            "collocations",
            "fixed phrases",
            "useful transition expressions",
        ]
    )
    avoid: list[str] = field(
        default_factory=lambda: [
            "proper nouns",
            "person names",
            "company names",
            "overly context-specific facts",
            "basic vocabulary unless it appears in a highly reusable phrase",
        ]
    )
    learner_lift_description: str = (
        "Would this be especially valuable for this learner, who may know the "
        "words but would not naturally produce the phrase in real time?"
    )
    example_context: str = "business/VC/startup-context example sentence"
    tags_hint: list[str] = field(default_factory=lambda: ["business_collocation", "strategy", "vc_startup"])
    categories: list[str] = field(
        default_factory=lambda: [
            "meeting",
            "opinion",
            "hedge",
            "synthesis",
            "negotiation",
            "news",
            "vc_startup",
            "casual",
            "phrasal_verb",
            "collocation",
            "fixed_phrase",
            "transition",
        ]
    )
    extra_instructions: str = ""


def load_extraction_profile(path: Path | None = None) -> ExtractionProfile:
    if path is None:
        return ExtractionProfile()
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() in {".toml", ".tml"}:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        raise ValueError("profile must be a JSON or TOML file")
    if not isinstance(payload, dict):
        raise ValueError("profile must contain an object/table")
    return profile_from_mapping(payload)


def profile_from_mapping(payload: dict[str, Any]) -> ExtractionProfile:
    allowed = set(ExtractionProfile.__dataclass_fields__)
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError("unknown profile field(s): " + ", ".join(unknown))

    base = ExtractionProfile()
    values: dict[str, Any] = {}
    for key, value in payload.items():
        current = getattr(base, key)
        if isinstance(current, list):
            values[key] = _as_str_list(value, field_name=key)
        elif isinstance(current, str):
            values[key] = _as_str(value, field_name=key)
        else:
            values[key] = value
    return replace(base, **values)


def profile_to_mapping(profile: ExtractionProfile) -> dict[str, Any]:
    return asdict(profile)


def save_extraction_profile(profile: ExtractionProfile, path: Path) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = profile_to_mapping(profile)
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    elif path.suffix.lower() in {".toml", ".tml"}:
        path.write_text(render_profile_toml(profile), encoding="utf-8")
    else:
        raise ValueError("profile output path must end in .json or .toml")


def render_profile_toml(profile: ExtractionProfile) -> str:
    payload = profile_to_mapping(profile)
    lines: list[str] = []
    for key, value in payload.items():
        if isinstance(value, str):
            if "\n" in value:
                lines.append(f'{key} = """{_escape_multiline_toml(value)}"""')
            else:
                lines.append(f"{key} = {_toml_string(value)}")
        elif isinstance(value, list):
            lines.append(f"{key} = [")
            for item in value:
                lines.append(f"  {_toml_string(str(item))},")
            lines.append("]")
        else:
            raise ValueError(f"cannot render profile field {key!r} as TOML")
    return "\n".join(lines) + "\n"


def build_profile_generation_system_prompt() -> str:
    fields = ", ".join(ExtractionProfile.__dataclass_fields__)
    default = json.dumps(profile_to_mapping(ExtractionProfile()), ensure_ascii=False, indent=2)
    return f"""You create Phrasify extraction profiles from natural-language user preferences.

Phrasify extracts reusable English expressions from transcripts. A profile configures the target learner, domain, situations, expression focus, explanation language, and scoring guidance.

Return only JSON with exactly these top-level fields:
{fields}

Every field must be present. String-list fields must be arrays of strings. Do not invent private facts. Convert vague user requests into concise, reusable extraction settings. Keep the profile general enough to work across many transcripts.

Compatibility notes:
- Keep field names exactly as listed.
- `explanation_language` controls the language used inside `jp_translation`, `nuance`, and `usage`.
- `learner_lift_description` should explain what "valuable but hard to produce naturally" means for this learner.
- `categories` should be short category labels suitable for the output `category` field.
- `tags_hint` should be example tags, not a closed taxonomy.

Default profile for reference:
{default}
"""


def build_profile_generation_user_message(description: str) -> str:
    return f"""Create a Phrasify extraction profile from this user request:

--- BEGIN USER REQUEST ---
{description.strip()}
--- END USER REQUEST ---

The result should be directly usable as a profile JSON/TOML file."""


def profile_from_llm_payload(payload: dict[str, Any]) -> ExtractionProfile:
    profile = profile_from_mapping(payload)
    if not profile.name:
        raise ValueError("generated profile name must not be empty")
    if not profile.learner:
        raise ValueError("generated profile learner must not be empty")
    if not profile.focus:
        raise ValueError("generated profile focus must not be empty")
    return profile


def apply_profile_overrides(
    profile: ExtractionProfile,
    *,
    learner: str | None = None,
    level: str | None = None,
    explanation_language: str | None = None,
    domains: list[str] | None = None,
    focus: list[str] | None = None,
) -> ExtractionProfile:
    updates: dict[str, Any] = {}
    if learner:
        updates["learner"] = learner
    if level:
        updates["level"] = level
    if explanation_language:
        updates["explanation_language"] = explanation_language
    if domains:
        updates["domains"] = domains
    if focus:
        updates["focus"] = focus
    return replace(profile, **updates) if updates else profile


def render_extraction_prompt(profile: ExtractionProfile) -> str:
    domains = _join_items(profile.domains)
    situations = _join_items(profile.situations)
    focus = _bullet_list(profile.focus)
    avoid = _bullet_list(profile.avoid)
    tags = json.dumps(profile.tags_hint, ensure_ascii=False)
    categories = " | ".join(profile.categories)
    extra = (
        "\n# Additional profile instructions\n\n" + profile.extra_instructions.strip() + "\n"
        if profile.extra_instructions.strip()
        else ""
    )

    return f"""You are an {profile.role}.

Your learner is {profile.learner}. The learner level is {profile.level}. Extract reusable English expressions that can be spoken or written in real situations. The target domains are: {domains}.

# Extraction goal

Turn the transcript chunk into learning-ready expression cards. Prefer reusable phrases, collocations, sentence frames, hedges, domain expressions, and natural spoken or written patterns. Do not optimize for rare words. Optimize for expressions the learner can reuse in {situations}.

# Native but reusable scoring

For every expression, explicitly evaluate whether it is native but reusable. Score each field from 0.0 to 1.0.

- `reusability`: Can the learner reuse this in many target situations?
- `executive_naturalness`: Does it sound mature, polished, and natural for the configured audience?
- `silicon_valley_fit`: Would it sound natural in the configured domains, especially if they include startup, technology, product, investing, or founder conversations?
- `mba_interview_fit`: Would it be useful and appropriate in interview, application, leadership, or career-story contexts?
- `japanese_speaker_lift`: {profile.learner_lift_description}
- `too_basic`: Is this too basic for the configured learner level unless used as a useful sentence frame?
- `too_context_specific`: Is this too tied to this transcript's specific facts to be reused elsewhere?

Give high `japanese_speaker_lift` to useful sentence frames and alternatives to simple defaults such as framing, hedging, disagreeing politely, qualifying, summarizing, or shifting perspective. A phrase can use simple words and still have high learner lift if the spoken frame is hard for the configured learner to produce naturally.

# What to extract

{focus}

# What to avoid

{avoid}

# Hard rules

- `expression` should be a phrase or compact expression, not a long sentence.
- `original_sentence` must be copied from the transcript chunk when possible. Do not invent source sentences.
- Avoid items listed in "What to avoid."
- Avoid vocabulary that is too basic for the configured learner unless it appears in a highly reusable phrase.
- Prefer quality over filling the quota.
- If an expression is useful but the source has a different inflected form, keep the source-faithful expression and put the reusable pattern in `pattern`.
- Keep the JSON field names exactly as specified for compatibility. Fill `jp_translation`, `nuance`, and `usage` in {profile.explanation_language}.
{extra}
# Output schema

Return only JSON:

```json
{{
  "expressions": [
    {{
      "expression": "string",
      "original_sentence": "string copied from transcript",
      "jp_translation": "natural {profile.explanation_language} translation of original_sentence",
      "nuance": "{profile.explanation_language} explanation of meaning and nuance",
      "usage": "{profile.explanation_language} explanation of when/how to use it",
      "pattern": "optional reusable form",
      "reusable_examples": [
        "{profile.example_context}",
        "another example sentence"
      ],
      "tags": {tags},
      "category": "{categories}",
      "scores": {{
        "usefulness": 0.0,
        "reusability": 0.0,
        "executive_naturalness": 0.0,
        "silicon_valley_fit": 0.0,
        "mba_interview_fit": 0.0,
        "japanese_speaker_lift": 0.0,
        "too_basic": 0.0,
        "too_context_specific": 0.0,
        "source_confidence": 0.0
      }}
    }}
  ]
}}
```

Return no prose, no markdown fences, and no commentary.
"""


def _as_str(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"profile field {field_name!r} must be a string")
    return value.strip()


def _as_str_list(value: Any, *, field_name: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"profile field {field_name!r} must be a list of strings")
    return [item.strip() for item in value if item.strip()]


def _join_items(items: list[str]) -> str:
    return ", ".join(items) if items else "general professional communication"


def _bullet_list(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- reusable expressions"


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def _escape_multiline_toml(value: str) -> str:
    return value.replace('"""', '\\"\\"\\"')
