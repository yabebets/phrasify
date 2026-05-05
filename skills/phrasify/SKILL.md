---
name: phrasify
description: Use when the user wants to extract reusable English expression cards from transcripts, customize extraction profiles, convert Phrasify JSONL output to CSV, or prepare Notion handoff data. Guides Codex or Claude Code agents to run the local phrasify CLI safely, keep API keys private, and avoid project-specific paths in reusable workflows.
---

# Phrasify

Phrasify is a CLI for turning English transcripts into reusable expression cards. It ships with a Japanese business English extraction profile by default, but users can customize the learner, domains, expression focus, and explanation language. It supports Markdown, text, SRT, VTT, YouTube URL, and Podcast URL inputs, then exports JSONL, JSON, CSV, or Notion handoff JSON.

## Locate the CLI

Prefer the current repository root when it contains `pyproject.toml` and `src/phrasify/`. Otherwise, look for a nearby Phrasify checkout before asking the user where it is.

```bash
cd /path/to/phrasify
```

If no local checkout is present, check whether `phrasify` is already on `PATH`.

## First-time setup

Use editable install during development:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[anthropic]'
```

Use `'.[openai]'` instead when the user wants OpenAI. Basic dry-run, JSONL parsing, CSV export, and aggregation do not require provider SDKs.

For YouTube / Podcast URL input, install the media extra:

```bash
.venv/bin/pip install -e '.[media,anthropic]'
```

URL input saves a fetched transcript Markdown under `outputs/transcripts/` before extraction. YouTube uses captions first. Podcast input tries published transcript URLs, Spotify episode metadata plus Apple RSS audio transcription, and YouTube captions fallback. OpenAI audio transcription requires `OPENAI_API_KEY`; long audio also needs `ffmpeg`.

Extraction profiles can be passed with `--profile path/to/profile.toml`. Quick overrides are also available: `--learner`, `--learner-level`, `--explanation-language`, `--domains`, and `--focus`. Use these when the user wants Phrasify tuned for a learner other than the default Japanese business English audience.

Users can also generate a profile from natural language:

```bash
.venv/bin/phrasify profile create \
  "I am a French founder preparing for investor updates." \
  --out profiles/founder_updates_fr.toml \
  --provider anthropic
```

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

For URL input:

```bash
.venv/bin/phrasify extract "https://www.youtube.com/watch?v=VIDEO_ID" --dry-run
```

3. Run extraction only after dry-run looks reasonable:

```bash
.venv/bin/phrasify extract /path/to/transcript.md --provider anthropic --max-expressions 30
```

For a custom learner/domain profile:

```bash
.venv/bin/phrasify extract /path/to/transcript.md \
  --profile examples/software_engineering_profile.toml \
  --provider anthropic
```

If the user describes their learning goals informally and wants reusable settings, create a profile first with `phrasify profile create`, then run `extract --profile <generated-profile>`.

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
