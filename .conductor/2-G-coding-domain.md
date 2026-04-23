# Phase 2 · Stream G — Coding domain

**Goal.** Ship `operad/agents/coding/` with leaves and one composed
pattern (`PRReviewer`). Mirror the shape of `operad/agents/reasoning/`.

**Owner.** One agent.
**Depends on.** Stream E (`Retriever` is useful for context retrieval;
`ToolUser` pairs naturally with running linters).
**Addresses:** C-4 (coding sub-domain).

---

## Scope

### Files you will create
- `operad/agents/coding/__init__.py`
- `operad/agents/coding/components/__init__.py`
- `operad/agents/coding/components/code_reviewer.py`
- `operad/agents/coding/components/context_optimizer.py`
- `operad/agents/coding/components/diff_summarizer.py`
- `operad/agents/coding/pr_reviewer.py` — Pipeline composition.
- `tests/test_coding_components.py`, `test_pr_reviewer.py`.
- `examples/pr_reviewer.py`.

### Files you will edit
- `operad/agents/__init__.py` — re-export from `coding`.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- `operad/agents/reasoning/`. Mirror its shape; don't modify it.
- Core, runtime, metrics.

---

## Design direction

### Typed building blocks

```python
class DiffChunk(BaseModel):
    path: str
    old: str
    new: str
    context: str = Field(default="", description="Surrounding code.")

class ReviewComment(BaseModel):
    path: str
    line: int
    severity: Literal["info", "warning", "error"]
    comment: str

class ReviewReport(BaseModel):
    comments: list[ReviewComment] = Field(default_factory=list)
    summary: str = ""
```

Pydantic v2 accepts `list[ReviewComment]` directly on a field; you
don't need a `RootModel` wrapper unless you want one.

### `CodeReviewer`

```python
class CodeReviewer(Agent[DiffChunk, ReviewReport]):
    input = DiffChunk
    output = ReviewReport
    role = "You are a meticulous senior code reviewer."
    task = "Identify bugs, style issues, and missing tests in the diff."
    rules = (
        "Only comment when the issue is real; do not nitpick style if the codebase doesn't enforce it.",
        "Cite the line number for every comment.",
        "Classify severity as info, warning, or error.",
    )
```

### `ContextOptimizer`

Accepts a `DiffChunk` with empty context and a reference to an async
`read_file` callable; returns a `DiffChunk` with `context` populated
by the minimal surrounding code. Override `forward`; no config needed.

### `DiffSummarizer`

```python
class PRDiff(BaseModel):
    chunks: list[DiffChunk]

class PRSummary(BaseModel):
    headline: str
    changes: list[str]

class DiffSummarizer(Agent[PRDiff, PRSummary]):
    role = "You summarize pull request diffs at a glance."
    task = "Produce a one-line headline and a bulleted change list."
    rules = ("Keep the headline under 70 characters.",
             "One bullet per logical change, not per file.")
```

### `PRReviewer`

```python
class PRReviewer(Pipeline):   # or: Pipeline wrapper
    def __init__(self, *, config: Configuration, read_file):
        super().__init__(
            ContextOptimizer(read_file=read_file),
            DiffSummarizer(config=config),
            CodeReviewer(config=config),
            input=PRDiff, output=ReviewReport,
        )
```

This only type-checks if the types line up end-to-end. Likely you'll
need to add small adapters or make each component's input/output
match. If the sequence doesn't quite fit, model it as a custom
composite with an explicit `forward` that routes deterministically.

---

## Tests

- Each leaf builds under `FakeLeaf`-style stubs.
- `PRReviewer.build()` produces a 3-node graph.
- Mermaid export for `PRReviewer` contains the three stage paths.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/pr_reviewer.py` runs a synthetic PR review against a local
  model (guarded like `examples/parallel.py` — check env var before
  executing).

---

## Watch-outs

- Don't implement actual git-diff parsing. Accept structured input.
- The `severity` enum stays small. Don't proliferate levels.
- Ship at least one `Example(...)` per leaf (see `Stream K` for why).
