# 1-3 — YAML loader / dumper

**Batch:** 1 · **Parallelizable with:** 1-1, 1-2, 1-4, 1-5 · **Depends on:** —

You are building the I/O layer that turns a uthereal YAML into a typed
operad `Agent` and back. The round-trip property in C5 of the contracts
is binding.

## Goal

Implement `load_yaml` and `dump_yaml`, plus the example parser. The
loader is generic over the operad agent class — it does not know about
any specific leaf — so you test it against a fake leaf class defined in
the test file.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/leaves/_common.py` | the loader, dumper, example parser, type registry |
| `apps_uthereal/leaves/__init__.py` | already exists (empty); leave it empty |
| `apps_uthereal/tests/test_loader.py` | exhaustive tests using a fake leaf class |
| `apps_uthereal/tests/fixtures/yamls/fake_leaf.yaml` | test fixture |
| `apps_uthereal/tests/fixtures/yamls/fake_leaf_with_closure.yaml` | tests closure→task merge |

## API surface

```python
# apps_uthereal/leaves/_common.py
from __future__ import annotations

from pathlib import Path
from typing import Any
from operad import Agent, Configuration, Example
from apps_uthereal.errors import LoaderError
from apps_uthereal.tiers import tier_to_config

In = TypeVar("In", bound=BaseModel)
Out = TypeVar("Out", bound=BaseModel)

CLOSURE_SEPARATOR: str = "\n\n## Output\n\n"

def load_yaml(
    path: Path,
    leaf_cls: type[Agent[In, Out]],
    *,
    config_overrides: dict | None = None,
) -> Agent[In, Out]:
    """Construct an instance of `leaf_cls` populated from a uthereal YAML.

    Populates: role, task (with closure appended via CLOSURE_SEPARATOR),
    rules (tuple), examples (tuple of Example[In, Out]), config (via
    tier_to_config).

    Raises LoaderError with a structured `reason` for malformed YAMLs:
        - "missing_field" with `field=<name>`
        - "unknown_tier" with `tier=<value>`
        - "example_validation_failed" with `index=<i>` and `errors=...`
        - "yaml_parse_failed" with `parser_error=<str>`

    Examples that fail to validate are warned and dropped, NOT raised, by
    default. Pass `strict_examples=True` to raise instead.
    """

def dump_yaml(agent: Agent, path: Path, *, source_path: Path | None = None) -> None:
    """Write the agent's current parameter state back to YAML.

    If `source_path` is provided, comment and ordering preservation is
    attempted by round-tripping through ruamel.yaml against the source
    file. If absent, write a fresh YAML in the canonical order.

    Round-trip property (C5): for any agent A loaded from path,
        load_yaml(path, type(A))
        ↔ dump_yaml(A, tmp_path)
        ↔ load_yaml(tmp_path, type(A))
    yields agents with equal `hash_content`.
    """

def parse_examples(
    raw: list[dict],
    leaf_cls: type[Agent[In, Out]],
    *,
    strict: bool = False,
) -> tuple[Example[In, Out], ...]:
    """Convert YAML example dicts to operad Example objects.

    Each YAML example is `{input: <str-or-dict>, output: <dict>}`. When
    `input` is a string (free-text wrapped in `<tags>`), parse it into
    the input schema by:
      1. If the schema has exactly one string field, route the whole
         text into that field.
      2. Otherwise, use a tag parser: `<field>value</field>` patterns,
         missing fields use schema defaults.

    `output` is always a dict; coerce via leaf_cls.output.model_validate.

    Validation failures: warn + drop in non-strict mode; raise
    LoaderError(reason="example_validation_failed") in strict mode.
    """

def split_closure_from_task(task: str) -> tuple[str, str]:
    """Inverse of the closure→task merge. Returns (task_body, closure).

    If task does not contain CLOSURE_SEPARATOR, returns (task, "").
    """
```

## Implementation notes

- **YAML library: `ruamel.yaml`, not `pyyaml`.** Initialize in round-trip
  mode (`YAML(typ="rt")`) so comments, multiline block style (`|`), and
  key ordering are preserved on dump. `pyyaml` is acceptable only inside
  `parse_examples` for the example-input string-to-tag parsing, never
  for the structural YAML I/O.
- **Closure handling.** YAMLs include a `closure:` field with output
  formatting instructions. Append it to `task` with `CLOSURE_SEPARATOR`
  on load; split it back on dump. Keep the separator as an exact
  constant so the split is unambiguous.
- **Type rewriting.** YAML `output: uthereal_workflow.…schemas.X` paths
  must NOT be interpreted as importable. The loader ignores the `output`
  field on YAML — the typed schema comes from `leaf_cls.output`. The
  `output:` field is preserved on dump as YAML metadata only (don't
  rewrite it; just round-trip whatever was there).
- **Configuration.** Read `config.llm_tier`, call `tier_to_config(tier,
  overrides=config_overrides)`. Errors here are `LoaderError`. Other
  fields under `config:` (`model_kwargs`, `client_kwargs`,
  `tracer_inputs`) are preserved as YAML metadata for dump but ignored
  on load.
- **Closure-merge stability.** `dump_yaml` should produce the same
  YAML bytes (modulo timestamp / ordering) for an unmodified agent
  loaded from the same path. The test suite enforces this with a
  byte-equality assertion when no parameter changed.
- **Example tag parser.** Most YAMLs use ad-hoc XML-like
  `<field>value</field>` tags in example inputs (see
  `agent_context_safeguard.yaml`). Implement a small parser that:
  1. Finds all top-level `<tag>...</tag>` segments via regex.
  2. Maps each tag to a field on the input schema.
  3. Falls back to schema defaults for missing fields.
  Newline preservation matters. Test exhaustively.
- **Strict vs non-strict examples.** YAML examples often drift from the
  schema (typos, fields renamed). Don't bring down the whole loader for
  a bad example — log a warning and drop. The loader logs at WARNING
  with the example index and the validation error. CI can run with
  `strict_examples=True` to enforce; production loads with `strict=False`.

## Acceptance criteria

- [ ] `load_yaml(fixture_path, FakeLeaf)` returns a built or unbuilt agent with
  populated `role`, `task`, `rules`, `examples`, and `config`.
- [ ] The loaded agent's `task` contains the closure as a trailing section.
- [ ] `dump_yaml` followed by `load_yaml` produces an agent with equal
  `hash_content`.
- [ ] When the source YAML is unmodified, `dump_yaml(agent, p,
  source_path=original)` produces byte-equal output (modulo trailing
  newline).
- [ ] An unknown `llm_tier` raises `LoaderError(reason="unknown_tier")`.
- [ ] A missing `prompt:` block raises
  `LoaderError(reason="missing_field", field="prompt")`.
- [ ] A malformed example (output dict fails validation) is dropped with
  a warning; same example with `strict_examples=True` raises.
- [ ] Comments in the source YAML are preserved on round-trip.
- [ ] Multi-line block style (`role: |`) is preserved.

## Tests

- `test_load_minimal_yaml_returns_typed_agent`
- `test_closure_merged_into_task`
- `test_split_closure_inverse`
- `test_round_trip_preserves_hash_content`
- `test_round_trip_preserves_byte_equality_when_unchanged`
- `test_round_trip_preserves_comments` — assert `# comment` survives
- `test_round_trip_preserves_block_style` — assert `|` style survives
- `test_unknown_tier_raises_LoaderError`
- `test_missing_prompt_raises_LoaderError`
- `test_examples_with_invalid_output_dropped_in_non_strict`
- `test_examples_with_invalid_output_raise_in_strict`
- `test_example_tag_parser_extracts_fields_correctly` — parametrize over multiple tag formats
- `test_example_tag_parser_handles_missing_fields_with_defaults`
- `test_dump_includes_unrecognized_yaml_keys` — e.g. `agent_name`, `instrument`, `tracer_inputs`
- `test_load_propagates_config_overrides`

## Fixtures

`tests/fixtures/yamls/fake_leaf.yaml`:

```yaml
agent_name: FakeLeaf
config:
  llm_tier: "fast"
prompt:
  role: "You are a fake."
  task: "Do fake things."
  rules:
    - "Always be fake."
    - "Never be real."
  examples:
    - input: "<question>What is fake?</question>"
      output:
        answer: "Everything fake."
  closure: "Output a fake answer."
```

The fake leaf class for tests:

```python
class FakeLeafIn(BaseModel):
    question: str = ""
class FakeLeafOut(BaseModel):
    answer: str = ""
class FakeLeaf(Agent[FakeLeafIn, FakeLeafOut]):
    input = FakeLeafIn
    output = FakeLeafOut
```

## References

- `operad/core/agent.py` — `Agent.__init__`, `Example`, `hash_content`.
- `operad/agents/safeguard/components/context.py` — typical leaf class
  with `cleandoc` rules and structured examples.
- `ruamel.yaml` documentation for round-trip mode (`YAML(typ="rt")`).

## Notes

- This checkout did not yet contain the task 1-1 `apps/uthereal/`
  scaffold, `apps_uthereal.errors`, or `apps_uthereal.tiers`. The loader
  imports those modules when present and uses narrow local fallbacks only
  when they are absent, so the integrated branch should naturally prefer
  the scaffold-owned implementations.
- The root project in this checkout did not declare `ruamel.yaml`, though
  the contract requires it. Verification was run with `uv run --with
  ruamel.yaml ...`.
