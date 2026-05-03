from __future__ import annotations

import re

from .models import TranscriptChunk


TIMESTAMP_AT_START_RE = re.compile(r"^\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]\s*")
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?。！？])\s+")


def split_long_paragraph(paragraph: str, max_chars: int) -> list[str]:
    if len(paragraph) <= max_chars:
        return [paragraph]

    parts = [p.strip() for p in SENTENCE_BOUNDARY_RE.split(paragraph) if p.strip()]
    if len(parts) <= 1:
        return [paragraph[i : i + max_chars].strip() for i in range(0, len(paragraph), max_chars)]

    segments: list[str] = []
    current: list[str] = []
    current_len = 0
    for part in parts:
        if len(part) > max_chars:
            if current:
                segments.append(" ".join(current).strip())
                current = []
                current_len = 0
            segments.extend(
                part[i : i + max_chars].strip() for i in range(0, len(part), max_chars)
            )
            continue
        projected = current_len + (1 if current else 0) + len(part)
        if current and projected > max_chars:
            segments.append(" ".join(current).strip())
            current = [part]
            current_len = len(part)
            continue
        current.append(part)
        current_len = projected
    if current:
        segments.append(" ".join(current).strip())
    return [segment for segment in segments if segment]


def chunk_text(text: str, source_stem: str, max_chars: int = 12_000) -> list[TranscriptChunk]:
    if max_chars <= 500:
        raise ValueError("max_chars must be greater than 500")
    paragraphs = [
        segment
        for paragraph in re.split(r"\n\s*\n", text)
        for segment in split_long_paragraph(paragraph.strip(), max_chars)
        if segment
    ]
    chunks: list[TranscriptChunk] = []
    current: list[str] = []
    current_start = 0
    cursor = 0
    current_ts: str | None = None

    def flush(end: int) -> None:
        nonlocal current, current_start, current_ts
        if not current:
            return
        idx = len(chunks) + 1
        chunks.append(
            TranscriptChunk(
                chunk_id=f"{source_stem}-{idx:03d}",
                text="\n\n".join(current).strip(),
                start_char=current_start,
                end_char=end,
                timestamp=current_ts,
            )
        )
        current = []
        current_ts = None

    for paragraph in paragraphs:
        start = text.find(paragraph, cursor)
        if start == -1:
            start = cursor
        end = start + len(paragraph)
        cursor = end
        ts_match = TIMESTAMP_AT_START_RE.match(paragraph)
        if current and sum(len(p) + 2 for p in current) + len(paragraph) > max_chars:
            flush(start)
            current_start = start
        if not current:
            current_start = start
            current_ts = ts_match.group("ts") if ts_match else None
        current.append(paragraph)

    flush(len(text))
    if not chunks and text.strip():
        chunks.append(
            TranscriptChunk(
                chunk_id=f"{source_stem}-001",
                text=text.strip(),
                start_char=0,
                end_char=len(text),
            )
        )
    return chunks
