# `apps/uthereal/` — implementation orchestration

This folder is the implementation plan for `apps/uthereal/`, a new editable
install in the operad monorepo that bridges operad's training machinery to
uthereal's `selfserve` chat workflow. You are one of several agents
implementing this plan; your specific task is described by the
`<sequence>-<parallel>-<name>.md` file you were assigned.

Read this document and `00-contracts.md` in full before opening any code.
You have a focused, bounded task — but you are capable, and you are
expected to push back on anything in your brief that's wrong.

---

## 1. The goal

A single end-to-end loop:

> dataset entry → operad-native re-implementation of `ArtemisWorkflow` →
> typed `WorkflowTrace` → human (the user's) feedback → blame the
> responsible component → backpropagated targeted textual gradient →
> rewrite the responsible leaf's prompt → write back to YAML → re-run to
> verify.

The whole loop runs deterministically under operad cassettes — record once
per dataset entry, replay forever. Every part of the loop except the
human is deterministic.

There is **no component-wise benchmarking**, **no LLMAAJ judge layer**,
**no multi-target gradients** in this phase. One workflow, one trace, one
human, one fix. Resist scope creep.

---

## 2. Architecture summary

```
.uthereal-runs/<entry_id>/                       (per-entry artifacts)
   trace.jsonl, answer.txt, feedback.json,
   blame.json, fix.diff, verify.json,
   cassettes/{llm,rag}/

apps/uthereal/                                   (the new package)
├── apps_uthereal/
│   ├── tiers.py                                 [batch 1]
│   ├── schemas/                                 [batch 1]   vendored Pydantic
│   ├── leaves/                                  [batch 1+2] YAML-loaded operad agents
│   ├── retrieval/                               [batch 1]   RetrievalClient + cassette
│   ├── workflow/                                [batch 1+2+3] trace, state, runner
│   ├── feedback/                                [batch 1+2] schema, Blamer, loss
│   ├── train/                                   [batch 4]   apply_fix
│   └── cli.py                                   [batch 1+4+5]
├── tests/
└── pyproject.toml
```

The runner is operad-native composition. It does not import
`uthereal_src`, `uthereal_workflow`, `uthereal_core`, or any uthereal
package. The vendored YAMLs are the source of truth for prompts; the
vendored Pydantic schemas are the source of truth for typed boundaries.

The seven leaves wired up in phase 1 (everything else is deferred):

| Leaf class | YAML | Purpose |
|---|---|---|
| `ContextSafeguardLeaf` | `input/agents/agent_context_safeguard.yaml` | Block / exit / pass. |
| `SafeguardTalkerLeaf` | `input/agents/agent_safeguard_talker.yaml` | Refusal text. |
| `ReasonerLeaf` | `reasoner/agents/agent_reasoner.yaml` | Route + rewrite + downstream. |
| `ConversationalTalkerLeaf` | `reasoner/agents/agent_conversational_talker.yaml` | Direct-answer text. |
| `RuleClassifierLeaf` | `retrieval/agents/agent_rule_classifier.yaml` | Pick rules. |
| `RetrievalOrchestratorLeaf` | `retrieval/agents/agent_retrieval_orchestrator.yaml` | Generate retrieval specs. |
| `EvidencePlannerLeaf` | `retrieval/agents/agent_evidence_planner.yaml` | Plan evidence. |
| `FactFilterLeaf` | `retrieval/agents/agent_fact_filter.yaml` | Filter hits. |
| `RAGTalkerLeaf` | `retrieval/agents/agent_talker.yaml` | Final RAG answer. |

(Yes that's nine. The "seven" in earlier conversations included the two
optional title leaves; in phase 1 we ship nine YAML-loaded leaves plus the
custom Blamer.)

---

## 3. Dependency graph

```
batch 1 (parallel, 5 tasks)         no inter-deps
   1-1  skeleton  ───────────────┐
   1-2  vendored-schemas ────────┤
   1-3  yaml-loader ─────────────┤
   1-4  retrieval-client ────────┤
   1-5  trace-feedback-models ───┤
                                 │
batch 2 (parallel, 4 tasks)      │  needs all of batch 1
   2-1  operad-leaves ───────────┼─< 1-2, 1-3
   2-2  run-state ───────────────┼─< 1-2
   2-3  blamer ──────────────────┼─< 1-2, 1-5
   2-4  feedback-loss ───────────┼─< 1-5
                                 │
batch 3 (sequential, 1 task)     │  needs all of batch 2
   3-1  runner ──────────────────┼─< 2-1, 2-2, 1-4, 1-5
                                 │
batch 4 (parallel, 3 tasks)      │  needs runner
   4-1  cli-run-show-feedback ───┼─< 3-1, 1-5
   4-2  apply-fix ───────────────┼─< 3-1, 2-3, 2-4
   4-3  cli-blame ───────────────┼─< 3-1, 2-3
                                 │
batch 5 (sequential, 1 task)     │  needs everything
   5-1  verify-and-demo ─────────┘
```

---

## 4. Required reading before you start

In strict order:

1. **This file** (`AGENTS.md`).
2. **`.conductor/uthereal/00-contracts.md`** — invariants every task respects.
3. **Your `<sequence>-<parallel>-<name>.md`** task file.
4. **`/Users/viictorjimenezzz/Documents/operad/AGENTS.md`** — workspace
   rules. The "Surgical Changes" rule is binding: every changed line must
   trace directly to your brief.
5. **`/Users/viictorjimenezzz/Documents/operad/INVENTORY.md`** — operad's
   capability catalog. Sections you'll cite: §1 (Agent), §6
   (component library), §10 (Configuration), §13 (observers), §17
   (cassettes), §21 (Parameters / training).
6. **The relevant uthereal YAMLs** under
   `/Users/viictorjimenezzz/Documents/uthereal/uthereal-src/uthereal_workflow/agentic_workflows/chat/selfserve/`.
   Particularly the `AGENTS.md` and `specs.md` there — they explain the
   workflow's structure and quality bar.
7. **Operad reference patterns** — the closest analogues to what you're
   building:
   - `apps/demos/triage_reply/` — a self-contained operad app with
     leaves, a tree, a metric, a dataset, and a `run.py` driver.
   - `apps/studio/` — a sibling editable install that consumes operad
     and hosts a CLI + small server.
   - `operad/agents/safeguard/components/context.py` — leaf with
     `cleandoc` rules + structured examples.
   - `operad/agents/memory/components/beliefs.py` — leaf with rich
     output and contradiction logic.

You should not need to read sibling task files. If you find yourself
reaching for a sibling task file, that's a contract gap — surface it.

---

## 5. Conventions

**Style.**
- Python 3.12+, Pydantic v2.
- `from __future__ import annotations` at the top of every module.
- Type hints everywhere; `T | None` instead of `Optional[T]`.
- No bare `except:`.
- Public functions and classes have docstrings.
- No emojis.
- Match operad's style. Use `cleandoc` for multiline prompt strings on
  Agent class bodies; use `model_config = ConfigDict(frozen=True)` for
  value-object Pydantic models.

**Imports.**
- Forbidden: `uthereal_src.*`, `uthereal_workflow.*`, `uthereal_core.*`,
  `uthereal_apps.*`, `uthereal_infra.*`. The bridge is standalone.
- Inside `apps_uthereal/`, prefer absolute imports
  (`from apps_uthereal.schemas.retrieval import ...`).
- Reuse operad primitives. Don't reimplement `Sequential`, `Parallel`,
  `Router`, `Agent`, `Configuration`, `tape()`, `backward()`,
  `TextualGradient`, `RewriteAgent`, `Optimizer`, `freeze_parameters`.

**Async.**
- Anything that touches an `Agent`, an HTTP client, or a cassette is
  `async def`.
- Use `asyncio.gather` for parallel calls; never `asyncio.wait` unless
  you need its specific semantics.

**Errors.**
- Loader errors: `apps_uthereal.errors.LoaderError(yaml_path, reason)`.
- Cassette misses in replay: re-raise operad's `CassetteMiss`.
- RAG errors: `apps_uthereal.errors.RetrievalError(spec, status, body)`.
- Never swallow `BuildError`, `ValidationError`, or `CancelledError`.

---

## 6. Testing conventions

- `pytest` + `pytest-asyncio` (auto mode, mirroring `apps/studio/`).
- Tests live under `apps/uthereal/tests/<module>/test_*.py`.
- Tests run offline by default — no Gemini, no RAG container.
- Every task ships its own tests. No "tests come later" deferrals.
- Use `tmp_path`, `monkeypatch`, parametrize over edge cases.
- For mocked-out collaborators, prefer small in-test classes over
  `unittest.mock`. Match operad's `FakeLeaf` / `FakeRetriever` patterns.

To run your slice:

```bash
uv run pytest apps/uthereal/tests/<your-module>/ -v
```

To smoke-import:

```bash
uv run python -c "from apps_uthereal import <your-module>; print('ok')"
```

To lint (when `ruff` is configured for `apps/uthereal/`):

```bash
uv run ruff check apps/uthereal/
```

---

## 7. How to know your task is done

A task is done when **all** of these hold:

1. Every file in your task's "Files to create" exists at the documented
   path with the documented public API.
2. Every item in your task's "Acceptance criteria" is satisfied.
3. Every test in "Tests" passes; you ship them with your code.
4. No imports from forbidden packages (per §5).
5. No file outside your task's owned set has been modified, except for
   the root `pyproject.toml`'s workspace declaration if your task
   explicitly says so.
6. `uv run pytest apps/uthereal/tests/` runs from a clean checkout (so
   your tests must not depend on a sibling task's runtime artifacts).
7. The `## Notes` section at the bottom of your task file is filled in
   with anything you discovered that wasn't in the brief.

The reviewer (the user) will run a smoke check against the task's
acceptance criteria. Tasks that fail the smoke check get bounced.

---

## 8. Smart-agent guidance

You are capable. Use that capability to:

- **Push back** on anything in your brief that contradicts operad's
  patterns or this folder's contracts. Surface the disagreement in your
  `## Notes` section before silently changing scope.
- **Add tests** beyond the explicit list when the surface deserves them
  — particularly negative tests (cassette miss, malformed YAML, schema
  drift).
- **Refuse to over-engineer.** The workspace `AGENTS.md` rule is binding:
  *"if you write 200 lines and it could be 50, rewrite it."* If your
  brief feels like it's asking for a configurable subsystem when a
  function would do, ask before building.
- **Document** what isn't obvious. The next agent (or the reviewer) will
  read your code; one paragraph in the module docstring is cheaper than
  five minutes of confusion.

When in doubt, default to operad's existing patterns. The dashboard
(`apps/dashboard/`), studio (`apps/studio/`), and demos
(`apps/demos/triage_reply/`) are your style references.

---

## 9. Out of scope (every task)

Phase 1 explicitly does **not** include:

- Streaming, image attachments, VLM, conversation/interaction title
  generation, citation gist, memory persistence (`MemoryManager*`,
  `BeliefsExtractor*`, `SessionMemoryUpdater*`).
- Component-wise benchmarking — only the end-to-end loop.
- Multi-target gradients — one fix per cycle.
- LLMAAJ judges and rubric-based scoring — the human is the loss.
- A web UI — CLI only. The Studio app is reference, not target.
- Re-recording a cassette mid-loop. Cassettes are recorded per dataset
  entry by `apps-uthereal run` and consumed everywhere else.

If your brief asks you to do any of these, the brief is wrong. Stop and
ask.

---

## 10. Communication

Each task file ends with a `## Notes` section. Append your discoveries
there as you implement; the reviewer reads them. If you need to amend
`00-contracts.md`, propose the amendment in your task notes — don't edit
the contracts directly.
