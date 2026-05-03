from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from phrasify.aggregate import aggregate_jsonl, clip_id_from_jsonl


class AggregateTests(unittest.TestCase):
    def test_clip_id_strips_date_suffix(self) -> None:
        self.assertEqual(clip_id_from_jsonl(Path("demo_20260503.jsonl")), "demo")
        self.assertEqual(clip_id_from_jsonl(Path("demo.jsonl")), "demo")

    def test_aggregate_jsonl_counts_frequency(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "a_20260503.jsonl").write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "expression": "double down on",
                        "category": "collocation",
                        "jp_translation": "注力する",
                        "extracted_at": "2026-05-03T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (out / "b_20260503.jsonl").write_text(
                json.dumps(
                    {
                        "seq": 1,
                        "expression": "Double down on.",
                        "category": "collocation",
                        "jp_translation": "さらに注力する",
                        "extracted_at": "2026-05-04T00:00:00+00:00",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            rows = aggregate_jsonl(out)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["frequency"], 2)
        self.assertEqual(rows[0]["jp_translation"], "さらに注力する")


if __name__ == "__main__":
    unittest.main()
