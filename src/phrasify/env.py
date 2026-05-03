from __future__ import annotations

import os
from pathlib import Path


def load_env_files(start: Path) -> None:
    """Load simple KEY=VALUE files without requiring python-dotenv."""
    candidates = [
        start / ".env",
        start / ".env.local",
        start.parent / ".env",
        start.parent / ".env.local",
        start.parent.parent / ".env.local",
        start.parent.parent / "lab" / ".env",
    ]
    for path in candidates:
        if path.exists():
            _load_env_file(path)


def _load_env_file(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
