# 4-3 — CLI `blame`

**Batch:** 4 · **Parallelizable with:** 4-1, 4-2 · **Depends on:** 2-3, 3-1

You are the bridge between the human's natural-language feedback and a
leaf-targeted gradient. The blame command runs the Blamer agent and
serializes its verdict.

## Goal

Implement `apps-uthereal blame` as a CLI subcommand. Read trace and
feedback, run the `Blamer` agent, write `blame.json`. Allow human
override via flag.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/commands/blame.py` | the `blame` subcommand |
| `apps_uthereal/tests/test_cmd_blame.py` | tests |

## API surface

```python
# apps_uthereal/commands/blame.py
"""Owner: 4-3-cli-blame."""
from __future__ import annotations

def add_parser(subparsers) -> None: ...
async def run(args) -> int: ...
```

CLI:

```bash
apps-uthereal blame --trace-id ID [--feedback PATH]
                    [--target STEP_NAME] [--no-confirm]
                    [--selfserve-root PATH]
```

Flags:

- `--trace-id ID` (required).
- `--feedback PATH` — defaults to `<run_dir>/feedback.json`.
- `--target STEP_NAME` — manual override; skips the Blamer.
- `--no-confirm` — don't prompt for confirmation; just write blame.json.
- `--selfserve-root PATH` — needed to load leaves for `LeafSummary`s.

Behavior:

1. Resolve `<run_dir>` from trace-id (allow prefix match, same as
   `show`).
2. Read `trace.jsonl` and `feedback.json`. Validate.
3. **If `--target` is set:** synthesize a `BlamerOutput` directly
   (skip the Blamer call):
   ```python
   BlamerOutput(
       target_path=args.target,
       rationale=f"Manual override via --target {args.target}.",
       leaf_targeted_critique=feedback.final_answer_critique,
       severity=feedback.severity,
   )
   ```
4. **Else:** load all leaves (for the `leaf_directory`); call
   `render_blamer_input`; run `Blamer()` against it. Use cassettes
   under `<run_dir>/cassettes/llm/` (the Blamer's call gets its own
   cassette key automatically — operad handles this).
5. Print the verdict (target_path, rationale, leaf_targeted_critique).
6. Unless `--no-confirm`, prompt: `Apply this blame? [Y/n/edit] `.
   - `Y` (default): write `blame.json`, return 0.
   - `n`: do not write, return 0.
   - `edit`: open `$EDITOR` on a JSON template prepopulated with the
     Blamer's verdict; on save, validate as `BlamerOutput` and write.
7. Return 0.

## Implementation notes

- **No-confirm semantics.** Useful for scripted pipelines (CI demos,
  the `5-1-verify-and-demo` flow). When set, `Y` is implicit.
- **Manual override deserves an audit trail.** The synthesized
  `BlamerOutput` has a clear `rationale` saying it was a manual
  override. Don't hide that — `apply_fix` should still print "blame
  source: manual" so the user remembers.
- **Cassette path.** Use the same `<run_dir>/cassettes/llm/` so the
  Blamer's call is recorded next to the workflow's calls. After the
  first blame, subsequent re-runs replay deterministically.
- **`leaf_directory`.** All nine leaves (loaded from YAML), including
  ones that didn't fire in this run. The Blamer needs them all so it
  can reason about leaves that *should* have fired.
- **Editor flow.** Same as the `feedback` command's editor handling:
  `subprocess.run([os.environ.get("EDITOR", "vi"), path])`.
  Template includes the Blamer's verdict pre-filled, with comments
  explaining each field.
- **Print the answer.** Print the trace's `final_answer_text` to stdout
  before showing the Blamer verdict, so the user has context.

## Acceptance criteria

- [ ] `apps-uthereal blame --trace-id ID --no-confirm` writes
      `<run_dir>/blame.json` deserializable as `BlamerOutput`.
- [ ] `apps-uthereal blame --trace-id ID --target reasoner --no-confirm`
      writes a `BlamerOutput` with `target_path="reasoner"` and
      `rationale` containing "manual".
- [ ] `apps-uthereal blame` with no feedback file present returns
      exit 2 with a clear message.
- [ ] `apps-uthereal blame` with malformed feedback returns exit 2.
- [ ] Re-running `blame` on the same trace with cassettes replays
      deterministically (same `BlamerOutput`).
- [ ] `--target` with an unknown step_name returns exit 2 with the
      list of valid step_names.

## Tests

- `test_cmd_blame_writes_blame_json_no_confirm` — happy path.
- `test_cmd_blame_manual_override_skips_blamer_call` — assert no LLM
  cassette miss; assert rationale contains "manual".
- `test_cmd_blame_replay_deterministic`.
- `test_cmd_blame_missing_feedback_returns_2`.
- `test_cmd_blame_invalid_target_returns_2`.
- `test_cmd_blame_special_target_writes_blame_json` — manual override
  with `--target control_flow` writes the verdict; `apply_fix` later
  refuses gracefully (that's tested in 4-2).

## References

- `apps_uthereal/feedback/blamer.py` (2-3) — `Blamer`,
  `render_blamer_input`, `BlamerOutput`, `KNOWN_LEAF_PATHS`,
  `SPECIAL_TARGETS`.
- `apps_uthereal/leaves/registry.py` (2-1) — `load_all_leaves`.
- `apps_uthereal/workflow/trace.py` (1-5) — `WorkflowTrace.from_jsonl`.

## Notes

(Append discoveries here as you implement.)
