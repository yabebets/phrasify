from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .nlp import apply_nlp_score_adjustments, expression_in_source_by_lemma


@dataclass(frozen=True)
class TranscriptDocument:
    path: Path
    title: str
    text: str
    frontmatter: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TranscriptChunk:
    chunk_id: str
    text: str
    start_char: int
    end_char: int
    timestamp: str | None = None


@dataclass
class SourceRef:
    file: str
    chunk_id: str | None = None
    timestamp: str | None = None


@dataclass
class Scores:
    usefulness: float | None = None
    reusability: float | None = None
    executive_naturalness: float | None = None
    silicon_valley_fit: float | None = None
    mba_interview_fit: float | None = None
    japanese_speaker_lift: float | None = None
    too_basic: float | None = None
    too_context_specific: float | None = None
    native_reusable_score: float | None = None
    source_confidence: float | None = None


NATIVE_REUSABLE_SCORE_WEIGHTS = {
    "reusability": 0.25,
    "executive_naturalness": 0.20,
    "silicon_valley_fit": 0.15,
    "mba_interview_fit": 0.10,
    "japanese_speaker_lift": 0.25,
    "too_basic": -0.20,
    "too_context_specific": -0.20,
}


@dataclass
class ExpressionCard:
    expression: str
    original_sentence: str
    jp_translation: str
    nuance: str
    usage: str
    reusable_examples: list[str]
    tags: list[str]
    source: SourceRef
    pattern: str | None = None
    category: str | None = None
    scores: Scores = field(default_factory=Scores)
    extracted_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    review_status: str = "New"
    seq: int | None = None
    expression_in_source: bool | None = None
    original_sentence_in_source: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if data["seq"] is None:
            data.pop("seq")
        if data["pattern"] is None:
            data.pop("pattern")
        if data["category"] is None:
            data.pop("category")
        data["scores"] = {
            k: v for k, v in data["scores"].items() if v is not None
        }
        if not data["scores"]:
            data.pop("scores")
        return data


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [_as_str(v) for v in value if _as_str(v)]
    s = _as_str(value)
    return [s] if s else []


def _tags_from_item(item: dict[str, Any]) -> list[str]:
    tags = _as_str_list(item.get("tags"))
    category = _as_str(item.get("category"))
    if category and category not in tags:
        tags.insert(0, category)
    return tags


def card_from_llm_item(
    item: dict[str, Any],
    source_file: str,
    chunk_id: str | None,
    transcript_text: str,
    seq: int | None = None,
) -> ExpressionCard:
    """Map either the DesignSpec schema or the prior extraction schema into a card."""
    expression = _as_str(item.get("expression"))
    original_sentence = _as_str(
        item.get("original_sentence") or item.get("example_from_clip")
    )
    jp_translation = _as_str(
        item.get("jp_translation")
        or item.get("original_sentence_ja")
        or item.get("example_from_clip_ja")
        or item.get("definition_ja")
    )
    nuance = _as_str(item.get("nuance") or item.get("definition_ja"))
    usage = _as_str(item.get("usage") or item.get("definition_ja"))
    reusable_examples = _as_str_list(item.get("reusable_examples"))
    reusable_examples.extend(_as_str_list(item.get("example_paraphrase")))
    reusable_examples = list(dict.fromkeys(reusable_examples))
    tags = _tags_from_item(item)

    source_payload = item.get("source") if isinstance(item.get("source"), dict) else {}
    source = SourceRef(
        file=_as_str(source_payload.get("file")) or source_file,
        chunk_id=_as_str(source_payload.get("chunk_id")) or chunk_id,
        timestamp=_as_str(source_payload.get("timestamp")) or None,
    )
    score_payload = item.get("scores") if isinstance(item.get("scores"), dict) else {}
    scores = scores_from_payload(score_payload)
    has_explicit_native_score = scores.native_reusable_score is not None
    if (
        apply_nlp_score_adjustments(scores, expression, original_sentence)
        and not has_explicit_native_score
    ):
        scores.native_reusable_score = calculate_native_reusable_score(scores)
    text_lower = transcript_text.lower()
    expression_in_source = bool(
        expression
        and (
            expression.lower() in text_lower
            or expression_in_source_by_lemma(expression, transcript_text)
        )
    )
    original_sentence_in_source = bool(original_sentence and original_sentence in transcript_text)

    return ExpressionCard(
        seq=seq,
        expression=expression,
        original_sentence=original_sentence,
        jp_translation=jp_translation,
        nuance=nuance,
        usage=usage,
        reusable_examples=reusable_examples,
        tags=tags,
        source=source,
        pattern=_as_str(item.get("pattern")) or None,
        category=_as_str(item.get("category")) or None,
        scores=scores,
        review_status=_as_str(item.get("review_status")) or "New",
        expression_in_source=expression_in_source,
        original_sentence_in_source=original_sentence_in_source,
    )


def card_from_record(record: dict[str, Any]) -> ExpressionCard:
    source_payload = record.get("source") if isinstance(record.get("source"), dict) else {}
    score_payload = record.get("scores") if isinstance(record.get("scores"), dict) else {}
    return ExpressionCard(
        seq=record.get("seq"),
        expression=_as_str(record.get("expression")),
        original_sentence=_as_str(record.get("original_sentence")),
        jp_translation=_as_str(record.get("jp_translation")),
        nuance=_as_str(record.get("nuance")),
        usage=_as_str(record.get("usage")),
        reusable_examples=_as_str_list(record.get("reusable_examples")),
        tags=_as_str_list(record.get("tags")),
        source=SourceRef(
            file=_as_str(source_payload.get("file")),
            chunk_id=_as_str(source_payload.get("chunk_id")) or None,
            timestamp=_as_str(source_payload.get("timestamp")) or None,
        ),
        pattern=_as_str(record.get("pattern")) or None,
        category=_as_str(record.get("category")) or None,
        scores=scores_from_payload(score_payload),
        extracted_at=_as_str(record.get("extracted_at"))
        or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        review_status=_as_str(record.get("review_status")) or "New",
        expression_in_source=record.get("expression_in_source"),
        original_sentence_in_source=record.get("original_sentence_in_source"),
    )


def _coerce_score(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, score))


def scores_from_payload(payload: dict[str, Any]) -> Scores:
    scores = Scores(
        usefulness=_coerce_score(payload.get("usefulness")),
        reusability=_coerce_score(payload.get("reusability")),
        executive_naturalness=_coerce_score(payload.get("executive_naturalness")),
        silicon_valley_fit=_coerce_score(payload.get("silicon_valley_fit")),
        mba_interview_fit=_coerce_score(payload.get("mba_interview_fit")),
        japanese_speaker_lift=_coerce_score(payload.get("japanese_speaker_lift")),
        too_basic=_coerce_score(payload.get("too_basic")),
        too_context_specific=_coerce_score(payload.get("too_context_specific")),
        native_reusable_score=_coerce_score(payload.get("native_reusable_score")),
        source_confidence=_coerce_score(payload.get("source_confidence")),
    )
    if scores.native_reusable_score is None:
        scores.native_reusable_score = calculate_native_reusable_score(scores)
    return scores


def calculate_native_reusable_score(scores: Scores) -> float | None:
    values = {
        field_name: getattr(scores, field_name)
        for field_name in NATIVE_REUSABLE_SCORE_WEIGHTS
    }
    if all(value is None for value in values.values()):
        return None
    raw = sum(
        (values[field_name] or 0.0) * weight
        for field_name, weight in NATIVE_REUSABLE_SCORE_WEIGHTS.items()
    )
    return round(max(0.0, min(1.0, raw)), 3)


def validate_card(card: ExpressionCard) -> list[str]:
    errors: list[str] = []
    required = {
        "expression": card.expression,
        "original_sentence": card.original_sentence,
        "jp_translation": card.jp_translation,
        "usage": card.usage,
        "reusable_examples": card.reusable_examples,
        "tags": card.tags,
        "source.file": card.source.file,
    }
    for field_name, value in required.items():
        if not value:
            errors.append(f"missing required field: {field_name}")
    return errors
