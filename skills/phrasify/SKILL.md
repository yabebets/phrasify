---
name: phrasify
description: Use when the user wants to extract reusable business English expression cards from transcripts, convert Phrasify JSONL output to CSV, or prepare Notion handoff data. Guides Codex or Claude Code agents to run the local phrasify CLI safely, keep API keys private, and avoid project-specific paths in reusable workflows.
---

# Phrasify

Phrasify is a CLI for turning English transcripts into reusable expression cards for Japanese-native business English learners. It supports Markdown, text, SRT, and VTT inputs, then exports JSONL, JSON, CSV, or Notion handoff JSON.

## Locate the CLI

Prefer the local repository copy when present:

```bash
cd tools/phrasify
```

If the current project is the standalone Phrasify repo, use the repository root. If neither exists, check whether `phrasify` is already on `PATH` before asking the user where the repo is.

## First-time setup

Use editable install during development:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[anthropic]'
```

Use `'.[openai]'` instead when the user wants OpenAI. Basic dry-run, JSONL parsing, CSV export, and aggregation do not require provider SDKs.

Keep secrets local:

```bash
cp .env.example .env
```

Never print `.env` contents or API keys. `extract` sends transcript chunks to the selected LLM provider; `export` and `aggregate` are local-only.

## Workflow

1. Confirm the transcript path and desired output format.
2. Run dry-run first to verify loader and chunking:

```bash
.venv/bin/phrasify extract /path/to/transcript.md --dry-run
```

3. Run extraction only after dry-run looks reasonable:

```bash
.venv/bin/phrasify extract /path/to/transcript.md --provider anthropic --max-expressions 30
```

4. Convert existing JSONL to CSV when requested:

```bash
.venv/bin/phrasify export outputs/example_20260503.jsonl --format csv
```

5. Generate Notion handoff JSON when requested:

```bash
.venv/bin/phrasify export outputs/example_20260503.jsonl --format notion-handoff
```

Use `--notion-database-id` or `--notion-data-source-id` only when the user explicitly provides a target. Do not hardcode personal Notion IDs in commands, docs, tests, or code.

## Output Handling

Default generated files live under `outputs/`, which is gitignored except for `.gitkeep`. When reporting results, summarize:

- output file path
- number of cards
- whether CSV / JSONL / Notion handoff was produced
- any notable grounding metrics such as `expression_in_source` and `original_sentence_in_source`

Do not commit generated transcript outputs unless the user explicitly asks and the file contains no private material.

## Development Checks

Use the stdlib test suite:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

For packaging checks:

```bash
python3 -m venv /tmp/phrasify-check
/tmp/phrasify-check/bin/pip install -e .
/tmp/phrasify-check/bin/phrasify --help
```

Clean generated `__pycache__` and `*.egg-info` directories before committing if they appear.
