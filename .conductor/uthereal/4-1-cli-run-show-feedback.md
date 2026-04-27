# 4-1 — CLI: `run`, `show`, `feedback`

**Batch:** 4 · **Parallelizable with:** 4-2, 4-3 · **Depends on:** 1-5, 3-1

You are the user's first interface. The three commands here are the
data-collection half of the loop: run an entry, show its trace, capture
human feedback.

## Goal

Implement three CLI subcommands. Each has its own module under
`apps_uthereal/commands/`. The dispatcher (in `cli.py`, owned by 1-1)
already has the parser plumbing; you fill in the bodies.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/commands/run.py` | `run` — execute one entry, record cassettes, write trace + answer |
| `apps_uthereal/commands/show.py` | `show` — pretty-print the trace |
| `apps_uthereal/commands/feedback.py` | `feedback` — open `$EDITOR` on a JSON template |
| `apps_uthereal/tests/test_cmd_run.py` | tests |
| `apps_uthereal/tests/test_cmd_show.py` | tests |
| `apps_uthereal/tests/test_cmd_feedback.py` | tests |

## API surface

Every command module exports:

```python
def add_parser(subparsers) -> None: ...
async def run(args) -> int: ...
```

### `commands/run.py`

```bash
apps-uthereal run --entry PATH [--selfserve-root PATH]
                  [--rag-base-url URL] [--cassette-mode MODE]
```

Flags:

- `--entry PATH` (required) — path to a JSON file deserializable as
  `DatasetEntry`. The entry's `entry_id` is computed (or read from
  the file).
- `--selfserve-root PATH` — defaults to
  `$UTHEREAL_SELFSERVE_ROOT` env var, then to a sane fallback. Required
  to be set somehow.
- `--rag-base-url URL` — defaults to `$UTHEREAL_RAG_URL`.
- `--cassette-mode {record,replay,record-missing}` — default
  `record-missing`.

Behavior:

1. Resolve `entry_id`; create `.uthereal-runs/<entry_id>/`.
2. Save the entry as `entry.json` (idempotent).
3. Construct `LiveRetrievalClient(rag_base_url)` if URL set, else None.
   Wrap in `CassetteRetrievalClient(cassette_dir=run_dir/'cassettes/rag',
   inner=live, mode=cassette_mode)`.
4. Set `OPERAD_CASSETTE` env var so operad's LLM cassettes are
   captured under `run_dir/'cassettes/llm'`.
5. Construct `ArtemisRunner(selfserve_root=..., retrieval=cassette_rag)`.
6. Build the runner; load workspace metadata (when needed; for phase 1
   we read `WorkspaceMetadata` from a fixture or from a sidecar file —
   document the choice).
7. Construct `ArtemisInput(entry, workspace_metadata)`.
8. `answer, trace = await runner.run_with_trace(artemis_input)`.
9. Write `trace.jsonl`, `answer.txt`. Print a one-line summary.
10. Return exit code 0.

### `commands/show.py`

```bash
apps-uthereal show --trace-id ID [--frame STEP_NAME]
```

Flags:

- `--trace-id ID` (required).
- `--frame STEP_NAME` — focus on one leaf's frame; otherwise print all.

Behavior:

1. Read `.uthereal-runs/<trace_id_prefix>*/trace.jsonl`. Resolve the
   short trace ID against existing run dirs (allow prefix match).
2. Pretty-print:
   - Header: trace_id, entry_id, intent_decision, final_step,
     started/finished timestamps.
   - For each frame (or just the requested one): step_name, agent_class,
     input (truncated), output (truncated), latency_ms.
3. Return 0.

The output is plain text suitable for terminal viewing. No colors
required (but `rich` is acceptable if you keep a fallback for non-TTY).

### `commands/feedback.py`

```bash
apps-uthereal feedback --trace-id ID [--no-editor]
```

Behavior:

1. Read trace. Build a `HumanFeedback.template(trace_id)`.
2. Pretty-print the final answer to stdout (so the user can read what
   they're critiquing).
3. Write the template to `<run_dir>/feedback.json` with helpful inline
   comments (use a JSON-with-leading-comment-block file: comments at the
   top, then the JSON). Pre-fill `trace_id`.
4. Open `$EDITOR` on the file (skip with `--no-editor` for tests).
5. Re-read the file, validate as `HumanFeedback`, write back canonical
   JSON (no comments).
6. Return 0 on success, 2 on validation failure (print the error).

## Implementation notes

- **`run_dir` resolution.** Define `apps_uthereal.paths.run_dir(entry_id)`
  returning `runs_dir() / entry_id`. Used by all three commands.
- **Workspace metadata for phase 1.** Two acceptable shapes:
  1. The `DatasetEntry` JSON includes a `workspace` sub-object that
     deserializes to `WorkspaceMetadata` directly.
  2. A separate `--workspace-metadata PATH` flag.
  Pick (1) for simplicity. Document in the run command's `--help`.
- **Cassette env var.** Setting `OPERAD_CASSETTE` before constructing
  the runner is the operad-blessed way (see operad README §17). Make
  sure the cassette path passed to operad points to the run-dir
  subfolder.
- **Trace ID resolution.** Trace IDs are 16-char hex; entry IDs are
  12-char hex. The directory name is the entry ID. The trace file
  contains both. Accept either prefix in `--trace-id` (treat it as the
  entry ID for filesystem lookup, then verify trace_id matches).
- **`show` output stability.** `apps-uthereal show` MUST be
  deterministic across runs (C11). No timestamps in the printed output
  beyond what's already in the trace.
- **Editor handling.** Use `subprocess.run([os.environ.get("EDITOR",
  "vi"), path])`. Don't try to be clever; respect the user's `$EDITOR`.
- **Pre-fill the feedback template** with comments explaining each
  field:
  ```
  # trace_id: filled in for you
  # final_answer_critique: required — what's wrong with the answer
  # target_path: optional — null means let the Blamer decide; or set
  #   one of: context_safeguard, safeguard_talker, reasoner,
  #           conv_talker, rule_classifier, retrieval_orchestrator,
  #           evidence_planner, fact_filter, rag_talker.
  # severity: 0..1 (default 1.0)
  # desired_behavior: optional — what you'd want instead.
  {
    "trace_id": "...",
    "final_answer_critique": "",
    "target_path": null,
    "severity": 1.0,
    "desired_behavior": null
  }
  ```

## Acceptance criteria

- [ ] `apps-uthereal run --entry PATH` produces a fully-populated
      `.uthereal-runs/<entry_id>/` directory with all expected
      artifacts (entry.json, trace.jsonl, answer.txt, cassettes/).
- [ ] Re-running with `--cassette-mode replay` produces the same answer
      and trace_id.
- [ ] `apps-uthereal show --trace-id <id>` prints a deterministic,
      readable trace.
- [ ] `apps-uthereal show --trace-id <id> --frame reasoner` prints only
      that frame.
- [ ] `apps-uthereal feedback --trace-id <id> --no-editor` writes a
      template with all required fields populated correctly.
- [ ] After manual editing, `feedback` validates the JSON against
      `HumanFeedback` and rewrites it canonically.
- [ ] Invalid feedback (e.g. unknown `target_path`) returns exit code 2.

## Tests

- `test_run_creates_run_dir_artifacts` — invoke with mocked retrieval
  and a fixture entry; assert files exist.
- `test_run_replay_produces_same_trace_id`.
- `test_run_returns_2_on_missing_entry`.
- `test_show_prints_all_frames_by_default`.
- `test_show_filters_by_frame`.
- `test_show_resolves_short_trace_id`.
- `test_show_deterministic_output` — capture stdout twice; assert byte-equal.
- `test_feedback_writes_template_no_editor`.
- `test_feedback_template_has_all_required_fields`.
- `test_feedback_validates_after_edit` — write a valid edited file,
  assert canonical JSON written; write invalid, assert exit 2.

## References

- `apps/studio/operad_studio/cli.py` — sibling app's CLI patterns.
- `apps_uthereal/cli.py` (1-1) — dispatcher you slot into.
- `apps_uthereal/workflow/runner.py` (3-1) — `run_with_trace`.
- `apps_uthereal/feedback/schema.py` (1-5) — `HumanFeedback.template`.

## Notes

- Workspace metadata uses the task's option (1): the entry JSON may
  include a top-level `workspace` object that validates as
  `WorkspaceMetadata`. `DatasetEntry` itself remains unchanged; the CLI
  reads the raw JSON first and passes `workspace` separately into
  `ArtemisInput`. If the object is absent, the CLI uses minimal metadata
  containing only `workspace_id`, which keeps direct-answer and safeguard
  smoke runs usable without adding a second flag.
- `apps_uthereal.paths.run_dir(entry_id)` was added as requested by this
  task even though `paths.py` is marked `Owner: 1-1-skeleton`.
- `apps_uthereal.retrieval.client` currently exports the Protocol and
  `RetrievalError`, but not the concrete `LiveRetrievalClient` or
  `CassetteRetrievalClient` named in C6. To keep this task scoped, the
  run command owns small concrete wrappers locally instead of modifying
  the 1-4 retrieval file.
- `apps/uthereal/tests/test_cli.py` had a placeholder assertion for the
  old run-command stub (`Owner: 4-1`). It was updated to assert the new
  implemented missing-entry error.
- `feedback --no-editor` leaves a newly-created commented template in
  place so tests and humans can inspect/edit it. If `feedback.json`
  already exists, `--no-editor` validates that file and rewrites
  canonical JSON.
- Full-suite verification currently has unrelated pre-existing loader
  failures in `apps_uthereal/leaves/_common.py` / `errors.py`:
  `LoaderError` attribute/constructor handling and config override
  propagation. The command slice tests pass.
