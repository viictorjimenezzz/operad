# Feature · Tracing visibility — `operad.tracing.watch()` + env var + CLI `tail`

**Addresses.** E-11 (ISSUES.md) + `TODO_TRACING_WATCH` in `missing.py`.

`TraceObserver`, `JsonlObserver`, and `RichDashboardObserver` all exist
but the user must wire them manually. Add a one-liner convenience
surface so "see what my agents are doing" is immediate.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-11.
- `operad/runtime/observers/*`, `operad/runtime/trace.py`,
  `operad/cli.py`.

---

## Proposal

Three small deliverables, one agent:

### 1. `operad.tracing.watch()` context manager

```python
# operad/tracing.py
from contextlib import contextmanager
from pathlib import Path

@contextmanager
def watch(*, jsonl: str | Path | None = None, rich: bool = True):
    """Attach default observers for the duration of the block.

    with operad.tracing.watch():
        out = await agent(x)          # Rich dashboard + JSONL log

    Arguments default to the most useful combo: Rich TUI on, JSONL
    disabled. Pass `jsonl="trace.jsonl"` to record, `rich=False` to
    suppress the TUI (useful in CI).
    """
```

Under the hood: register observers, yield, unregister. Uses the
existing `ObserverRegistry`.

### 2. `OPERAD_TRACE` env-var auto-attach

Add module-level side-effect (guarded):

```python
# operad/tracing.py
import os
if (_path := os.environ.get("OPERAD_TRACE")):
    from .runtime.observers import JsonlObserver, registry
    registry.register(JsonlObserver(_path))
```

Use `operad.tracing` idiomatically: users `import operad.tracing`
at the top of their app; setting `OPERAD_TRACE=/tmp/run.jsonl`
starts logging with zero code changes.

### 3. `operad tail <trace.jsonl>` CLI

Add a subcommand to `operad/cli.py` that replays an NDJSON trace log
through a Rich live view. Pauses between events optional
(`--speed=1.0` by default, `--speed=0` for instant).

```
operad tail tests/cassettes/run-abc.jsonl --speed=0.5
```

Useful for post-mortem of a failed run.

---

## Required tests

`tests/test_tracing_watch.py`:

1. `with watch(): await agent(x)` — assert the registry has observers
   during the block and zero after.
2. Env-var path: set `OPERAD_TRACE=tmp/run.jsonl`, import
   `operad.tracing`, call an agent, assert the file has NDJSON lines.
3. `operad tail tests/cassettes/sample.jsonl --speed=0` exits 0 and
   prints the right number of events. Ship a tiny sample NDJSON.

---

## Scope

- New: `operad/tracing.py`.
- Edit: `operad/cli.py` (add `tail` subcommand).
- Edit: `operad/__init__.py` (re-export `tracing`).
- New: `tests/test_tracing_watch.py`, `tests/fixtures/sample_trace.jsonl`.
- Edit: `README.md` (add a 5-line "Tracing" section), `CLAUDE.md` (same).

Do NOT:
- Change the existing observer API.
- Auto-attach the Rich observer from the env var — TUIs should be
  explicit. Only the JSONL writer is auto-attached.
- Put `rich` in base deps — it's still optional (`observers` extra).

---

## Acceptance

- `uv run pytest tests/` green.
- `OPERAD_TRACE=/tmp/t.jsonl uv run python -c "import operad.tracing; import asyncio; ..."`
  produces NDJSON in `/tmp/t.jsonl`.
- `uv run operad tail /tmp/t.jsonl --speed=0` renders the run and
  exits.

---

## Watch-outs

- The env-var auto-attach is a module-level side-effect. Put a
  one-line note in the module docstring so readers aren't surprised.
- `Rich` import must be guarded; `tail` should degrade to plain text
  if rich isn't installed.
- Don't double-register when `watch()` is used inside a process that
  also has `OPERAD_TRACE` set.
