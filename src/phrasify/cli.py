from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .aggregate import aggregate_jsonl, write_aggregated_jsonl
from .chunking import chunk_text
from .dedup import dedup_cards
from .env import load_env_files
from .exporters import write_csv, write_json, write_jsonl, write_notion_handoff
from .llm import PROVIDER_DEFAULT_MODEL, call_llm, load_prompt, require_provider_env
from .models import ExpressionCard, card_from_llm_item, card_from_record, validate_card
from .pathing import resolve_unique_path, sanitize_stem


HERE = Path(__file__).resolve().parent
TOOL_ROOT = HERE.parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phrasify",
        description="Extract reusable English expression cards from transcripts.",
    )
    sub = parser.add_subparsers(dest="command")

    extract = sub.add_parser("extract", help="Extract expression cards from one file")
    extract.add_argument("input", type=Path, help="Transcript path (.md/.txt/.srt/.vtt)")
    extract.add_argument(
        "--provider",
        choices=("anthropic", "openai"),
        default="anthropic",
        help="LLM provider (default: anthropic)",
    )
    extract.add_argument(
        "--model",
        default=None,
        help="Model name (default depends on provider)",
    )
    extract.add_argument(
        "--prompt",
        type=Path,
        default=None,
        help="Override extraction prompt path",
    )
    extract.add_argument(
        "--output-dir",
        type=Path,
        default=TOOL_ROOT / "outputs",
        help="Directory for generated files",
    )
    extract.add_argument(
        "--format",
        choices=("jsonl", "json", "csv"),
        default="jsonl",
        help="Primary output format",
    )
    extract.add_argument(
        "--max-expressions",
        type=int,
        default=30,
        help="Maximum cards after deduplication",
    )
    extract.add_argument(
        "--chunk-max-chars",
        type=int,
        default=12_000,
        help="Maximum characters per transcript chunk",
    )
    extract.add_argument(
        "--discard-invalid",
        action="store_true",
        help="Discard cards missing required DesignSpec fields",
    )
    extract.add_argument(
        "--notion-handoff",
        action="store_true",
        help="Also write a Notion MCP handoff JSON file",
    )
    extract.add_argument(
        "--dry-run",
        action="store_true",
        help="Load, clean, and chunk the transcript without calling an LLM",
    )
    extract.set_defaults(func=extract_command)

    aggregate = sub.add_parser("aggregate", help="Aggregate and deduplicate output JSONL files")
    aggregate.add_argument(
        "--input-dir",
        type=Path,
        default=TOOL_ROOT / "outputs",
        help="Directory containing phrasify JSONL outputs",
    )
    aggregate.add_argument(
        "--out",
        type=Path,
        default=TOOL_ROOT / "outputs" / "aggregated.jsonl",
        help="Aggregated JSONL output path",
    )
    aggregate.add_argument(
        "--exclude",
        nargs="*",
        default=["aggregated.jsonl"],
        help="JSONL filenames to skip",
    )
    aggregate.set_defaults(func=aggregate_command)

    export = sub.add_parser("export", help="Convert an existing phrasify JSONL file")
    export.add_argument("input", type=Path, help="Input phrasify JSONL file")
    export.add_argument(
        "--format",
        choices=("csv", "json"),
        default="csv",
        help="Output format (default: csv)",
    )
    export.add_argument("--out", type=Path, default=None, help="Output path")
    export.add_argument(
        "--notion-handoff",
        action="store_true",
        help="Also write a Notion MCP handoff JSON file",
    )
    export.set_defaults(func=export_command)

    return parser


def load_cards_from_jsonl(path: Path) -> list[ExpressionCard]:
    cards: list[ExpressionCard] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cards.append(card_from_record(json.loads(line)))
    return cards


def export_command(args: argparse.Namespace) -> int:
    if not args.input.exists():
        raise FileNotFoundError(args.input)
    cards = load_cards_from_jsonl(args.input)
    out_path = args.out or args.input.with_suffix("." + args.format)
    if args.format == "csv":
        write_csv(cards, out_path)
    else:
        write_json(cards, out_path)
    print(f"[export] cards={len(cards)} -> {out_path}")
    if args.notion_handoff:
        source_id = args.input.stem
        handoff_path = out_path.with_name(f"notion-batch-{source_id}.json")
        write_notion_handoff(cards, handoff_path, source_id=source_id, jsonl_path=args.input)
        print(f"[notion] {handoff_path}")
    return 0


def aggregate_command(args: argparse.Namespace) -> int:
    rows = aggregate_jsonl(args.input_dir, exclude=set(args.exclude))
    write_aggregated_jsonl(rows, args.out)
    total_occurrences = sum(row["frequency"] for row in rows)
    print(
        f"[aggregate] unique_expressions={len(rows)} "
        f"occurrences={total_occurrences} -> {args.out}"
    )
    return 0


def extract_command(args: argparse.Namespace) -> int:
    from .loaders import load_transcript

    load_env_files(TOOL_ROOT)
    document = load_transcript(args.input)
    chunks = chunk_text(
        document.text,
        source_stem=sanitize_stem(document.path.stem),
        max_chars=args.chunk_max_chars,
    )

    print(
        f"[phrasify] input={document.path} title={document.title!r} "
        f"chars={len(document.text)} chunks={len(chunks)}"
    )
    if args.dry_run:
        for chunk in chunks:
            print(
                f"[chunk] {chunk.chunk_id} chars={len(chunk.text)} "
                f"timestamp={chunk.timestamp or '-'}"
            )
        return 0

    model = args.model or PROVIDER_DEFAULT_MODEL[args.provider]
    require_provider_env(args.provider)
    prompt = load_prompt(args.prompt)

    cards: list[ExpressionCard] = []
    remaining = args.max_expressions
    for chunk in chunks:
        if remaining <= 0:
            break
        print(
            f"[extract] chunk={chunk.chunk_id} chars={len(chunk.text)} "
            f"provider={args.provider} model={model}"
        )
        items = call_llm(
            provider=args.provider,
            model=model,
            system_prompt=prompt,
            transcript=chunk.text,
            transcript_title=document.title,
            chunk_id=chunk.chunk_id,
            max_expressions=remaining,
        )
        for item in items:
            card = card_from_llm_item(
                item,
                source_file=str(document.path),
                chunk_id=chunk.chunk_id,
                transcript_text=chunk.text,
            )
            card.source.timestamp = card.source.timestamp or chunk.timestamp
            errors = validate_card(card)
            if errors:
                print(
                    f"[warn] invalid card expression={card.expression!r}: "
                    + "; ".join(errors),
                    file=sys.stderr,
                )
                if args.discard_invalid:
                    continue
            cards.append(card)
        remaining = max(0, args.max_expressions - len(cards))

    cards = dedup_cards(cards)[: args.max_expressions]
    for seq, card in enumerate(cards, start=1):
        card.seq = seq

    suffix = "." + args.format
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    out_path = resolve_unique_path(
        args.output_dir / f"{sanitize_stem(document.path.stem)}_{stamp}{suffix}"
    )
    if args.format == "jsonl":
        write_jsonl(cards, out_path)
    elif args.format == "json":
        write_json(cards, out_path)
    else:
        write_csv(cards, out_path)

    expression_hits = sum(1 for c in cards if c.expression_in_source)
    sentence_hits = sum(1 for c in cards if c.original_sentence_in_source)
    print(
        f"[verify] expression_in_source={expression_hits}/{len(cards)} "
        f"original_sentence_in_source={sentence_hits}/{len(cards)}"
    )
    print(f"[saved] {out_path}")

    if args.notion_handoff:
        handoff_path = resolve_unique_path(
            args.output_dir
            / f"notion-batch-{sanitize_stem(document.path.stem)}-{stamp}.json"
        )
        write_notion_handoff(
            cards,
            handoff_path,
            source_id=sanitize_stem(document.path.stem),
            jsonl_path=out_path if args.format == "jsonl" else None,
        )
        print(f"[notion] {handoff_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return int(args.func(args))
    except (FileNotFoundError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
