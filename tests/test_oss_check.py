from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from phrasify import __version__  # noqa: F401


class OssCheckTests(unittest.TestCase):
    def test_oss_check_allows_placeholder_env(self) -> None:
        from scripts.oss_check import scan_file

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env.example"
            path.write_text("ANTHROPIC_API_KEY=\nOPENAI_API_KEY=your-openai-api-key\n")

            self.assertEqual(scan_file(path), [])

    def test_oss_check_flags_exp_private_path(self) -> None:
        from scripts.oss_check import scan_file

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "README.md"
            path.write_text("Use /Users/toshiakiyabe/exp/Knowledge/Clips/private.md\n")

            findings = scan_file(path)

        self.assertGreaterEqual(len(findings), 1)
        self.assertEqual(findings[0].pattern, "personal absolute path")

    def test_oss_check_skips_private_overlay(self) -> None:
        from scripts.oss_check import list_candidate_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_dir = root / ".phrasify.local"
            private_dir.mkdir()
            (private_dir / "notes.md").write_text("/Users/toshiakiyabe/exp\n")
            public = root / "README.md"
            public.write_text("public docs\n")

            paths = list_candidate_files(root)

        self.assertEqual(paths, [public])


if __name__ == "__main__":
    unittest.main()
