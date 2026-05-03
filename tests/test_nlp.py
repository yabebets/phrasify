from __future__ import annotations

import unittest

from phrasify.nlp import (
    build_candidate_hint_block,
    expression_in_source_by_lemma,
    extract_candidate_expressions,
)


class NlpTests(unittest.TestCase):
    def test_extract_candidate_expressions_finds_reusable_frames(self) -> None:
        text = (
            "That being said, I am not fully convinced. "
            "The way I see it, we should take a step back."
        )
        candidates = extract_candidate_expressions(text)
        candidate_texts = {candidate.text.lower() for candidate in candidates}
        self.assertIn("that being said", candidate_texts)
        self.assertIn("take a step back", candidate_texts)
        self.assertIn("the way i see it", candidate_texts)

    def test_build_candidate_hint_block_is_llm_readable(self) -> None:
        block = build_candidate_hint_block("That being said, we should pressure test it.")
        self.assertIn("Candidate expression hints", block)
        self.assertIn("That being said", block)
        self.assertIn("pressure test", block)

    def test_expression_in_source_by_lemma_handles_inflection(self) -> None:
        self.assertTrue(
            expression_in_source_by_lemma(
                "double down on",
                "We doubled down on founder-led sales.",
            )
        )


if __name__ == "__main__":
    unittest.main()
