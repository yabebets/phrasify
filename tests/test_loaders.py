from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from phrasify.loaders import load_transcript, parse_frontmatter


class LoaderTests(unittest.TestCase):
    def test_parse_frontmatter(self) -> None:
        fm, body = parse_frontmatter("---\ntitle: Demo\nlang: en\n---\n\nBody")
        self.assertEqual(fm, {"title": "Demo", "lang": "en"})
        self.assertEqual(body, "Body")

    def test_load_markdown_prefers_transcript_section(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "clip.md"
            path.write_text(
                "---\ntitle: Demo Clip\n---\n\nIntro\n\n## Transcript\n\n"
                "Use this part.\n\n## Notes\n\nNot this.",
                encoding="utf-8",
            )
            doc = load_transcript(path)
        self.assertEqual(doc.title, "Demo Clip")
        self.assertIn("Use this part.", doc.text)
        self.assertNotIn("Not this.", doc.text)

    def test_load_srt_strips_indices_and_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.srt"
            path.write_text(
                "1\n00:00:00,000 --> 00:00:02,000\nLet's double down.\n\n"
                "2\n00:00:02,500 --> 00:00:04,000\nAt a high level, it works.\n",
                encoding="utf-8",
            )
            doc = load_transcript(path)
        self.assertNotIn("00:00", doc.text)
        self.assertIn("Let's double down.", doc.text)
        self.assertIn("At a high level", doc.text)

    def test_load_transcript_rejects_unsupported_extension(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "sample.pdf"
            path.write_text("body", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unsupported transcript type"):
                load_transcript(path)


if __name__ == "__main__":
    unittest.main()
