from __future__ import annotations

import re
from pathlib import Path

from .cleaning import extract_markdown_transcript_sections, normalize_transcript_text
from .models import TranscriptDocument


SUPPORTED_SUFFIXES = {".md", ".txt", ".srt", ".vtt"}


def parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    if not raw.startswith("---"):
        return {}, raw
    end = raw.find("\n---", 3)
    if end == -1:
        return {}, raw
    block = raw[3:end].strip()
    body = raw[end + 4 :].lstrip("\n")
    fm: dict[str, str] = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip()
        fm[key] = value.strip('"').strip("'")
    return fm, body


def load_transcript(path: Path) -> TranscriptDocument:
    path = path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
        raise ValueError(f"unsupported transcript type: {path.suffix}; expected {supported}")

    raw = path.read_text(encoding="utf-8")
    frontmatter: dict[str, str] = {}
    body = raw
    if path.suffix.lower() == ".md":
        frontmatter, body = parse_frontmatter(raw)
        body = extract_markdown_transcript_sections(body)

    text = normalize_transcript_text(body)
    title = frontmatter.get("title") or path.stem
    return TranscriptDocument(path=path, title=title, text=text, frontmatter=frontmatter)

