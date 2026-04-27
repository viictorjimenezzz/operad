# 1-1 — package skeleton, tiers, CLI scaffolding

**Batch:** 1 · **Parallelizable with:** 1-2, 1-3, 1-4, 1-5 · **Depends on:** —

You are creating the package shell that every other task will fill in.
Your code must be importable and your CLI parser must dispatch correctly
*before* any other task runs.

## Goal

Stand up `apps/uthereal/` as an editable install in the operad monorepo.
Provide the tier-to-Configuration map, the CLI parser dispatcher with
every subcommand stubbed, and module-level errors. Nothing else.

## Files to create

| Path | Purpose |
|---|---|
| `apps/uthereal/pyproject.toml` | editable install, mirroring `apps/studio/pyproject.toml` |
| `apps/uthereal/README.md` | one-paragraph stub; full README is owned by 5-1 |
| `apps/uthereal/apps_uthereal/__init__.py` | `__version__ = "0.1.0"`; nothing else |
| `apps/uthereal/apps_uthereal/tiers.py` | `tier_to_config` |
| `apps/uthereal/apps_uthereal/errors.py` | structured exceptions |
| `apps/uthereal/apps_uthereal/cli.py` | argparse dispatcher |
| `apps/uthereal/apps_uthereal/commands/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/commands/_stub.py` | `NotImplementedStub(owner)` helper |
| `apps/uthereal/apps_uthereal/schemas/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/leaves/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/retrieval/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/workflow/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/feedback/__init__.py` | empty |
| `apps/uthereal/apps_uthereal/train/__init__.py` | empty |
| `apps/uthereal/tests/__init__.py` | empty |
| `apps/uthereal/tests/conftest.py` | shared pytest fixtures |
| `apps/uthereal/tests/test_tiers.py` | tests for `tier_to_config` |
| `apps/uthereal/tests/test_cli.py` | dispatcher smoke test |

You will also **modify** the root `/Users/viictorjimenezzz/Documents/operad/pyproject.toml`
to add `apps/uthereal` as a workspace member (and to add the script
entry point). Do this once, atomically, and make sure no existing
workspace member is dropped or reordered.

## API surface

```python
# apps_uthereal/tiers.py
from operad import Configuration

TIER_FAST: str = "fast"
TIER_THINKING_LOW: str = "thinking_low"
TIER_THINKING_HIGH: str = "thinking_high"
RECOGNIZED_TIERS: frozenset[str] = frozenset({TIER_FAST, TIER_THINKING_LOW, TIER_THINKING_HIGH})

def tier_to_config(tier: str, *, overrides: dict | None = None) -> Configuration:
    """Map a uthereal `llm_tier` to a Gemini-backed operad Configuration.

    Raises `LoaderError(reason="unknown_tier", tier=tier)` for unknown values.
    `overrides` is a flat dict of attribute paths (e.g. `{"sampling.temperature": 0.0}`)
    applied after the base config is constructed; intended for tests and one-off
    runs, not for production use.
    """

# apps_uthereal/errors.py
class UtherealBridgeError(Exception): ...
class LoaderError(UtherealBridgeError):
    def __init__(self, *, reason: str, **details): ...
class RetrievalError(UtherealBridgeError):
    def __init__(self, *, reason: str, **details): ...
class TraceError(UtherealBridgeError):
    def __init__(self, *, reason: str, **details): ...

# apps_uthereal/cli.py
def main(argv: list[str] | None = None) -> int:
    """Entry point exposed via `apps-uthereal` script."""
```

The `commands/` subpackage convention (used by all command-owning tasks):
each command module exports `add_parser(subparsers) -> None` and
`async def run(args) -> int`. The dispatcher in `cli.py` collects them
by importlib walk; you provide the walker and a `_stub.py` helper that
later commands import from when not yet implemented.

## Implementation notes

- **Tiers.** All three tiers map to Gemini. Use placeholder model names
  (`"gemini-2.5-flash"`, `"gemini-2.5-pro"`, `"gemini-2.5-pro-thinking"`
  or whatever Gemini publishes — pick one consistent naming pattern).
  The exact strings are your call; document them in the module
  docstring. Backend is `"gemini"`. Sampling defaults: `temperature=0.0`,
  `max_tokens=2048` for the structured-output leaves; allow override via
  `overrides=`.
- **`pyproject.toml`** mirrors `apps/studio/pyproject.toml`. Dependencies:
  `operad`, `pydantic>=2`, `pyyaml>=6`, `ruamel.yaml>=0.18`, `httpx>=0.27`.
  Dev group: `pytest>=8`, `pytest-asyncio>=0.23`, `respx>=0.20`.
  Script: `apps-uthereal = "apps_uthereal.cli:main"`.
- **CLI dispatcher.** Use `argparse` (operad already does, see
  `examples/benchmark/run.py`). Commands enumerated in C11 of the
  contracts. Every subcommand defaults to `_stub.run(owner=...)`,
  which raises `NotImplementedError("Owner: <task-id>")` and exits with
  code 2.
- **Async commands.** The dispatcher resolves `args.func`; if it returns
  a coroutine, `asyncio.run` it.
- **Logging.** `logger = logging.getLogger("apps_uthereal")` at module
  top. CLI sets up basic config in `main()` only; library code never
  configures logging.
- **Run directory.** Provide `apps_uthereal.paths.runs_dir() -> Path`
  returning `Path.cwd() / ".uthereal-runs"`, creating it lazily. Used
  by every command (so it's foundational). Add this to `paths.py` in
  the package root.

## Acceptance criteria

- [ ] `uv sync` succeeds from a clean checkout including `apps/uthereal`.
- [ ] `uv run python -c "from apps_uthereal import tier_to_config; print(tier_to_config('fast'))"` prints a `Configuration` with `backend='gemini'`.
- [ ] `uv run apps-uthereal --help` prints usage with all six subcommands listed.
- [ ] `uv run apps-uthereal run --entry /tmp/x` exits with code 2 and an `Owner: 4-1` message.
- [ ] `tier_to_config("nonsense")` raises `LoaderError(reason="unknown_tier", tier="nonsense")`.
- [ ] `apps_uthereal.paths.runs_dir()` returns the resolved path; the directory is created if missing.
- [ ] No file in any sibling task's owned set is touched.
- [ ] All tests in `tests/test_tiers.py` and `tests/test_cli.py` pass.

## Tests

- `test_tier_to_config_returns_gemini_for_each_tier` — parametrized over `TIER_FAST`, `TIER_THINKING_LOW`, `TIER_THINKING_HIGH`.
- `test_tier_to_config_unknown_tier_raises_LoaderError`.
- `test_tier_to_config_overrides_apply` — pass `overrides={"sampling.temperature": 0.5}` and assert the resulting `Configuration.sampling.temperature`.
- `test_cli_help_contains_all_subcommands` — assert substrings `"run"`, `"show"`, `"feedback"`, `"blame"`, `"fix"`, `"verify"`.
- `test_cli_run_returns_2_with_owner_message` — capture stderr / argv error message.
- `test_cli_show_with_no_args_returns_2`.

## References

- `apps/studio/pyproject.toml` — sibling app pyproject pattern.
- `apps/studio/operad_studio/cli.py` — CLI entry point pattern.
- `examples/benchmark/run.py` — argparse pattern.
- `operad/core/models.py` — `Configuration` shape.

## Notes

(Append discoveries here as you implement.)
