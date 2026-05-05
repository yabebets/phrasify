from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phrasify.cli import build_parser, filter_cards_by_scores, main
from phrasify.media import RemoteTranscript
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

    def test_cli_dry_run_accepts_url_input(self) -> None:
        remote = RemoteTranscript(
            url="https://www.youtube.com/watch?v=abc123def45",
            title="Demo URL",
            text="At a high level, this market is moving fast.",
            source_type="youtube",
            transcript_source="youtube-captions",
        )
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td) / "outputs"
            buf = io.StringIO()
            with patch("phrasify.media.load_remote_transcript", return_value=remote):
                with contextlib.redirect_stdout(buf):
                    code = main(
                        [
                            "extract",
                            remote.url,
                            "--dry-run",
                            "--output-dir",
                            str(out_dir),
                        ]
                    )

        self.assertEqual(code, 0)
        out = buf.getvalue()
        self.assertIn("[transcript]", out)
        self.assertIn("[chunk]", out)

    def test_profile_create_writes_generated_profile(self) -> None:
        payload = {
            "name": "founder_updates_fr",
            "role": "expert English learning material designer",
            "learner": "a French founder preparing for investor updates",
            "level": "advanced",
            "explanation_language": "French",
            "domains": ["fundraising", "investor updates"],
            "situations": ["board updates", "investor calls"],
            "focus": ["concise update phrases", "polite pushback expressions"],
            "avoid": ["company-specific facts"],
            "learner_lift_description": "Would this help the learner sound concise and credible?",
            "example_context": "We are tracking ahead of plan on retention.",
            "tags_hint": ["fundraising", "updates"],
            "categories": ["update", "pushback", "collocation"],
            "extra_instructions": "",
        }
        with tempfile.TemporaryDirectory() as td:
            out_path = Path(td) / "profile.toml"
            buf = io.StringIO()
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                with patch("phrasify.cli.call_json", return_value=payload):
                    with contextlib.redirect_stdout(buf):
                        code = main(
                            [
                                "profile",
                                "create",
                                "I am a French founder preparing investor updates.",
                                "--out",
                                str(out_path),
                            ]
                        )
            text = out_path.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("founder_updates_fr", text)
        self.assertIn("French founder", text)
        self.assertIn("[profile]", buf.getvalue())

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
