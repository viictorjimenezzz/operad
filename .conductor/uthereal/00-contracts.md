# 00 — Core contracts

These are invariants every task respects. If your brief and this document
disagree, this document wins. If something you need is not here, **stop
and ask** — do not freelance shared types.

The contracts are organized by concern. Each contract has an ID
(`C1`, `C2`, ...) you can cite in PRs and in your `## Notes` section.

---

## C1 — File ownership

Every Python file in `apps/uthereal/` is owned by exactly one task.
The first non-blank line of each file's docstring (after
`from __future__ import annotations`) names the owning task:

```python
"""...

Owner: 1-3-yaml-loader.
"""
```

Tasks in later batches may **import from** files owned by earlier tasks.
They must **never modify** them. If a contract change is needed, propose
an amendment in your `## Notes` section — do not edit the contracts file
in line.

The skeleton task (1-1) is the only task that touches the root
`pyproject.toml` (to add `apps/uthereal` as a workspace member).

---

## C2 — No uthereal-src dependency

`apps/uthereal/` MUST NOT import any of:

- `uthereal_src.*`
- `uthereal_workflow.*`
- `uthereal_core.*`
- `uthereal_apps.*`
- `uthereal_infra.*`

YAMLs from `selfserve/` are **read** as plain text via `pyyaml` /
`ruamel.yaml`. Schemas referenced by the YAMLs are **vendored** as
Python in `apps_uthereal/schemas/` (task 1-2). The original YAML's
`output: uthereal_workflow…` paths are rewritten to vendored paths
during `load_yaml`.

Two consequences:

- The bridge package can be installed in a venv that does not have
  uthereal-src on `PYTHONPATH`.
- The CI for `apps/uthereal/` does not need uthereal-src to pass.

---

## C3 — Vendored schemas are immutable post-batch-1

After task 1-2 completes, schemas in `apps_uthereal/schemas/` are
immutable. Each schema file has a header indicating its upstream:

```python
"""Vendored from
uthereal_workflow.agentic_workflows.chat.selfserve.input.schemas.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""
```

If a later task requires a schema modification, it must propose an
amendment to this document, with sign-off, before any code changes. The
default answer is "vendor a new sibling schema, don't mutate the
canonical one."

---

## C4 — Configuration is tier-driven

Every leaf agent's `Configuration` is produced by the function in task
1-1:

```python
from apps_uthereal.tiers import tier_to_config

leaf_config = tier_to_config(yaml_dict["config"]["llm_tier"])
```

Hardcoding model names is forbidden. Recognized tiers:

```
{"fast", "thinking_low", "thinking_high"}
```

All three resolve to Gemini variants (the user's deployment is
Gemini-only). The exact model strings are owned by task 1-1; do not
inline them anywhere else.

If a YAML's `config.llm_tier` is unrecognized, `load_yaml` raises a
structured `LoaderError(reason="unknown_tier", tier=value)`. Never
silently fall back to a default tier.

---

## C5 — YAML I/O is loader-mediated

All YAML reads go through:

```python
from apps_uthereal.leaves._common import load_yaml, dump_yaml

leaf = load_yaml(path, leaf_cls=ContextSafeguardLeaf)
dump_yaml(leaf, path)
```

**Round-trip property.** For any agent `A` loaded from `path`,
`dump_yaml(A, path2)` followed by `load_yaml(path2, type(A))` produces an
agent with `A.hash_content == loaded.hash_content`.

**Format preservation.** Round-trip MUST preserve YAML formatting (key
order, comments, multi-line block style) when no parameter has changed.
Use `ruamel.yaml` round-trip mode — not `pyyaml`. Comments matter; the
upstream YAMLs use load-bearing section markers (`# === PART A ===`).

**Field mapping.**

| YAML path | Operad agent attribute |
|---|---|
| `prompt.role` | `Agent.role` |
| `prompt.task` | `Agent.task` |
| `prompt.rules` (list) | `Agent.rules` (tuple) |
| `prompt.examples` (list) | `Agent.examples` (tuple of `Example[In, Out]`) |
| `prompt.closure` | appended to `Agent.task` with separator `\n\n## Output\n\n` |
| `config.llm_tier` | `Configuration` via `tier_to_config` |
| `config.tracer_inputs` | dropped on load; preserved on dump (round-trip metadata) |
| `agent_name`, `workflow_name`, `agent_description`, `instrument` | preserved on dump as YAML-only metadata |

The `closure → task` merge is one-way at load time. On dump, if the
loaded agent's `task` still contains the original closure section
verbatim, split it back; otherwise keep everything in `task` and write
empty `closure`.

---

## C6 — Retrieval is Protocol-mediated

All retrieval calls go through the `RetrievalClient` Protocol from
`apps_uthereal.retrieval.client` (task 1-4). Direct HTTP calls to a RAG
service are forbidden anywhere except inside `LiveRetrievalClient`.

```python
from apps_uthereal.retrieval.client import (
    RetrievalClient, LiveRetrievalClient, CassetteRetrievalClient,
    RetrievalError,
)
```

The Protocol surface:

```python
class RetrievalClient(Protocol):
    async def retrieve(
        self,
        spec: "RetrievalSpecification",
        *,
        workspace_id: str,
    ) -> "RetrievalResult": ...

    async def get_workspace_metadata(
        self,
        workspace_id: str,
    ) -> "WorkspaceMetadata": ...
```

The default in tests, in `apps-uthereal show / blame / fix / verify`,
and inside any code path that doesn't explicitly need network I/O, is
`CassetteRetrievalClient(inner=None, mode="replay")`.

`apps-uthereal run` is the only command that may use a Live client; it
wraps it in `CassetteRetrievalClient(mode="record-missing")` so the
recorded cassette is on disk before any other command runs.

---

## C7 — Tracing is observer-driven

When `ArtemisRunner.__call__(x)` runs, it installs a
`WorkflowTraceObserver` on operad's observer registry for the duration
of the call. Every leaf invocation produces exactly one `TraceFrame`.

Tasks that need to introspect a run **consume** the resulting
`WorkflowTrace` — they do not subscribe their own observers. The runner
is the only owner of an active observer registration.

The trace is emitted to two places:

- In-memory: returned by the runner alongside the typed final answer
  (`(answer, trace)` tuple from a public method on the runner — see 3-1).
- On disk: written to `<run_dir>/trace.jsonl` by `apps-uthereal run`
  (task 4-1).

---

## C8 — Cassette policy

Every dataset entry has its own cassette directory:

```
.uthereal-runs/<entry_id>/cassettes/
├── llm/   — operad's standard cassette files keyed by hash_prompt+hash_input+hash_model
└── rag/   — RAG cassettes keyed by sha256(workspace_id || canonical_json(spec))[:16]
```

`entry_id = sha256(canonical_json(entry))[:12]`. The canonical JSON is
field-sorted, no whitespace, UTF-8.

Modes (passed through env var or CLI flag):

| Mode | Behavior |
|---|---|
| `record` | First run for an entry. Misses are recorded. |
| `replay` | Strict. Misses raise `CassetteMiss` / `RetrievalError`. |
| `record-missing` | Partial. Replays hits, records misses, leaves a record-marker note in the run report. |

Defaults:

- `apps-uthereal run` → `record-missing` (so first runs record, repeats
  replay).
- `apps-uthereal show / blame / feedback` → no LLM calls; cassettes
  unused.
- `apps-uthereal fix` → `replay` for the rerun-under-tape pass; if the
  target leaf's prompt was changed mid-step, that one leaf hits a miss
  and `fix` is responsible for handling it (see C9).
- `apps-uthereal verify` → `record-missing` (the rewritten leaf's
  cassette will record on miss; downstream leaves may also miss because
  upstream output changed).
- All test invocations → `replay`.

The cassette layout under `tests/fixtures/cassettes/` is checked in;
test agents do not record, only replay.

---

## C9 — Optimizer scoping

`apps-uthereal fix` (task 4-2) MUST mutate exactly one leaf. Implementation
sequence:

```python
runner.freeze_parameters("**")
target_leaf = runner.get_submodule(target_path)
runner.unfreeze_parameters(**{
    f"{target_path}.role":  True,
    f"{target_path}.task":  True,
    f"{target_path}.rules": True,
})

async with operad.optim.backprop.tape() as t:
    out = await runner(entry.to_input())

score, grad = await HumanFeedbackLoss().compute(out.response, feedback)
await t.backward(grad, parameters=list(target_leaf.parameters()))

opt = TextualGradientDescent(target_leaf.parameters(), lr=1.0)
await opt.step()
```

After the step, `apply_fix` MUST verify that no parameter outside
`target_path` changed:

```python
def _assert_only_target_changed(runner, target_path, before_state):
    after_state = runner.state()
    for path, before in before_state.items():
        if not path.startswith(target_path):
            assert after_state[path] == before, f"unexpected change at {path}"
```

`TRAINABLE_FIELDS = ("role", "task", "rules")`. `examples` is
**not** trainable in phase 1 — it keeps the change surface small and
the diff readable.

---

## C10 — Trace shape (frozen)

```python
class TraceFrame(BaseModel):
    step_name: str           # leaf path within the runner; matches runner.get_submodule(path)
    agent_class: str         # type(leaf).__name__
    leaf_role: str           # snapshot of leaf.role at invocation time
    leaf_task: str           # snapshot of leaf.task
    leaf_rules: list[str]    # snapshot of leaf.rules
    input: dict[str, Any]    # JSON-coerced input (BaseModel.model_dump(mode="json"))
    output: dict[str, Any]   # JSON-coerced output
    latency_ms: float
    hash_prompt: str         # from OperadOutput
    hash_input: str
    hash_output_schema: str
    run_id: str
    started_at: datetime
    finished_at: datetime
    parent_step: str | None  # for nested observer frames; root frames have None

    model_config = ConfigDict(frozen=True)


class WorkflowTrace(BaseModel):
    trace_id: str            # sha256 of frames; computed on .seal()
    entry_id: str
    frames: list[TraceFrame]
    final_answer_text: str   # mirrored from the last leaf for convenience
    intent_decision: Literal["DIRECT_ANSWER", "RAG_NEEDED", "SAFEGUARD_REJECTED"]
    sealed: bool = False     # frames must not be mutated after seal()

    def seal(self) -> "WorkflowTrace": ...
    def find_step(self, step_name: str) -> TraceFrame: ...
    def to_jsonl(self, path: Path) -> None: ...
    @classmethod
    def from_jsonl(cls, path: Path) -> "WorkflowTrace": ...
    def to_blamer_summary(self, max_field_chars: int = 600) -> str: ...
```

`step_name` MUST equal the dotted attribute path the runner uses, so the
Blamer's `target_path` directly maps to a leaf via
`runner.get_submodule(target_path)`. Examples:
`"context_safeguard"`, `"reasoner"`, `"conv_talker"`,
`"rag_pipeline.evidence_planner"`.

---

## C11 — CLI invariants

All CLI commands are subcommands of `apps-uthereal`. The list:

| Command | Purpose | Owner |
|---|---|---|
| `apps-uthereal run --entry PATH` | Execute one entry; record cassettes; emit `trace.jsonl`, `answer.txt`. | 4-1 |
| `apps-uthereal show --trace-id ID` | Pretty-print the trace. | 4-1 |
| `apps-uthereal feedback --trace-id ID` | Open `$EDITOR` on a `feedback.json` template. | 4-1 |
| `apps-uthereal blame --trace-id ID [--feedback PATH]` | Run the Blamer; emit `blame.json`. | 4-3 |
| `apps-uthereal fix --trace-id ID [--target PATH] [--dry-run]` | Apply the fix; print or write the YAML diff. | 4-2 |
| `apps-uthereal verify --trace-id ID` | Re-run the entry against rewritten YAMLs; print before/after diff. | 5-1 |

Skeleton scaffolding (parser plumbing for all subcommands, with
"not-yet-implemented" stubs) is owned by task 1-1. Each later task fills
in the body of its subcommands but never re-arranges the parser
structure.

Exit codes:

- `0` — success.
- `1` — domain failure (e.g. `CassetteMiss` in replay, `BlamerOutput.target_path == "control_flow"`).
- `2` — usage error.

Each command writes a JSON artifact under `.uthereal-runs/<entry_id>/`
(see C12). The artifact must be deterministic — two `apps-uthereal show`
calls on the same trace produce byte-identical output.

---

## C12 — Run directory layout (frozen)

```
.uthereal-runs/<entry_id>/
├── entry.json              # input (serialized DatasetEntry)
├── trace.jsonl             # one TraceFrame per line
├── answer.txt              # final answer text
├── feedback.json           # optional, written by `feedback`
├── blame.json              # optional, written by `blame`
├── fix.diff                # optional, written by `fix`
├── verify.json             # optional, written by `verify`
└── cassettes/
    ├── llm/
    └── rag/
```

`entry_id = sha256(canonical_json(entry))[:12]`.

The directory is the single shared state across CLI commands. No global
state, no environment-variable side channels (apart from `OPERAD_*`,
which operad itself reads).

---

## C13 — Style

(Recap from `AGENTS.md`, repeated here because PR review checks against
this list.)

- `from __future__ import annotations` at the top of every module.
- `T | None` instead of `Optional[T]`.
- Pydantic v2; `model_config = ConfigDict(frozen=True)` for value
  objects.
- No bare `except:`.
- Public functions and classes have docstrings.
- No emojis.
- Module-level loggers (`logger = logging.getLogger(__name__)`) — not
  class attributes, never `print` for diagnostics inside library code.
- No relative imports beyond a single dot
  (e.g. `from .schema import ...` is fine inside a package; reaching
  outside the package via `from ..` is not).

---

## C14 — Test discipline

- Each task ships its own tests under `apps/uthereal/tests/<module>/`.
- Tests run offline by default — no Gemini, no RAG container. Network
  access is forbidden in tests.
- Async tests use `pytest-asyncio` `auto` mode (matches `apps/studio/`).
- Fixture data lives under `apps/uthereal/tests/fixtures/`. Cassette
  fixtures under `apps/uthereal/tests/fixtures/cassettes/`. All checked
  in.
- Use `tmp_path`, `monkeypatch`, parametrize over edge cases (empty
  inputs, malformed YAML, schema drift, cassette miss).
- Negative tests are required where the contract has a "MUST raise"
  clause.

---

## C15 — Schema drift detection (advisory)

Task 1-2 ships a `make schemas-check` target that compares vendored
schemas against the live uthereal-src copies (when the uthereal venv is
on `PYTHONPATH`). The target prints a unified diff and exits 0 (warning
only) — drift is informational in phase 1.

---

## C16 — Anti-patterns (forbidden)

- Reimplementing YAML parsing. Use the loader.
- Reaching into operad internals (`operad.core._private`, `_observers`,
  etc.). Use the public API documented in `INVENTORY.md`.
- Adding new top-level dependencies without sign-off. Existing closure
  is operad + `pydantic` + `pyyaml` + `ruamel.yaml` + `httpx` (for
  retrieval) + the dev-group tools (`pytest`, `pytest-asyncio`,
  `respx`/`httpx-mock` for HTTP mocking).
- Network calls in module-level code (`__init__.py` HTTP calls).
  Initialize lazily.
- Logging at `INFO` for hot paths. Hot-path logs are `DEBUG`.
- Catching `BuildError`, `ValidationError`, or `CancelledError` and
  turning them into something else.
- Writing to `apps/uthereal/` paths during tests; use `tmp_path`.
- Adding mutable default arguments.

---

## C17 — Amendment process

If you need to amend this document:

1. Stop coding.
2. In your task's `## Notes` section, write:
   ```
   ## Proposed contract amendment
   - **Section:** C5 (YAML I/O is loader-mediated)
   - **Change:** Allow `prompt.examples` to be partially-typed dicts...
   - **Rationale:** ...
   - **Alternatives considered:** ...
   ```
3. Wait for the reviewer's sign-off before implementing.

Do not silently change the contract. The whole point of this document
is that every parallel agent can rely on it.
