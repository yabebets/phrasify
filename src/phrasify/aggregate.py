from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .dedup import normalize_expression


def clip_id_from_jsonl(path: Path) -> str:
    stem = path.stem
    if len(stem) > 9 and stem[-9] == "_" and stem[-8:].isdigit():
        return stem[:-9]
    return stem


def aggregate_jsonl(input_dir: Path, exclude: set[str] | None = None) -> list[dict[str, Any]]:
    exclude = exclude or {"aggregated.jsonl"}
    buckets: dict[str, dict[str, Any]] = {}
    for jsonl in sorted(input_dir.glob("*.jsonl")):
        if jsonl.name in exclude:
            continue
        clip_id = clip_id_from_jsonl(jsonl)
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            expression = (record.get("expression") or "").strip()
            if not expression:
                continue
            key = normalize_expression(expression)
            bucket = buckets.setdefault(
                key,
                {
                    "normalized": key,
                    "expression": expression,
                    "category": record.get("category"),
                    "tags": record.get("tags") or [],
                    "best_record": record,
                    "best_extracted_at": record.get("extracted_at", ""),
                    "occurrences": [],
                },
            )
            bucket["occurrences"].append(
                {
                    "source_id": clip_id,
                    "seq": record.get("seq"),
                    "expression_raw": expression,
                    "original_sentence": record.get("original_sentence"),
                    "expression_in_source": record.get("expression_in_source"),
                    "original_sentence_in_source": record.get("original_sentence_in_source"),
                    "extracted_at": record.get("extracted_at"),
                }
            )
            if record.get("extracted_at", "") >= bucket["best_extracted_at"]:
                bucket["best_extracted_at"] = record.get("extracted_at", "")
                bucket["best_record"] = record
                bucket["expression"] = expression
                bucket["category"] = record.get("category")
                bucket["tags"] = record.get("tags") or []

    aggregated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for seq, bucket in enumerate(
        sorted(buckets.values(), key=lambda b: (-len(b["occurrences"]), b["normalized"])),
        start=1,
    ):
        best = bucket["best_record"]
        rows.append(
            {
                "seq": seq,
                "expression": bucket["expression"],
                "normalized": bucket["normalized"],
                "category": bucket["category"],
                "tags": bucket["tags"],
                "frequency": len(bucket["occurrences"]),
                "source_ids": sorted({o["source_id"] for o in bucket["occurrences"]}),
                "jp_translation": best.get("jp_translation"),
                "nuance": best.get("nuance"),
                "usage": best.get("usage"),
                "pattern": best.get("pattern"),
                "reusable_examples": best.get("reusable_examples") or [],
                "occurrences": bucket["occurrences"],
                "aggregated_at": aggregated_at,
            }
        )
    return rows


def write_aggregated_jsonl(rows: list[dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

