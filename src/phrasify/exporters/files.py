from __future__ import annotations

import csv
import json
from pathlib import Path

from ..models import ExpressionCard


def write_jsonl(cards: list[ExpressionCard], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for card in cards:
            f.write(json.dumps(card.to_dict(), ensure_ascii=False) + "\n")


def write_json(cards: list[ExpressionCard], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"expressions": [card.to_dict() for card in cards]}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(cards: list[ExpressionCard], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "seq",
        "expression",
        "original_sentence",
        "jp_translation",
        "nuance",
        "usage",
        "reusable_examples",
        "tags",
        "source_file",
        "source_chunk_id",
        "source_timestamp",
        "pattern",
        "category",
        "usefulness_score",
        "native_reusable_score",
        "reusability_score",
        "executive_naturalness_score",
        "silicon_valley_fit_score",
        "mba_interview_fit_score",
        "japanese_speaker_lift_score",
        "too_basic_score",
        "too_context_specific_score",
        "source_confidence_score",
        "expression_in_source",
        "original_sentence_in_source",
        "review_status",
        "extracted_at",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for card in cards:
            writer.writerow(
                {
                    "seq": card.seq,
                    "expression": card.expression,
                    "original_sentence": card.original_sentence,
                    "jp_translation": card.jp_translation,
                    "nuance": card.nuance,
                    "usage": card.usage,
                    "reusable_examples": "\n".join(card.reusable_examples),
                    "tags": ", ".join(card.tags),
                    "source_file": card.source.file,
                    "source_chunk_id": card.source.chunk_id,
                    "source_timestamp": card.source.timestamp,
                    "pattern": card.pattern,
                    "category": card.category,
                    "usefulness_score": card.scores.usefulness,
                    "native_reusable_score": card.scores.native_reusable_score,
                    "reusability_score": card.scores.reusability,
                    "executive_naturalness_score": card.scores.executive_naturalness,
                    "silicon_valley_fit_score": card.scores.silicon_valley_fit,
                    "mba_interview_fit_score": card.scores.mba_interview_fit,
                    "japanese_speaker_lift_score": card.scores.japanese_speaker_lift,
                    "too_basic_score": card.scores.too_basic,
                    "too_context_specific_score": card.scores.too_context_specific,
                    "source_confidence_score": card.scores.source_confidence,
                    "expression_in_source": card.expression_in_source,
                    "original_sentence_in_source": card.original_sentence_in_source,
                    "review_status": card.review_status,
                    "extracted_at": card.extracted_at,
                }
            )
