# 2 · 2 — Freeze/thaw built graphs + graph-aware BuildError

**Addresses.** B1 (`Agent.freeze` / `Agent.thaw`), B2 (Mermaid-fragment
appended to `BuildError`).

**Depends on.** 1-1-restructure (for the `operad.utils.hashing` /
`operad.core.models` surfaces this PR may import from).

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §5 (AgentGraph as first-class artefact).
- `operad/core/build.py` — `Tracer`, `Node`, `Edge`, `AgentGraph`, the
  `build_agent` / `abuild_agent` entry points.
- `operad/core/graph.py` — `to_json`, `from_json`, `to_mermaid`.
- `operad/core/state.py` — `AgentState`, used for freeze payload.
- `operad/utils/errors.py` — `BuildError`, `BuildReason` literal.

---

## Proposal

### B1 · `Agent.freeze` / `Agent.thaw`

**Problem.** `build()` symbolically traces the tree every time a process
starts. For CLI tools, AWS Lambdas, and test fixtures, that cold start
(and the accompanying strands init) dominates latency. Freeze/thaw
persists the built graph to disk and reconstitutes without re-tracing.

**API.**

```python
# operad/core/agent.py (signatures only; implementation lives in 2-2's
# `operad/core/freeze.py` helper module)

def freeze(self, path: str | Path) -> None:
    """Persist a built agent to `path` (JSON).

    Serialises:
      - `AgentGraph` (via `core.graph.to_json`)
      - `AgentState` tree (via `self.state()`)
      - Per-leaf rendered system messages (cache for fast reload)
      - A version header: operad_version_hash + python_version_hash

    Raises `BuildError("not_built", ...)` if `self._built` is False.
    Strips `config.api_key` before serialising (never persist secrets).
    """

@classmethod
def thaw(cls, path: str | Path) -> Self:
    """Reconstitute a built agent from `path`.

    Skips symbolic tracing: the `AgentGraph` is loaded directly.
    Strands internals are re-wired from `AgentState` (the same mechanism
    `build()` uses after tracing, so re-use `_init_strands`).
    Raises if the stored `operad_version_hash` does not match the
    current version — cross-version thaw is not supported for v1.
    """
```

Storage format (JSON, pretty-printed, deterministic):

```json
{
  "operad_version_hash": "...",
  "python_version_hash": "...",
  "agent_class": "fully.qualified.Reasoner",
  "state": { ...AgentState dump... },
  "graph": { ...AgentGraph.to_json()... },
  "prompts": {
    "Root.reasoner": "<rendered system message>",
    "Root.critic":   "<rendered system message>"
  }
}
```

Prefer one file; do **not** split across multiple paths.

Implementation split:
- Add a small module `operad/core/freeze.py` with
  `freeze_agent(agent, path)` and `thaw_agent(path)`. Keep the logic
  out of `agent.py`.
- `Agent.freeze` / `Agent.thaw` are thin one-line delegations to those
  functions, mirroring how `build` / `abuild` delegate.

### B2 · Mermaid-augmented `BuildError.__str__`

**Problem.** Current `BuildError` messages say things like
`input_mismatch: expected Question, got Utterance at 'Pipeline.stage_1
 → stage_2'`. Useful but requires the reader to mentally render the
graph.

**Change.** Extend `BuildError.__str__` to append a small Mermaid
fragment highlighting the failing edge for the error reasons that
carry a graph context (`input_mismatch`, `output_mismatch`,
`payload_branch`, `router_miss`). The fragment is a valid Mermaid
`flowchart` that users can paste into any Mermaid renderer or a GitHub
comment.

Shape:

```
BuildError(input_mismatch): at Pipeline.stage_1 → stage_2
    expected Question, got Utterance

--- mermaid ---
flowchart LR
    stage_1[Reasoner: Utterance → Answer] -->|❌| stage_2[Critic: Question → Score]
```

The Mermaid footer is optional — only emit it when the error carries a
path hint. `BuildReason.not_built`, `prompt_incomplete`, and
`trace_failed` get no Mermaid (nothing graph-local to point at).

Keep the existing human-readable first-line format untouched so
existing regex-based log parsers keep working. The Mermaid fragment is
separated by a `--- mermaid ---` marker line and rendered after a
blank line.

---

## Required tests

`tests/test_build_freeze.py` (new):

1. **Freeze round trip.** Build a `Pipeline` of two `FakeLeaf` agents,
   `.freeze(tmp_path / "agent.json")`, load in a subprocess via a tiny
   throwaway script, `.invoke()` — assert the same typed response.
2. **API-key redaction.** Agent with `config.api_key="secret-123"`.
   Freeze; read the JSON as raw text; assert no `"secret-123"` substring.
3. **Version guard.** Freeze; poke the `operad_version_hash` to a fake
   value; thaw must raise `BuildError("not_built", ...)` with a message
   mentioning version mismatch.

`tests/test_build_error_mermaid.py` (new):

4. **input_mismatch mermaid.** Construct a `Pipeline` whose stage types
   don't line up; call `.build()`; `str(exc_info.value)` contains
   `--- mermaid ---` and a `flowchart` line.
5. **not_built no mermaid.** `.invoke()` on an unbuilt agent raises;
   the string does **not** contain `--- mermaid ---`.

All tests offline.

---

## Scope

**New files.**
- `operad/core/freeze.py` (freeze/thaw implementation).
- `tests/test_build_freeze.py`.
- `tests/test_build_error_mermaid.py`.

**Edited files.**
- `operad/core/agent.py` — add two tiny delegate methods `freeze`,
  `thaw` (this is the only change to agent.py; do NOT add anything
  else here — that's 2-1's file-ownership).

  > **Shared file coordination with 2-1.** Agent.py ownership in Wave 2
  > belongs to 2-1. This PR adds exactly two thin delegate methods
  > (`freeze`, classmethod `thaw`); nothing else. If 2-1 lands first,
  > apply the two methods cleanly. If this PR lands first, 2-1 must
  > absorb the delegates. Coordinate via the conductor task list if
  > conflict looms.
- `operad/core/__init__.py` — re-export `freeze_agent`, `thaw_agent` if
  the user wants function-form access.
- `operad/utils/errors.py` — extend `BuildError.__str__` with the
  mermaid footer path.
- `operad/core/graph.py` — if a tiny helper is needed to render a
  single-edge mermaid fragment, add it here (prefer re-using
  `to_mermaid`).

**Must NOT touch.**
- Anything in `operad/runtime/`, `operad/agents/`, `operad/algorithms/`,
  `operad/utils/` outside `errors.py`.

---

## Acceptance

- `uv run pytest tests/` green.
- `Agent.freeze(path)` + fresh-interpreter `Agent.thaw(path)` →
  `invoke` works offline.
- `BuildError` raised by a type-mismatched Pipeline prints a valid
  Mermaid fragment between `--- mermaid ---` and the end of the string.
- No API keys in frozen files.

---

## Watch-outs

- **Default-forward leaves + strands internals.** `build()` wires
  `strands.Agent` internals inside `_init_strands`. `thaw` must re-run
  that wiring (without re-running the symbolic tracer). Factor
  `_init_strands` so it can accept a cached `AgentState` + prerendered
  system message.
- **Composite routing state.** `Pipeline._stages`, `Parallel._keys`,
  `Parallel._combine` are not part of `AgentState` today; they're
  reconstructed from the composite's `__init__`. Freeze must either
  serialise them alongside `state()` or reconstruct via the class'
  deterministic construction order. Keep to one approach and document.
- **Version compatibility.** v1 is strict: reject any thaw where
  `operad_version_hash` doesn't match. This is intentional — a
  cross-version compatibility story belongs in a later brief, not this
  one.
- **Mermaid escaping.** Class names with `<`, `>` (e.g. generic types)
  need to be escaped for Mermaid labels. Use `" "` wrapping. Keep the
  fragment small: two nodes + one edge is enough for v1.
- **BuildReason literal.** Do not add new reasons in this PR; 2-3 adds
  `schema_drift`, and those two PRs may race on `utils/errors.py`.
  Change only the `__str__` method here; leave the `BuildReason` tuple
  alone.
