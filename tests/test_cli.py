from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from phrasify.cli import build_parser, filter_cards_by_scores, main
from phrasify.models import card_from_llm_item


class CliTests(unittest.TestCase):
    def test_cli_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            transcript = Path(td) / "demo.txt"
            transcript.write_text(
                "At a high level, we help founders move faster.", encoding="utf-8"
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["extract", str(transcript), "--dry-run"])

        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("[phrasify]", out)
        self.assertIn("[chunk]", out)

    def test_cli_export_csv(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            src = root / "cards.jsonl"
            out = root / "cards.csv"
            src.write_text(
                (
                    '{"seq":1,"expression":"at a high level",'
                    '"original_sentence":"At a high level, it works.",'
                    '"jp_translation":"大まかに言うと機能します。",'
                    '"nuance":"全体像を示す。","usage":"説明の冒頭。",'
                    '"reusable_examples":["At a high level, we help founders."],'
                    '"tags":["transition"],"source":{"file":"clip.md"}}\n'
                ),
                encoding="utf-8",
            )
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["export", str(src), "--format", "csv", "--out", str(out)])
            self.assertEqual(code, 0)
            self.assertTrue(out.exists())
            self.assertIn("at a high level", out.read_text(encoding="utf-8"))

    def test_cli_dry_run_rejects_empty_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            transcript = Path(td) / "empty.txt"
            transcript.write_text("   \n", encoding="utf-8")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                code = main(["extract", str(transcript), "--dry-run"])
        self.assertEqual(code, 1)
        self.assertIn("empty transcript", err.getvalue())

    def test_extract_default_output_dir_is_current_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            cwd = Path.cwd()
            try:
                import os

                os.chdir(td)
                parser = build_parser()
                args = parser.parse_args(["extract", "demo.txt", "--dry-run"])
                self.assertEqual(args.output_dir.resolve(), (Path(td) / "outputs").resolve())
            finally:
                os.chdir(cwd)

    def test_filter_cards_by_scores_removes_low_value_cards(self) -> None:
        high_value = card_from_llm_item(
            {
                "expression": "that being said",
                "original_sentence": "That being said, we should validate demand.",
                "jp_translation": "とはいえ、需要は検証すべきです。",
                "nuance": "視点を切り替える。",
                "usage": "議論の転換で使う。",
                "reusable_examples": ["That being said, I would test pricing first."],
                "tags": ["transition"],
                "scores": {
                    "native_reusable_score": 0.82,
                    "too_basic": 0.1,
                    "too_context_specific": 0.1,
                },
            },
            "clip.md",
            "clip-001",
            "That being said, we should validate demand.",
        )
        too_basic = card_from_llm_item(
            {
                "expression": "very good",
                "original_sentence": "It is very good.",
                "jp_translation": "とても良いです。",
                "nuance": "基本的な評価。",
                "usage": "一般的な形容。",
                "reusable_examples": ["It is very good."],
                "tags": ["basic"],
                "scores": {
                    "native_reusable_score": 0.4,
                    "too_basic": 0.9,
                    "too_context_specific": 0.1,
                },
            },
            "clip.md",
            "clip-002",
            "It is very good.",
        )
        filtered = filter_cards_by_scores(
            [high_value, too_basic],
            min_native_reusable_score=0.7,
            max_too_basic=0.5,
        )
        self.assertEqual(filtered, [high_value])


if __name__ == "__main__":
    unittest.main()
