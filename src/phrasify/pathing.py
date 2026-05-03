from __future__ import annotations

import re
from pathlib import Path


def sanitize_stem(value: str) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return s.strip("_")[:90] or "transcript"


def resolve_unique_path(base: Path) -> Path:
    if not base.exists():
        return base
    stem, suffix = base.stem, base.suffix
    parent = base.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1

