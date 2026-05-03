# Contributing

Phrasify is early. Contributions are welcome once the standalone repository is public.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
PYTHONPATH=src python -m unittest discover -s tests -v
```

Core parsing and export tests should not call external LLM APIs. Use fixtures for provider-specific behavior.

## Pull Request Checklist

- Add or update tests for changed behavior.
- Keep provider-specific logic out of core parsing and export modules.
- Do not commit `.env`, generated outputs, API keys, personal transcripts, or personal Notion IDs.
- Update `README.md` when changing CLI behavior.

