# Contributing

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Local checks

```bash
ruff check .
pytest
```

## Development principles

- Keep exports deterministic and CI-friendly.
- Prefer explicit configuration over hidden behavior.
- Add tests for new config options and command generation logic.

## Pull request checklist

- Add or update tests.
- Update planning/spec docs if behavior changes.
- Keep backward compatibility unless change is intentionally breaking.
