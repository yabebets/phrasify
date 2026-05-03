from __future__ import annotations

import re

from .models import ExpressionCard


def normalize_expression(expression: str) -> str:
    s = expression.strip().lower()
    s = re.sub(r"[‘’“”]", "'", s)
    s = re.sub(r"\s+", " ", s)
    return s.rstrip(".,;:!?")


def dedup_cards(cards: list[ExpressionCard]) -> list[ExpressionCard]:
    seen: dict[str, ExpressionCard] = {}
    for card in cards:
        key = normalize_expression(card.expression)
        if not key:
            continue
        existing = seen.get(key)
        if existing is None:
            seen[key] = card
            continue
        # Prefer grounded cards; otherwise keep the first stable record.
        existing_score = int(bool(existing.expression_in_source)) + int(
            bool(existing.original_sentence_in_source)
        )
        card_score = int(bool(card.expression_in_source)) + int(
            bool(card.original_sentence_in_source)
        )
        if card_score > existing_score:
            seen[key] = card
    out = list(seen.values())
    for seq, card in enumerate(out, start=1):
        card.seq = seq
    return out

