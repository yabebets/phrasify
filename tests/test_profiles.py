from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from phrasify.profiles import (
    apply_profile_overrides,
    build_profile_generation_system_prompt,
    load_extraction_profile,
    render_extraction_prompt,
    save_extraction_profile,
)


class ProfileTests(unittest.TestCase):
    def test_default_profile_preserves_japanese_business_focus(self) -> None:
        prompt = render_extraction_prompt(load_extraction_profile())
        self.assertIn("native Japanese speaker", prompt)
        self.assertIn("venture capital", prompt)
        self.assertIn("Japanese explanation", prompt)
        self.assertIn('"japanese_speaker_lift"', prompt)

    def test_load_toml_profile_customizes_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.toml"
            path.write_text(
                """
name = "software_engineering_es"
learner = "a Spanish-speaking software engineer preparing for technical leadership meetings"
level = "CEFR B2"
explanation_language = "Spanish"
domains = ["software engineering", "product management"]
situations = ["architecture reviews", "roadmap discussions"]
focus = ["technical tradeoff expressions", "alignment phrases"]
avoid = ["company-specific facts"]
example_context = "software leadership example sentence"
tags_hint = ["engineering", "leadership"]
categories = ["technical", "leadership", "collocation"]
""",
                encoding="utf-8",
            )
            profile = load_extraction_profile(path)
        prompt = render_extraction_prompt(profile)
        self.assertIn("Spanish-speaking software engineer", prompt)
        self.assertIn("software engineering", prompt)
        self.assertIn("Spanish explanation", prompt)
        self.assertIn("technical tradeoff expressions", prompt)
        self.assertIn('"japanese_speaker_lift"', prompt)

    def test_profile_overrides_take_precedence(self) -> None:
        profile = apply_profile_overrides(
            load_extraction_profile(),
            learner="a French founder learning investor updates",
            explanation_language="French",
            domains=["fundraising", "investor updates"],
            focus=["concise update phrases"],
        )
        prompt = render_extraction_prompt(profile)
        self.assertIn("French founder", prompt)
        self.assertIn("fundraising", prompt)
        self.assertIn("French explanation", prompt)
        self.assertIn("concise update phrases", prompt)

    def test_unknown_profile_field_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.json"
            path.write_text('{"unknown": "value"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "unknown profile field"):
                load_extraction_profile(path)

    def test_save_profile_as_toml_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "profile.toml"
            save_extraction_profile(load_extraction_profile(), path)
            profile = load_extraction_profile(path)
        self.assertEqual(profile.name, "japanese_business")
        self.assertIn("venture capital", profile.domains)

    def test_profile_generation_prompt_lists_required_fields(self) -> None:
        prompt = build_profile_generation_system_prompt()
        self.assertIn("Return only JSON", prompt)
        self.assertIn("explanation_language", prompt)
        self.assertIn("learner_lift_description", prompt)


if __name__ == "__main__":
    unittest.main()
