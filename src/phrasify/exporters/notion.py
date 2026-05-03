from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from ..models import ExpressionCard


DEFAULT_NOTION_DB_ID = "745f3755-c507-4f63-837e-0c9b17374409"
DEFAULT_NOTION_DATA_SOURCE_ID = "d55ebdaa-dfbb-4dd8-b142-433b828ed902"


def build_notion_handoff(
    cards: list[ExpressionCard],
    source_id: str,
    jsonl_path: Path | None = None,
    database_id: str = DEFAULT_NOTION_DB_ID,
    data_source_id: str = DEFAULT_NOTION_DATA_SOURCE_ID,
) -> dict:
    pages = []
    for card in cards:
        pages.append(
            {
                "properties": {
                    "Expression": card.expression,
                    "Category": card.category or (card.tags[0] if card.tags else None),
                    "Clip Source": source_id,
                    "Definition (JA)": card.nuance or card.usage,
                    "Usage": card.usage,
                    "Original Sentence": card.original_sentence,
                    "Original Sentence (JA)": card.jp_translation,
                    "Reusable Examples": "\n".join(card.reusable_examples),
                    "Pattern": card.pattern or "",
                    "Tags": ", ".join(card.tags),
                    "Expression In Source": "__YES__"
                    if card.expression_in_source
                    else "__NO__",
                    "Original Sentence In Source": "__YES__"
                    if card.original_sentence_in_source
                    else "__NO__",
                    "date:Extracted At:start": card.extracted_at[:10],
                    "Review Status": card.review_status,
                }
            }
        )
    return {
        "schema_version": 2,
        "target": {
            "database_id": database_id,
            "data_source_id": data_source_id,
            "data_source_url": f"collection://{data_source_id}",
        },
        "source": {
            "source_id": source_id,
            "jsonl_path": str(jsonl_path) if jsonl_path else None,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "expression_count": len(cards),
        },
        "dedup_strategy": {
            "key": "Expression",
            "match": "case_insensitive_strip_punctuation",
            "on_match": "append_source_id_to_clip_source_if_missing",
            "on_new": "create_page",
        },
        "pages_to_create_or_update": pages,
    }


def write_notion_handoff(
    cards: list[ExpressionCard],
    path: Path,
    source_id: str,
    jsonl_path: Path | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = build_notion_handoff(cards, source_id=source_id, jsonl_path=jsonl_path)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

