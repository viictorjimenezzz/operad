# Feature · Agent introspection (`.operad()`, `.diff()`, `_repr_html_`)

Three small, related surface additions that together make the
library's internals visible at a glance. All live on `Agent` and
`AgentGraph`; they share imports, tests, and touch the same class, so
a single agent should own all three.

**Covers Part-3 items.** #1 (renamed to `.operad()`), #2 (`.diff()` as
instance method), #13 (inline graph in notebooks / IDE).

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §6–§7, and these phase briefs:
- `.conductor/1-B-agent-state.md` — `.diff()` consumes `AgentState`.
- `.conductor/2-C-observers.md` — ensure introspection doesn't emit
  observer events.

---

## Proposal sketch

### 1. `Agent.operad()` — render every leaf's prompt

Replaces the "prompt dry-run mode" idea. Walks the tree and prints
every default-forward leaf's rendered system + schema + example
bundle, labelled by qualified path. Zero tokens generated.

```python
def operad(self, *, file: TextIO = sys.stdout) -> None:
    """Print every leaf's rendered prompt and schema.

    Useful as a sanity check before .abuild() and before any token is
    spent. Walks the agent tree; skips composites (which have no
    prompt of their own).
    """
```

A machine-readable variant `operad_dump() -> dict[path, str]` is a
useful sibling — add it if it costs you nothing.

### 2. `Agent.diff(other)` — compare two agents

Instance method; `self` is the reference ("before"), `other` is the
candidate ("after"). Returns an `AgentDiff` object with a
human-readable `__str__` and a structured `.changes` list.

```python
def diff(self, other: "Agent[Any, Any]") -> AgentDiff:
    """Compare another agent to this one (self is the reference).

    Powers Evolutionary's change-log, PR reviews of prompt changes,
    and the "what did the mutation actually do?" question.
    """
```

The diff should cover (per leaf path):
- `role` / `task` / `rules` string-level diff (use `difflib`).
- `examples` list-level diff (added / removed).
- `config` field-level diff (temperature, model, etc.).
- Tree-structural diff (child added / removed / renamed).

### 3. `AgentGraph._repr_html_` + `Agent._repr_html_`

Jupyter calls `_repr_html_()` when it exists. Return HTML that embeds
the Mermaid diagram. Keep it simple — a `<pre class="mermaid">` block
that works with any Mermaid-rendering Jupyter extension, or a
self-contained `<div>` that loads the Mermaid CDN script.

```python
def _repr_html_(self) -> str:
    """Inline Mermaid rendering for notebooks and IDEs."""
```

Put it on `AgentGraph` primarily. `Agent._repr_html_` delegates to
`self._graph._repr_html_()` if built, otherwise returns a plaintext
summary.

---

## Research directions

- **Pydantic v2 deep-diff.** Is `model_dump(mode="python")` + a naive
  walk enough, or is there a cleaner idiom? Investigate
  `deepdiff` — likely too heavy a dep; implement a small recursive
  differ.
- **Mermaid in Jupyter.** Classic Jupyter renders raw Mermaid only
  with an extension. VS Code's Jupyter kernel, JupyterLab, and
  marimo all differ. The safe lowest-common-denominator is an
  `<img>` tag pointing at `https://mermaid.ink/img/...` — investigate
  whether that's acceptable (it makes an outbound request, which may
  be undesirable in offline environments). Fallback: raw
  `<pre class="mermaid">`.
- **`__repr__` vs `_repr_html_`.** Keep `__repr__` text-only
  (Stream B's brief adds a `__repr__`). HTML rendering is purely for
  rich displays.

---

## Integration & compatibility requirements

- **Read Stream B's `.conductor/1-B-agent-state.md`.** `.diff()`
  consumes `AgentState`; do not re-invent state capture.
- **Do not change `invoke` / `__call__` return types** in this
  feature. That is Feature `feature-operad-output.md`'s business.
- **No observer events during introspection.** Guard with the same
  contextvar pattern Stream C uses; simpler: these methods are sync
  and don't call `invoke`.
- **No new heavy dependencies.** `difflib` is stdlib; that's the bar.
  If you reach for `deepdiff` or `rich` for the diff rendering, put
  them behind an optional import.
- **File touchpoints.** `operad/core/agent.py` (three methods),
  `operad/core/graph.py` (`_repr_html_`), `operad/core/diff.py` (new
  — `AgentDiff` dataclass + rendering helpers). Everything else is
  tests.

---

## Acceptance

- `uv run pytest tests/` green.
- `agent.operad()` on a built ReAct prints four labelled prompts.
- `agent.diff(other)` returns a non-empty `AgentDiff` when any leaf
  differs; empty when agents are equivalent.
- In a Jupyter notebook, evaluating a built agent renders the
  Mermaid graph inline (document the required extension in
  `CLAUDE.md` if any).

---

## Watch-outs

- Keep the printed output stable across Python versions — users will
  snapshot-test it.
- `.diff()` must not mutate either agent.
- Mermaid rendering should degrade to plain text in non-HTML
  environments; detect via the caller's repr protocol (or always
  define both `__repr__` and `_repr_html_`, letting Jupyter pick).
- Don't name the free function `diff()` — it's a method on the
  reference agent.
