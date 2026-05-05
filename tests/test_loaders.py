from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phrasify.loaders import load_transcript, parse_frontmatter
from phrasify.media import RemoteTranscript, resolve_podcast_episode, write_remote_transcript


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

    def test_write_remote_transcript_can_be_loaded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = write_remote_transcript(
                RemoteTranscript(
                    url="https://youtu.be/abc123def45",
                    title="Demo Video",
                    text="At a high level, we should double down.",
                    source_type="youtube",
                    transcript_source="youtube-captions",
                ),
                Path(td),
            )
            doc = load_transcript(path)
        self.assertEqual(doc.title, "Demo Video")
        self.assertIn("At a high level", doc.text)

    def test_resolve_podcast_episode_reads_rss_transcript_url(self) -> None:
        rss = """<?xml version="1.0"?>
        <rss xmlns:podcast="https://podcastindex.org/namespace/1.0">
          <channel>
            <item>
              <title>Episode One</title>
              <link>https://example.com/episodes/one</link>
              <enclosure url="https://cdn.example.com/one.mp3" type="audio/mpeg" />
              <podcast:transcript url="https://example.com/one.vtt" type="text/vtt" />
            </item>
          </channel>
        </rss>
        """
        with patch("phrasify.media._fetch_text", return_value=(rss, "application/rss+xml", "https://example.com/feed.xml")):
            episode = resolve_podcast_episode("https://example.com/feed.xml")
        self.assertEqual(episode["title"], "Episode One")
        self.assertEqual(episode["audio_url"], "https://cdn.example.com/one.mp3")
        self.assertEqual(episode["transcript_url"], "https://example.com/one.vtt")


if __name__ == "__main__":
    unittest.main()
