from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any


FRAME_PATTERNS = {
    "discourse_marker": [
        "that being said",
        "having said that",
        "with that in mind",
        "at the end of the day",
        "to be fair",
        "in other words",
        "put differently",
        "the way I see it",
    ],
    "hedge": [
        "I'm not fully convinced",
        "I would push back",
        "I tend to think",
        "it seems like",
        "to some extent",
        "I wouldn't necessarily",
        "I'm not sure I buy",
    ],
    "business_frame": [
        "double down on",
        "take a step back",
        "make the case for",
        "move the needle",
        "get conviction on",
        "pressure test",
    ],
}

COMMON_BASIC_PHRASES = {
    "i think",
    "very good",
    "really good",
    "it is good",
    "this is good",
    "thank you",
    "a lot of",
}

LEMMA_OVERRIDES = {
    "doubled": "double",
    "doubling": "double",
    "validated": "validate",
    "validating": "validate",
    "needed": "need",
    "needing": "need",
    "said": "say",
    "being": "be",
}


@dataclass(frozen=True)
class CandidateExpression:
    text: str
    kind: str
    source: str


@lru_cache(maxsize=1)
def load_spacy_model() -> Any | None:
    try:
        import spacy
    except ImportError:
        return None

    model_name = os.getenv("PHRASIFY_SPACY_MODEL", "en_core_web_sm")
    try:
        return spacy.load(model_name)
    except OSError:
        return None


def extract_candidate_expressions(text: str, max_items: int = 24) -> list[CandidateExpression]:
    candidates: list[CandidateExpression] = []
    candidates.extend(_regex_frame_candidates(text))

    nlp = load_spacy_model()
    if nlp is not None:
        doc = nlp(text)
        candidates.extend(_spacy_noun_chunk_candidates(doc))
        candidates.extend(_spacy_verb_phrase_candidates(doc))

    return _dedupe_candidates(candidates)[:max_items]


def build_candidate_hint_block(text: str, max_items: int = 24) -> str:
    candidates = extract_candidate_expressions(text, max_items=max_items)
    if not candidates:
        return ""
    lines = [
        "# Candidate expression hints",
        "Use these NLP candidates as hints only. Extract them only if they are "
        "native, reusable, and valuable for the learner.",
    ]
    for candidate in candidates:
        lines.append(f"- {candidate.text} [{candidate.kind}]")
    return "\n".join(lines)


def expression_in_source_by_lemma(expression: str, source_text: str) -> bool:
    if not expression or not source_text:
        return False
    if expression.lower() in source_text.lower():
        return True
    expression_lemmas = _lemmas(expression)
    source_lemmas = _lemmas(source_text)
    if not expression_lemmas or len(expression_lemmas) > len(source_lemmas):
        return False
    for start in range(0, len(source_lemmas) - len(expression_lemmas) + 1):
        if source_lemmas[start : start + len(expression_lemmas)] == expression_lemmas:
            return True
    return False


def apply_nlp_score_adjustments(scores: Any, expression: str, sentence: str) -> bool:
    changed = False
    frame_lift = _frame_lift_signal(expression)
    if frame_lift is not None:
        changed = _raise_score(scores, "japanese_speaker_lift", frame_lift) or changed
        changed = _raise_score(scores, "reusability", 0.75) or changed

    too_basic = _too_basic_signal(expression)
    if too_basic is not None:
        changed = _raise_score(scores, "too_basic", too_basic) or changed

    too_context_specific = _too_context_specific_signal(expression, sentence)
    if too_context_specific is not None:
        changed = _raise_score(scores, "too_context_specific", too_context_specific) or changed

    return changed


def _regex_frame_candidates(text: str) -> list[CandidateExpression]:
    candidates: list[CandidateExpression] = []
    for kind, phrases in FRAME_PATTERNS.items():
        for phrase in phrases:
            pattern = re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
            for match in pattern.finditer(text):
                candidates.append(
                    CandidateExpression(
                        text=_source_cased_text(match.group(0), phrase),
                        kind=kind,
                        source="regex",
                    )
                )
    return candidates


def _spacy_noun_chunk_candidates(doc: Any) -> list[CandidateExpression]:
    candidates: list[CandidateExpression] = []
    try:
        noun_chunks = list(doc.noun_chunks)
    except (NotImplementedError, ValueError):
        return candidates
    for chunk in noun_chunks:
        text = chunk.text.strip()
        if 2 <= len(text.split()) <= 5 and not _looks_too_basic(text):
            candidates.append(
                CandidateExpression(text=text, kind="noun_chunk", source="spacy")
            )
    return candidates


def _spacy_verb_phrase_candidates(doc: Any) -> list[CandidateExpression]:
    candidates: list[CandidateExpression] = []
    for token in doc:
        if token.pos_ not in {"VERB", "AUX"}:
            continue
        parts = [token]
        for child in token.children:
            if child.dep_ in {"prt", "prep", "dobj", "attr", "acomp"}:
                parts.append(child)
        if len(parts) < 2:
            continue
        ordered = sorted(parts, key=lambda t: t.i)
        if ordered[-1].i - ordered[0].i > 5:
            continue
        phrase = doc[ordered[0].i : ordered[-1].i + 1].text.strip()
        if 2 <= len(phrase.split()) <= 6:
            candidates.append(
                CandidateExpression(text=phrase, kind="verb_phrase", source="spacy")
            )
    return candidates


def _dedupe_candidates(candidates: list[CandidateExpression]) -> list[CandidateExpression]:
    deduped: list[CandidateExpression] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = re.sub(r"\s+", " ", candidate.text.lower()).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped


def _lemmas(text: str) -> list[str]:
    nlp = load_spacy_model()
    if nlp is not None:
        doc = nlp(text)
        return [
            token.lemma_.lower()
            for token in doc
            if not token.is_space and not token.is_punct
        ]
    return [_simple_lemma(token) for token in re.findall(r"[A-Za-z']+", text.lower())]


def _simple_lemma(token: str) -> str:
    if token in LEMMA_OVERRIDES:
        return LEMMA_OVERRIDES[token]
    if token.endswith("ing") and len(token) > 5:
        base = token[:-3]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        return base
    if token.endswith("ed") and len(token) > 4:
        base = token[:-2]
        if len(base) >= 2 and base[-1] == base[-2]:
            base = base[:-1]
        if base.endswith(("at", "iz", "is")):
            base += "e"
        return base
    if token.endswith("s") and len(token) > 4:
        return token[:-1]
    return token


def _frame_lift_signal(expression: str) -> float | None:
    lower = expression.lower()
    for phrases in FRAME_PATTERNS.values():
        if any(phrase.lower() in lower for phrase in phrases):
            return 0.82
    if re.search(r"\b(i would|i wouldn't|i tend to|the way i|that being said)\b", lower):
        return 0.78
    return None


def _too_basic_signal(expression: str) -> float | None:
    lower = re.sub(r"\s+", " ", expression.lower()).strip(" .,!?:;")
    if lower in COMMON_BASIC_PHRASES:
        return 0.85
    if len(lower.split()) == 1 and len(lower) <= 5:
        return 0.7
    return None


def _too_context_specific_signal(expression: str, sentence: str) -> float | None:
    text = f"{expression} {sentence}".strip()
    nlp = load_spacy_model()
    if nlp is not None:
        doc = nlp(text)
        token_count = sum(1 for token in doc if token.is_alpha)
        if token_count == 0:
            return None
        entity_tokens = {token.i for ent in doc.ents for token in ent}
        proper_tokens = {
            token.i for token in doc if token.pos_ == "PROPN" or token.i in entity_tokens
        }
        ratio = len(proper_tokens) / token_count
        if ratio >= 0.35:
            return 0.8
        if ratio >= 0.2:
            return 0.6
        return None

    tokens = re.findall(r"\b[A-Z][A-Za-z0-9&.-]+\b", text)
    content_tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9&.-]*\b", text)
    if content_tokens and len(tokens) / len(content_tokens) >= 0.35:
        return 0.7
    return None


def _raise_score(scores: Any, field_name: str, value: float) -> bool:
    current = getattr(scores, field_name, None)
    if current is None or current < value:
        setattr(scores, field_name, value)
        return True
    return False


def _source_cased_text(found: str, fallback: str) -> str:
    return found.strip() or fallback


def _looks_too_basic(text: str) -> bool:
    return re.sub(r"\s+", " ", text.lower()).strip(" .,!?:;") in COMMON_BASIC_PHRASES
