from __future__ import annotations

import unittest

from phrasify.chunking import chunk_text


class ChunkingTests(unittest.TestCase):
    def test_chunk_text_preserves_timestamp(self) -> None:
        text = "[0:12] First paragraph.\n\nSecond paragraph."
        chunks = chunk_text(text, source_stem="demo", max_chars=1000)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].chunk_id, "demo-001")
        self.assertEqual(chunks[0].timestamp, "0:12")

    def test_chunk_text_splits_on_paragraph_boundaries(self) -> None:
        text = "A" * 700 + "\n\n" + "B" * 700
        chunks = chunk_text(text, source_stem="demo", max_chars=1000)
        self.assertEqual([c.chunk_id for c in chunks], ["demo-001", "demo-002"])
        self.assertTrue(chunks[0].text.startswith("A"))
        self.assertTrue(chunks[1].text.startswith("B"))


if __name__ == "__main__":
    unittest.main()
