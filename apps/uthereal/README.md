# apps-uthereal

`apps-uthereal` is an operad-native bridge for uthereal's `selfserve` chat
workflow. It loads each leaf prompt from the YAML files shipped with
`uthereal-src` (no `uthereal_*` imports), composes them into an
`ArtemisRunner`, and exposes a cassette-deterministic prompt-fixing loop:

```text
run -> show -> feedback -> blame -> fix -> verify
```

LLM and retrieval calls are recorded to per-run cassettes so that the rest
of the loop is byte-stable across re-runs. Targeted backward propagation
turns a human critique of one final answer into a one-leaf prompt rewrite,
which is then dumped back to the source YAML and re-evaluated under the
recorded cassettes.

## Architecture

The full task graph and contracts live in
[`.conductor/uthereal/`](../../.conductor/uthereal/) (start with
[`AGENTS.md`](../../.conductor/uthereal/AGENTS.md) and
[`00-contracts.md`](../../.conductor/uthereal/00-contracts.md)).

High-level layout:

```
apps/uthereal/apps_uthereal/
  cli.py                # argparse dispatcher
  commands/             # run, show, feedback, blame, fix, verify
  leaves/               # 9 YAML-loaded leaf agents + the loader
  workflow/runner.py    # ArtemisRunner, run_with_trace, WorkflowTrace observer
  workflow/trace.py     # WorkflowTrace + TraceFrame Pydantic models
  schemas/              # vendored DatasetEntry / ArtemisInput / ArtemisFinalAnswer / Retrieval*
  retrieval/client.py   # RetrievalClient protocol + RetrievalError
  feedback/             # Blamer, HumanFeedbackLoss, HumanFeedback schema
  train/apply_fix.py    # tape().backward() + TextualGradientDescent driver
  tiers.py              # llm_tier -> operad Configuration
  paths.py              # .uthereal-runs/ layout
  errors.py             # LoaderError / RetrievalError / TraceError
```

## Quick start

```bash
# 1. Install dependencies (top-level repo).
uv sync

# 2. Make sure the bridge can find the selfserve YAMLs.
export UTHEREAL_SELFSERVE_ROOT=$HOME/Documents/uthereal/uthereal-src/uthereal_workflow/agentic_workflows/chat/selfserve

# 3. Make sure operad can authenticate to Gemini. Either set:
#    GOOGLE_API_KEY=<key>
#    or
#    GOOGLE_VERTEX_AI_SERVICE_ACCOUNT='{"type":"service_account",...}'

# 4. Run the demo end-to-end.
make -C apps/uthereal demo
```

The demo uses the DIRECT_ANSWER fixture under
`fixtures/entries/demo_entry.json` and targets the `conv_talker` leaf, which
keeps the loop hermetic from the live RAG service.

## CLI reference

| Command | Purpose |
|---|---|
| `apps-uthereal run --entry path/to/entry.json [--cassette-mode {record,replay,record-missing}] [--rag-base-url URL] [--selfserve-root PATH]` | Execute one `DatasetEntry` end-to-end and record cassettes. |
| `apps-uthereal show --trace-id ID` | Pretty-print the stored trace and final answer for a run. |
| `apps-uthereal feedback --trace-id ID [--no-editor]` | Open `$EDITOR` on a structured `feedback.json` template. With `--no-editor`, just create the template (or validate an already-edited one). |
| `apps-uthereal blame --trace-id ID [--target STEP] [--no-confirm] [--feedback PATH]` | Localize blame to one leaf step. With `--target`, bypass the LLM blamer; otherwise, the Blamer agent decides. |
| `apps-uthereal fix --trace-id ID [--dry-run] [--target STEP] [--lr 1.0]` | Run targeted backward propagation, rewrite the leaf's `role`/`task`/`rules`, and (unless `--dry-run`) write back to YAML. |
| `apps-uthereal verify --trace-id ID [--rag-base-url URL] [--selfserve-root PATH]` | Re-run the same entry against the patched YAMLs and write `verify.json` with a before/after diff. |

## Run-directory layout

Per [`00-contracts.md` C12](../../.conductor/uthereal/00-contracts.md):

```
.uthereal-runs/<entry_id>/
    entry.json
    trace.jsonl              # 1 header line, then 1 frame per leaf invocation
    answer.txt
    cassettes/
        llm/calls.jsonl
        rag/<retrieval-key>.json
        rag/metadata-<workspace>.json
    feedback.json            # written by `apps-uthereal feedback`
    blame.json               # written by `apps-uthereal blame`
    fix.diff                 # unified diff of trainable fields
    fix.json                 # FixReport (excluding before/after states)
    verify.json              # before/after diff of the patched run
```

## Adding a new entry

1. Author a `DatasetEntry` JSON. Use `fixtures/entries/demo_entry.json` as
   a starting template. Optional fields like `chat_history` /
   `session_memory_context` / `prior_beliefs_context` may be empty
   strings; `context` and `workspace_guide` should be descriptive.
2. `apps-uthereal run --entry path/to/entry.json --cassette-mode record-missing`
   records the cassettes under `.uthereal-runs/<entry_id>/`.
3. `apps-uthereal show --trace-id <id>` to sanity-check.
4. `apps-uthereal feedback --trace-id <id>` to write the critique.
5. `apps-uthereal blame --trace-id <id>` (or `--target <step>` to override).
6. `apps-uthereal fix --trace-id <id> --dry-run` to preview the rewrite.
7. `apps-uthereal fix --trace-id <id>` to apply the rewrite to YAML.
8. `apps-uthereal verify --trace-id <id>` to rerun and diff.

## Tests

Unit tests cover every leaf, the loader, the runner, the CLI commands, and
the apply-fix machinery:

```bash
uv run pytest apps/uthereal/tests/
```

Integration tests gated by `OPERAD_INTEGRATION` (live Gemini, live RAG
service) live under `tests/integration/`.

## Schema drift

`make -C apps/uthereal schemas-check` re-runs the vendored Pydantic
schemas against `uthereal-src` and exits non-zero on drift.

## Out of scope (phase 1)

Per [`AGENTS.md` §9](../../.conductor/uthereal/AGENTS.md):

- A live HTTP RAG service. The bridge speaks to whatever is on
  `--rag-base-url`; selfserve_v3 backends like MongoDB are not
  reimplemented.
- Streaming. All leaves are single-shot.
- Multi-leaf simultaneous fixes. One blame -> one leaf -> one fix.
- Optimizer state across runs. Each `fix` is independent.
- Promoting fixes to a PR. The bridge writes the YAML in place.
