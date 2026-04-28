# 4-2 — `apply_fix` + CLI `fix`

**Batch:** 4 · **Parallelizable with:** 4-1, 4-3 · **Depends on:** 2-3, 2-4, 3-1

You are the optimizer half of the loop. Given a trace, a Blamer
verdict, and human feedback, you apply a targeted prompt rewrite to one
leaf and write the new YAML.

## Goal

Implement `apply_fix` (the in-process function) and its CLI front
(`fix`). C9 (optimizer scoping) is binding — exactly one leaf mutates,
verified post-step.

## Files to create

| Path | Purpose |
|---|---|
| `apps_uthereal/train/apply_fix.py` | `apply_fix`, `FixReport`, helpers |
| `apps_uthereal/commands/fix.py` | the `fix` subcommand |
| `apps_uthereal/tests/test_apply_fix.py` | unit + integration tests |

## API surface

```python
# apps_uthereal/train/apply_fix.py
"""Owner: 4-2-apply-fix."""
from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel, ConfigDict

import operad.optim.backprop
from operad.optim.optimizers.tgd import TextualGradientDescent

from apps_uthereal.workflow.runner import ArtemisRunner
from apps_uthereal.workflow.trace import WorkflowTrace
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.feedback.loss import HumanFeedbackLoss


TRAINABLE_FIELDS: tuple[str, ...] = ("role", "task", "rules")


class FixReport(BaseModel):
    target_path: str
    before_state: dict           # leaf.state() before
    after_state: dict            # leaf.state() after
    diff_text: str               # human-readable unified diff of role/task/rules
    yaml_path: Path
    yaml_dry_run: bool
    severity: float

    model_config = ConfigDict(arbitrary_types_allowed=True)


async def apply_fix(
    *,
    runner: ArtemisRunner,
    artemis_input,                       # ArtemisInput
    feedback: HumanFeedback,
    target_path: str,                    # already resolved (Blamer or manual)
    yaml_root: Path,                     # selfserve_root
    dry_run: bool = False,
    lr: float = 1.0,
) -> FixReport:
    """Run the targeted backward + step + dump_yaml.

    Steps (mirroring C9 exactly):
      1. Snapshot before_state = runner.state().
      2. Freeze every leaf; unfreeze (target.role, target.task, target.rules).
      3. Run runner inside operad.optim.backprop.tape() against artemis_input.
         (Cassettes replay the LLM/RAG calls; no live calls.)
      4. Compute (score, grad) = await HumanFeedbackLoss().compute(
            answer, feedback)
      5. await tape.backward(grad,
            parameters=list(target_leaf.parameters()))
      6. await TextualGradientDescent(target_leaf.parameters(), lr=lr).step()
      7. _assert_only_target_changed(runner, target_path, before_state).
      8. If not dry_run: dump_yaml(target_leaf, yaml_path,
            source_path=yaml_path).
      9. Build FixReport.

    Raises:
      - UnactionableFeedback when the loss refuses (special target).
      - AssertionError if the post-step invariant fails.
    """


def _assert_only_target_changed(
    runner: "Agent", target_path: str, before_state: dict,
) -> None: ...


def _yaml_path_for_step(yaml_root: Path, step_name: str) -> Path:
    """Map step_name → absolute YAML path under yaml_root.

    Inverse of LEAF_REGISTRY's relative paths from 2-1."""


# apps_uthereal/commands/fix.py
def add_parser(subparsers) -> None: ...
async def run(args) -> int: ...
```

CLI:

```bash
apps-uthereal fix --trace-id ID [--target STEP_NAME] [--dry-run]
                  [--selfserve-root PATH] [--lr FLOAT]
```

Behavior:

1. Read trace and feedback from `.uthereal-runs/<entry_id>/`.
2. Resolve `target_path`:
   - If `--target` is set, use it.
   - Else read `<run_dir>/blame.json` (written by `4-3`); use
     `BlamerOutput.target_path`.
   - If neither is available, return exit 2 with a "no target —
     run `apps-uthereal blame` first or pass --target" message.
3. Reject special targets (`control_flow`, `data`, `no_fault`) with a
   structured error explaining why no leaf rewrite would help.
4. Construct `ArtemisRunner` (cassette-replay mode, no live calls).
5. Reconstruct `ArtemisInput` from `entry.json`.
6. Call `apply_fix(...)`. Print the diff.
7. If not `--dry-run`, write the YAML and print the path.
8. Write `<run_dir>/fix.diff` (the unified diff text) and `<run_dir>/
   fix.json` (a JSON dump of `FixReport`, excluding `before_state` /
   `after_state` to keep the artifact small — keep `target_path`,
   `severity`, `yaml_path`, `yaml_dry_run`, `diff_text`).
9. Return 0.

## Implementation notes

- **`runner.state()` vs `runner.named_parameters()`.** Use `state()` for
  the before/after snapshot (it returns the declared-state dict,
  including non-trainable fields). For the assertion, compare:
  ```python
  before = runner.state()        # full snapshot
  ...
  after = runner.state()
  for path, value in before.items():
      if not path.startswith(target_path + "."):
          assert after[path] == value, f"unexpected change at {path}"
  ```
- **Param scoping.** Operad's `freeze_parameters("**")` freezes all
  parameters under the runner. Then unfreeze only the target's:
  ```python
  runner.freeze_parameters("**")
  runner.unfreeze_parameters(**{
      f"{target_path}.role": True,
      f"{target_path}.task": True,
      f"{target_path}.rules": True,
  })
  ```
  Verify with:
  ```python
  trainable = [p for p in runner.parameters() if p.requires_grad]
  for p in trainable:
      assert p.path.startswith(target_path + "."), f"unexpected trainable: {p.path}"
  ```
- **Tape replay under cassettes.** The runner's leaves all have cassette
  hits from the original `apps-uthereal run`. Inside `tape()`, those
  hits replay deterministically. The whole `apply_fix` runs without
  network or LLM I/O.
- **Backward scoping.** Pass `parameters=list(target_leaf.parameters())`
  to `tape.backward(...)`. This is belt-and-suspenders — even if a
  gradient leaks, no off-target parameter has `requires_grad=True`,
  and `optimizer.step()` will skip frozen params.
- **Optimizer.** `TextualGradientDescent` is the simplest (per the
  `simple exercise` directive). `lr` defaults to `1.0` (full rewrite);
  expose as flag for users who want softer nudges.
- **Diff rendering.** Use `difflib.unified_diff` over the role/task/
  rules text. For rules, render as `\n`-joined for the diff. Limit
  context lines to 3.
- **Source-path-aware dump.** Pass `source_path=yaml_path` to
  `dump_yaml` so comments and ordering survive the rewrite (C5).
- **Verification.** Re-load the YAML and assert the target leaf's
  `hash_content` matches the in-memory leaf's `hash_content`. This
  closes the round-trip loop.
- **Idempotency in dry-run.** With `--dry-run`, `runner.state()` is
  *not* mutated permanently — clone the runner first (`runner.clone()`)
  so subsequent commands see the original state. Or revert the
  parameter values from `before_state` after computing the diff. Pick
  one; document it.

## Acceptance criteria

- [ ] `apply_fix(runner, x, fb, "reasoner", root)` returns a
      `FixReport` whose `diff_text` is non-empty when the gradient is
      non-empty.
- [ ] Post-step, only the target leaf's `state()` differs.
- [ ] `--dry-run` does not write the YAML; `--no-dry-run` does.
- [ ] After a non-dry-run, re-loading the YAML produces a leaf with
      `hash_content == in_memory_leaf.hash_content`.
- [ ] `apply_fix` with `target_path="control_flow"` (or other special)
      raises `UnactionableFeedback`; the CLI exits 1 with a clear
      message.
- [ ] `apply_fix` runs entirely under cassette replay — zero network
      calls (verified by passing a `RetrievalClient` mock that asserts
      `assert False` if `retrieve` is called and the cassette has the
      result).
- [ ] No imports from `uthereal_*`.

## Tests

- `test_apply_fix_mutates_only_target` — fixture trace + feedback;
  assert before/after diffs are confined to the target.
- `test_apply_fix_dry_run_does_not_write_yaml`.
- `test_apply_fix_writes_yaml_when_not_dry` — assert YAML path
  re-loads to equal `hash_content`.
- `test_apply_fix_raises_on_special_targets` — parametrize over
  control_flow / data / no_fault.
- `test_apply_fix_no_network` — pass an asserting mock retrieval client.
- `test_apply_fix_diff_text_unified_format`.
- `test_cmd_fix_uses_blame_json_when_target_absent`.
- `test_cmd_fix_returns_2_when_no_target_available`.
- `test_cmd_fix_writes_run_dir_artifacts`.

## References

- `operad/train/trainer.py` — reference for `tape() → backward() → step()`
  pattern.
- `operad/optim/optimizers/tgd.py` — `TextualGradientDescent`.
- `operad/core/agent.py` — `state()`, `clone()`, `freeze_parameters`.
- `operad/optim/parameter.py` — `Parameter.requires_grad`, `Parameter.path`.

## Notes

- Dry-run idempotency is handled by running the normal targeted step on the
  supplied runner, building the report from the post-step state, then restoring
  the target leaf's `role`, `task`, and `rules` plus all pre-existing
  `requires_grad` overrides. This avoids cloning an `ArtemisRunner`; cloning
  drops YAML metadata on cloned leaves and would require rebuilding provider
  runners in offline tests.
- `Agent.state()` returns an `AgentState` tree in this checkout, not the flat
  path dictionary shown in the brief. `apply_fix` flattens that tree internally
  for the C9 off-target assertion and keeps `FixReport.before_state` /
  `after_state` as the target leaf's JSON state.
- `Agent.freeze_parameters()` does not expose public flags for every config
  parameter yielded by `named_parameters()` (`config.model`, `config.backend`,
  `config.io.renderer`). To make the C9 trainable-parameter check exact,
  `apply_fix` snapshots and writes the agents' existing requires-grad override
  maps, then restores them before returning.
- This checkout does not contain the public `CassetteRetrievalClient` described
  by task 1-4. The `fix` command therefore includes a small replay-only reader
  for the documented `retrieve/<key>.json` and `metadata/<workspace_id>.json`
  cassette layout, scoped to the command file.
- Existing `dump_yaml(..., source_path=...)` can preserve comments in a way that
  reloads section comments inside `prompt.rules` as rule text for the reasoner
  fixture. `apply_fix` first uses the source-path-aware dump, then falls back to
  rewriting only `role`, `task`, `closure`, and `rules` if the required
  post-dump `hash_content` round-trip check fails.
