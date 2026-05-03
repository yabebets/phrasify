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

    def test_build_notion_handoff(self) -> None:
        payload = build_notion_handoff([_card()], source_id="clip")
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["source"]["expression_count"], 1)
        self.assertEqual(
            payload["pages_to_create_or_update"][0]["properties"]["Expression"],
            "at a high level",
        )


if __name__ == "__main__":
    unittest.main()
