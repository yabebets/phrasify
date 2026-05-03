#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


EXCLUDED_PARTS = {
    ".git",
    ".mypy_cache",
    ".phrasify.local",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "outputs",
}

ALLOWLISTED_FILES = {
    Path("scripts/oss_check.py"),
    Path("tests/test_oss_check.py"),
}


@dataclass(frozen=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]


PATTERNS = [
    SecretPattern(
        "personal absolute path",
        re.compile(r"/Users/toshiakiyabe\b|/Users/[^/\s]+/exp\b"),
    ),
    SecretPattern(
        "EXP knowledge vault path",
        re.compile(r"\bKnowledge/Clips\b|\bKnowledge/英語"),
    ),
    SecretPattern(
        "literal API key assignment",
        re.compile(
            r"\b(?:OPENAI_API_KEY|ANTHROPIC_API_KEY|NOTION_API_KEY)\s*=\s*"
            r"(?!\s*(?:$|your-|<|example|replace-me|changeme|dummy))[^#\s]+",
            re.IGNORECASE,
        ),
    ),
    SecretPattern(
        "OpenAI key token",
        re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    SecretPattern(
        "Anthropic key token",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ),
    SecretPattern(
        "Notion token",
        re.compile(r"\bntn_[A-Za-z0-9_-]{20,}\b"),
    ),
    SecretPattern(
        "legacy private Notion id",
        re.compile(r"\b(?:745f3755|d55ebdaa)[a-f0-9-]*\b", re.IGNORECASE),
    ),
]


@dataclass(frozen=True)
class Finding:
    path: Path
    line_no: int
    pattern: str
    line: str


def should_skip(path: Path) -> bool:
    return any(part in EXCLUDED_PARTS for part in path.parts)


def list_candidate_files(root: Path) -> list[Path]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=root,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        paths = [root / line for line in proc.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.CalledProcessError):
        paths = [p for p in root.rglob("*") if p.is_file()]
    candidates = []
    for path in paths:
        rel = path.relative_to(root)
        if path.is_file() and rel not in ALLOWLISTED_FILES and not should_skip(rel):
            candidates.append(path)
    return candidates


def scan_file(path: Path) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    findings: list[Finding] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern in PATTERNS:
            if pattern.regex.search(line):
                findings.append(
                    Finding(
                        path=path,
                        line_no=line_no,
                        pattern=pattern.name,
                        line=line.strip(),
                    )
                )
    return findings


def scan_paths(paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in paths:
        findings.extend(scan_file(path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that Phrasify public files do not contain EXP-local secrets or paths."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root to scan. Defaults to the current directory.",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    findings = scan_paths(list_candidate_files(root))
    if not findings:
        print("[oss-check] ok")
        return 0

    print("[oss-check] blocked: possible private material found", file=sys.stderr)
    for finding in findings:
        rel = finding.path.relative_to(root)
        print(
            f"{rel}:{finding.line_no}: {finding.pattern}: {finding.line}",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
