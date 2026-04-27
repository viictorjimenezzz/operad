# 5-1 — `verify` + demo + README

**Batch:** 5 · **Parallelizable with:** — (single task) · **Depends on:** all of 1, 2, 3, 4

You are the closer. After this task ships, the loop runs end-to-end:
`run → feedback → blame → fix → verify`. You also write the README and
a `make demo` target the reviewer uses to evaluate the bridge.

## Goal

Implement `verify` (the last CLI subcommand). Replace the stub README
with a full walkthrough. Provide a `make demo` target that runs the
full loop on a checked-in fixture.

## Files to create / replace

| Path | Action |
|---|---|
| `apps_uthereal/commands/verify.py` | new — the `verify` subcommand |
| `apps/uthereal/README.md` | replace stub with full walkthrough |
| `apps/uthereal/Makefile` | extend with `demo`, `clean-runs`, `cassettes-check` |
| `apps/uthereal/fixtures/entries/demo_entry.json` | new — checked-in entry |
| `apps/uthereal/fixtures/cassettes/demo_entry/{llm,rag}/...` | new |
| `apps/uthereal/tests/test_cmd_verify.py` | new — tests |
| `apps/uthereal/tests/test_demo_loop.py` | new — full-loop integration test |

## API surface

```python
# apps_uthereal/commands/verify.py
"""Owner: 5-1-verify-and-demo."""
from __future__ import annotations

def add_parser(subparsers) -> None: ...
async def run(args) -> int: ...
```

CLI:

```bash
apps-uthereal verify --trace-id ID [--selfserve-root PATH]
                     [--rag-base-url URL]
```

Behavior:

1. Read `<run_dir>/{trace.jsonl, answer.txt, fix.json}`.
2. Reconstruct the `ArtemisInput` from `entry.json`.
3. Construct a fresh `ArtemisRunner` against the *current* selfserve
   YAMLs (the rewritten one is now in place from `apps-uthereal fix`).
4. Construct a `CassetteRetrievalClient(mode="record-missing")` so:
   - Cassettes for unchanged retrieval calls replay.
   - The target leaf's prompt changed → its LLM cassette will miss →
     re-record.
   - Downstream leaves whose inputs depend on the changed leaf will
     also miss → re-record.
5. `new_answer, new_trace = await runner.run_with_trace(input)`.
6. Build a side-by-side diff:
   - Old answer vs new answer (whole text + first-N-words diff).
   - Old `intent_decision` vs new.
   - Old vs new `final_step`.
   - For the target leaf: old `output` vs new `output`.
7. Write `<run_dir>/verify.json` with the structured result:
   ```json
   {
     "trace_id_before": "...",
     "trace_id_after": "...",
     "before_answer": "...",
     "after_answer": "...",
     "before_intent": "...",
     "after_intent": "...",
     "before_final_step": "...",
     "after_final_step": "...",
     "target_path": "reasoner",
     "leaf_output_diff": { "before": {...}, "after": {...} },
     "rerecorded_steps": ["reasoner", "rag_talker", ...]
   }
   ```
8. Print the human-readable diff.
9. Return 0.

## README content (full version)

The README replaces the stub from 1-1 and lives at
`apps/uthereal/README.md`. Required sections:

- **What this is** — one paragraph: bridge between operad and uthereal's
  selfserve workflow; cassette-deterministic prompt-fixing loop.
- **Architecture** — link to `.conductor/uthereal/AGENTS.md` and inline
  the dependency graph.
- **Quick start** — exact commands to run the demo:
  ```bash
  uv sync
  make -C apps/uthereal demo
  ```
- **CLI reference** — every command with one-line description and the
  flags. Don't duplicate `--help`; just orient.
- **Run-directory layout** — copy from C12.
- **Adding a new entry** — the workflow:
  1. Author `DatasetEntry` JSON (template provided in
     `fixtures/entries/`).
  2. `apps-uthereal run --entry path/to/entry.json` (record cassettes).
  3. `apps-uthereal show --trace-id ID` (inspect).
  4. `apps-uthereal feedback --trace-id ID` (write feedback).
  5. `apps-uthereal blame --trace-id ID` (assign blame).
  6. `apps-uthereal fix --trace-id ID --dry-run` (preview the diff).
  7. `apps-uthereal fix --trace-id ID` (apply).
  8. `apps-uthereal verify --trace-id ID` (rerun and diff).
- **Tests** — how to run them (`uv run pytest apps/uthereal/tests/`).
- **Out of scope** — copy from AGENTS.md §9.
- **Schema drift** — `make schemas-check`.

## Makefile targets

```makefile
.PHONY: demo clean-runs schemas-check cassettes-check

demo:
	uv run apps-uthereal run     --entry fixtures/entries/demo_entry.json --cassette-mode replay
	uv run apps-uthereal show    --trace-id $$(cat .uthereal-runs/.demo_id)
	uv run apps-uthereal feedback --trace-id $$(cat .uthereal-runs/.demo_id) --no-editor
	uv run apps-uthereal blame   --trace-id $$(cat .uthereal-runs/.demo_id) --target reasoner --no-confirm
	uv run apps-uthereal fix     --trace-id $$(cat .uthereal-runs/.demo_id) --dry-run
	uv run apps-uthereal fix     --trace-id $$(cat .uthereal-runs/.demo_id)
	uv run apps-uthereal verify  --trace-id $$(cat .uthereal-runs/.demo_id)

clean-runs:
	rm -rf .uthereal-runs

schemas-check:
	uv run python apps/uthereal/scripts/schemas_check.py

cassettes-check:
	uv run python apps/uthereal/scripts/cassettes_check.py
```

The demo flow uses `--target reasoner` to skip the Blamer's LLM call
(the Blamer's behavior is non-deterministic without recorded cassettes;
manual override keeps `make demo` hermetic).

## Demo entry

`fixtures/entries/demo_entry.json` is a hand-crafted, in-scope dataset
entry where the original Reasoner's prompt produces a sub-optimal route
(e.g. routes a clear RAG question as DIRECT_ANSWER), and the human
feedback unambiguously points at the Reasoner.

The demo's purpose: a reviewer can reproduce the full loop in one
command, see the diff, see the verify, and decide whether the loop
works. Use a fictional workspace (e.g. "industrial manufacturing
safety") and a fictional question that's clearly RAG-needed.

## Implementation notes

- **`record-missing` for verify.** This is the only command besides
  `run` that can record. The cassettes for the target leaf and its
  downstream consumers will miss on first verify; subsequent verifies
  replay.
- **`rerecorded_steps`.** Inspect the cassette state before/after the
  verify run to compute which step's cassette was newly recorded. This
  is debugging signal — the user can confirm "yes, only the rewritten
  leaf and the talker after it re-recorded; everything else replayed".
- **Demo determinism.** With cassettes checked in, `make demo` produces
  byte-identical output across runs. Verify in CI by running it twice
  and asserting identical stdout.
- **Workspace metadata for demo.** Bundle the metadata inline in the
  `DatasetEntry` JSON. Avoid a separate file for the demo to keep it
  one-step.
- **The `verify` LLM cassette miss.** When the target leaf's prompt
  changes, operad's cassette key changes, so the LLM call misses. If
  the inner `LiveRetrievalClient` is `None` (no `--rag-base-url`), the
  miss raises. The demo provides cassettes for the post-fix prompts as
  well — recorded once during fixture authoring, checked in. This means
  the demo doesn't need a live Gemini account.

## Acceptance criteria

- [ ] `apps-uthereal verify --trace-id ID` produces `verify.json` with
      every documented field.
- [ ] When the fix is a no-op (e.g. `--dry-run` skipped the YAML write),
      `verify` reports zero rerecorded steps.
- [ ] `make demo` runs end-to-end in under 60 seconds on a clean
      `.uthereal-runs/`, and exits 0.
- [ ] Two consecutive `make demo` runs produce byte-identical stdout
      (after `make clean-runs`).
- [ ] README's "Quick start" section actually works as written.
- [ ] No imports from `uthereal_*`.

## Tests

- `test_cmd_verify_writes_verify_json` — fixture trace + applied fix;
  assert verify.json has all keys.
- `test_cmd_verify_when_unchanged_yaml_returns_no_rerecord`.
- `test_cmd_verify_propagates_cassette_miss_when_inner_unset` — when
  no live client and a leaf's cassette is missing, raise.
- `test_demo_loop_e2e` — `subprocess.run` the demo target end-to-end;
  assert exit 0.
- `test_demo_loop_byte_identical_across_runs`.

## References

- `apps_uthereal/commands/run.py` (4-1) — patterns for run-dir
  resolution and cassette wiring.
- `apps_uthereal/train/apply_fix.py` (4-2) — the artifacts you read
  (`fix.json`, the rewritten YAML).
- `apps/demos/triage_reply/run.py` — pattern for a self-contained
  end-to-end demo script.

## Notes

(Append discoveries here as you implement. Especially: any flake in the
demo's byte-identical stdout property and how you stabilized it.)
