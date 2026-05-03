from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from phrasify.exporters import build_notion_handoff, write_csv, write_jsonl
from phrasify.models import card_from_llm_item


def _card():
    return card_from_llm_item(
        {
            "expression": "at a high level",
            "original_sentence": "At a high level, this is a marketplace.",
            "jp_translation": "大まかに言うと、これはマーケットプレイスです。",
            "nuance": "全体像を示す導入表現。",
            "usage": "説明の冒頭で使う。",
            "reusable_examples": ["At a high level, we help founders raise faster."],
            "tags": ["synthesis"],
            "category": "synthesis",
        },
        "clip.md",
        "clip-001",
        "At a high level, this is a marketplace.",
        seq=1,
    )


class ExporterTests(unittest.TestCase):
    def test_write_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.jsonl"
            write_jsonl([_card()], path)
            row = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(row["expression"], "at a high level")
        self.assertEqual(row["source"]["chunk_id"], "clip-001")

    def test_write_csv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "out.csv"
            write_csv([_card()], path)
            text = path.read_text(encoding="utf-8")
        self.assertIn("expression", text)
        self.assertIn("at a high level", text)
        self.assertIn("expression_in_source", text)
        self.assertIn("source_confidence_score", text)

    def test_build_notion_handoff(self) -> None:
        payload = build_notion_handoff([_card()], source_id="clip")
        self.assertEqual(payload["schema_version"], 2)
        self.assertIsNone(payload["target"]["database_id"])
        self.assertIsNone(payload["target"]["data_source_id"])
        self.assertEqual(payload["source"]["expression_count"], 1)
        self.assertEqual(
            payload["pages_to_create_or_update"][0]["properties"]["Expression"],
            "at a high level",
        )

    def test_build_notion_handoff_accepts_explicit_target(self) -> None:
        payload = build_notion_handoff(
            [_card()],
            source_id="clip",
            database_id="db_123",
            data_source_id="ds_123",
        )
        self.assertEqual(payload["target"]["database_id"], "db_123")
        self.assertEqual(payload["target"]["data_source_url"], "collection://ds_123")


if __name__ == "__main__":
    unittest.main()
