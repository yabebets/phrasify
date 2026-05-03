from __future__ import annotations

import re


TIMESTAMP_RE = re.compile(
    r"(?:(?:\d{1,2}:)?\d{1,2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?:(?:\d{1,2}:)?\d{1,2}:\d{2}[,.]\d{3})(?:\s+.*)?"
)


def strip_subtitle_artifacts(text: str) -> str:
    lines: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        if line.upper() == "WEBVTT":
            continue
        if line.isdigit():
            continue
        if TIMESTAMP_RE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines)


def normalize_transcript_text(text: str) -> str:
    text = text.replace("\ufeff", "")
    text = strip_subtitle_artifacts(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_markdown_transcript_sections(body: str) -> str:
    """Prefer common transcript sections, fallback to the whole markdown body."""
    headers = {"## 全文", "## 原文抜粋", "## Transcript", "## transcript"}
    lines = body.splitlines()
    keep: list[str] = []
    include = False
    for line in lines:
        if line.startswith("## "):
            include = line.strip() in headers
            if include:
                keep.append(line)
            continue
        if include:
            keep.append(line)
    joined = "\n".join(keep).strip()
    return joined if joined else body

