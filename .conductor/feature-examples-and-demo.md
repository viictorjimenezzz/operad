# Feature · Unified examples config + `demo.py` showcase

**Addresses.** E-1 (ISSUES.md) + `TODO_EXAMPLES_SHARED_CONFIG` +
`TODO_DEMO_SCRIPT` in `missing.py`.

Two related deliverables that share a scope boundary (examples
directory + one top-level script). A single agent can land both.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-1.
- Every file under `examples/`.
- `operad/runtime/observers/rich.py` (for the demo).

---

## Part 1 — Unified examples config

Today the examples disagree: `memory_demo.py` hardcodes
`"qwen2.5-7b-instruct"`; `observer_demo.py` uses `"demo"`;
`eval_loop.py` uses `"offline"`; network examples default host to
`127.0.0.1:8080`; offline examples to `127.0.0.1:0`. Users can't just
`uv run python examples/<any>.py` and expect it to work.

### Canonical setup

Pick one runnable target:

- **Backend:** `llamacpp`
- **Host:** `127.0.0.1:9000` (user's port)
- **Model:** `google/gemma-4-e4b` (user's model)

### Shared helper

```python
# examples/_config.py
"""Shared config for network-backed examples.

All examples that talk to a real model server import `local_config()`.
Override via env vars if you have a different setup:

    OPERAD_LLAMACPP_HOST=127.0.0.1:9000
    OPERAD_LLAMACPP_MODEL=google/gemma-4-e4b
"""
from __future__ import annotations
import os
from operad import Configuration

DEFAULT_HOST = "127.0.0.1:9000"
DEFAULT_MODEL = "google/gemma-4-e4b"


def local_config(**overrides) -> Configuration:
    """Build a Configuration for the canonical local llama-server."""
    base: dict = dict(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", DEFAULT_HOST),
        model=os.environ.get("OPERAD_LLAMACPP_MODEL", DEFAULT_MODEL),
    )
    base.update(overrides)
    return Configuration(**base)
```

### Update every network example

Replace the per-file `Configuration(...)` construction with
`local_config(temperature=0.2, ...)` etc. Banner at the top of each
example now says:

```
# Requires a local llama-server serving google/gemma-4-e4b on 127.0.0.1:9000.
# Override via OPERAD_LLAMACPP_HOST and OPERAD_LLAMACPP_MODEL.
```

### Offline-only examples

`eval_loop.py`, `mermaid_export.py`, `evolutionary_demo.py` stay
offline — they use `FakeLeaf` or mock adapters. Don't drag them into
`local_config`. Add a banner:

```
# Runs offline — no model server required.
```

---

## Part 2 — `demo.py` showcase

A single top-level script that runs in ≤30 seconds against the local
gemma server and shows off the framework. Designed for iterm2 + fish;
uses the Rich observer for pretty output.

### Script outline

```python
# demo.py
"""operad showcase — run this once, love the framework forever.

Requires: local llama-server at 127.0.0.1:9000 serving google/gemma-4-e4b
(see examples/_config.py). Run with:

    uv run python demo.py
"""
```

1. **Build an agent.** Small ReAct-style composition — one `Reasoner`,
   one `Classifier`. Show `agent.operad()` output (the exact prompt
   the model will see).
2. **Print the Mermaid graph.** `to_mermaid(agent._graph)` → plain
   text inside a rich.panel.
3. **Live invocation.** Attach a `RichDashboardObserver`; run one
   call; watch the tree light up. Print the returned
   `OperadOutput.response` and the headline `hash_*` fields.
4. **Trace dump.** Use `TraceObserver` to capture the run; save to
   `/tmp/operad-demo-trace.json`; show the file path.
5. **Mutation + diff.** Apply `AppendRule(path="", rule="Be terse.")`
   to a clone; print `agent.diff(mutated)` — the human-readable
   AgentDiff rendering.

Each stage is a boxed section in Rich. Takes under 30 seconds
end-to-end against gemma-4-e4b.

### Acceptance for demo

- `uv run python demo.py` exits 0 on a working setup.
- No network call when `OPERAD_LLAMACPP_HOST` is unset and the
  server isn't running — print a one-line "start llama-server first"
  hint.
- Output fits in a standard 120-column terminal.

---

## Scope

- New: `examples/_config.py`.
- Edit: every network-backed example in `examples/` to use
  `local_config()`.
- Edit: banners at the top of each example (consistent wording).
- New: `demo.py` at repo root.
- Edit: `README.md` (add pointer under "Run the demo").
- Edit: `CLAUDE.md` (mention `_config.py` as the shared helper).

Do NOT:
- Add new dependencies. `demo.py` uses only what `observers` extra
  already installs.
- Break the offline examples by accidentally routing them through
  `local_config`.

---

## Acceptance

- `uv run pytest tests/` green (tests import examples).
- `uv run python examples/<any>.py` against a running gemma server
  works without editing the file.
- `uv run python demo.py` produces a clean, legible run in one
  terminal window.

---

## Watch-outs

- `Configuration(extra="forbid")` means every override in
  `local_config()` must be a real field. Typos raise.
- Don't hide the `OPERAD_OPENAI_MODEL` path in `federated.py` — that
  example legitimately needs both backends.
- Keep `_config.py` out of `operad/` — it's an examples helper, not
  public API. Underscore prefix signals "not-exported".
