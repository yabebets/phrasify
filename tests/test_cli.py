from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from phrasify.cli import main


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


if __name__ == "__main__":
    unittest.main()
