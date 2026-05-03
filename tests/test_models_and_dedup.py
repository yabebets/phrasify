from __future__ import annotations

import unittest

from phrasify.dedup import dedup_cards, normalize_expression
from phrasify.models import card_from_llm_item, card_from_record, validate_card


class ModelAndDedupTests(unittest.TestCase):
    def test_legacy_poc_item_maps_to_design_spec_card(self) -> None:
        transcript = "We decided to double down on enterprise sales."
        item = {
            "expression": "double down on",
            "category": "business_collocation",
            "definition_ja": "さらに注力する。",
            "example_from_clip": transcript,
            "example_from_clip_ja": "エンタープライズ営業にさらに注力することにした。",
            "example_paraphrase": "We should double down on founder-led sales.",
        }
        card = card_from_llm_item(item, "clip.md", "clip-001", transcript, seq=1)
        self.assertEqual(card.expression, "double down on")
        self.assertEqual(card.original_sentence, transcript)
        self.assertTrue(card.jp_translation.startswith("エンタープライズ"))
        self.assertEqual(card.nuance, "さらに注力する。")
        self.assertEqual(card.usage, "さらに注力する。")
        self.assertEqual(
            card.reusable_examples, ["We should double down on founder-led sales."]
        )
        self.assertEqual(card.tags, ["business_collocation"])
        self.assertIs(card.expression_in_source, True)
        self.assertIs(card.original_sentence_in_source, True)
        self.assertEqual(validate_card(card), [])

    def test_dedup_prefers_grounded_card(self) -> None:
        grounded = card_from_llm_item(
            {
                "expression": "double down on",
                "original_sentence": "We double down on sales.",
                "jp_translation": "営業に注力する。",
                "nuance": "注力する。",
                "usage": "戦略文脈。",
                "reusable_examples": ["We should double down on retention."],
                "tags": ["strategy"],
            },
            "clip.md",
            "clip-001",
            "We double down on sales.",
        )
        ungrounded = card_from_llm_item(
            {
                "expression": "Double down on.",
                "original_sentence": "Invented sentence.",
                "jp_translation": "訳。",
                "nuance": "注力。",
                "usage": "用途。",
                "reusable_examples": ["Example."],
                "tags": ["strategy"],
            },
            "clip.md",
            "clip-002",
            "No matching phrase here.",
        )
        deduped = dedup_cards([ungrounded, grounded])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].original_sentence, "We double down on sales.")
        self.assertEqual(normalize_expression("Double down on."), "double down on")

    def test_card_from_record_round_trips_export_schema(self) -> None:
        card = card_from_record(
            {
                "seq": 1,
                "expression": "at a high level",
                "original_sentence": "At a high level, this is simple.",
                "jp_translation": "大まかに言えば、これは単純です。",
                "nuance": "全体像を示す。",
                "usage": "説明の冒頭。",
                "reusable_examples": ["At a high level, we help founders."],
                "tags": ["transition"],
                "source": {"file": "clip.md", "chunk_id": "clip-001"},
                "scores": {
                    "usefulness": 0.9,
                    "native_reusable_score": 0.77,
                    "japanese_speaker_lift": 0.95,
                },
                "extracted_at": "2026-05-03T00:00:00+00:00",
            }
        )
        self.assertEqual(card.expression, "at a high level")
        self.assertEqual(card.source.chunk_id, "clip-001")
        self.assertEqual(card.scores.usefulness, 0.9)
        self.assertEqual(card.scores.native_reusable_score, 0.77)
        self.assertEqual(card.scores.japanese_speaker_lift, 0.95)

    def test_native_reusable_score_is_calculated_from_score_components(self) -> None:
        card = card_from_llm_item(
            {
                "expression": "that being said",
                "original_sentence": "That being said, we still need to validate demand.",
                "jp_translation": "とはいえ、需要はまだ検証する必要があります。",
                "nuance": "前段を認めつつ視点を切り替える。",
                "usage": "議論を前に進めながら留保を入れる。",
                "reusable_examples": ["That being said, I would still test pricing first."],
                "tags": ["transition", "hedge"],
                "scores": {
                    "reusability": 0.9,
                    "executive_naturalness": 0.8,
                    "silicon_valley_fit": 0.7,
                    "mba_interview_fit": 0.6,
                    "japanese_speaker_lift": 0.95,
                    "too_basic": 0.1,
                    "too_context_specific": 0.2,
                },
            },
            "clip.md",
            "clip-001",
            "That being said, we still need to validate demand.",
        )
        self.assertEqual(card.scores.native_reusable_score, 0.728)

    def test_card_uses_lemma_grounding_for_inflected_source_expression(self) -> None:
        card = card_from_llm_item(
            {
                "expression": "double down on",
                "original_sentence": "We doubled down on founder-led sales.",
                "jp_translation": "創業者主導の営業にさらに注力しました。",
                "nuance": "確信を持って注力する。",
                "usage": "戦略や投資判断で使う。",
                "reusable_examples": ["We should double down on retention."],
                "tags": ["strategy"],
            },
            "clip.md",
            "clip-001",
            "We doubled down on founder-led sales.",
        )
        self.assertIs(card.expression_in_source, True)

    def test_card_gets_nlp_score_adjustments_for_frames_and_basic_phrases(self) -> None:
        frame = card_from_llm_item(
            {
                "expression": "that being said",
                "original_sentence": "That being said, we should test pricing.",
                "jp_translation": "とはいえ、価格を検証すべきです。",
                "nuance": "視点を切り替える。",
                "usage": "留保を入れながら議論を進める。",
                "reusable_examples": ["That being said, I would validate demand first."],
                "tags": ["transition"],
            },
            "clip.md",
            "clip-001",
            "That being said, we should test pricing.",
        )
        basic = card_from_llm_item(
            {
                "expression": "very good",
                "original_sentence": "It is very good.",
                "jp_translation": "とても良いです。",
                "nuance": "基本的な評価。",
                "usage": "一般的な形容。",
                "reusable_examples": ["It is very good."],
                "tags": ["basic"],
            },
            "clip.md",
            "clip-002",
            "It is very good.",
        )
        self.assertGreaterEqual(frame.scores.japanese_speaker_lift or 0, 0.82)
        self.assertGreaterEqual(basic.scores.too_basic or 0, 0.85)


if __name__ == "__main__":
    unittest.main()
