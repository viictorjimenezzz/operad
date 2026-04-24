# 5-2 — Documentation updates

**Wave.** 5 (depends on everything in 1-4 being shipped).
**Parallel with.** 5-1, 5-3, 5-4, 5-5.

## Context

The optim/train layer is invisible until the docs describe it.
Update `README.md`, `VISION.md`, `FEATURES.md`, and write the first
tutorial.

Read the current versions of those files plus
`.context/NEXT_ITERATION.md`.

## Scope — in

### `README.md`

- Add a new section under "Core ideas" — something like:

  > **Agents are trainable.** Every mutable field on an Agent —
  > role, task, rules, examples, temperature — is a `Parameter`.
  > `operad.optim` provides `TextualGradientDescent`,
  > `MomentumTextGrad`, `EvoGradient`, `OPROOptimizer`, and
  > `APEOptimizer` — all subclasses of a shared `Optimizer` base —
  > plus a `Trainer` that wraps fit/evaluate/predict with callbacks
  > and LR schedulers.

- Add a "Training" code block alongside the existing "Run the demo"
  section, showing the 10-line fit loop (copy from
  `operad/optim/README.md`).
- Add `operad/optim/` and `operad/train/` to the `operad/` layout
  block.
- Bump the top-level one-liner if it now undersells the library.

### `VISION.md`

- Mark the Iteration-4 milestone from §7 as **SHIPPED** with a
  pointer to `.construct/optim/*.md` and the commit range.
- Update §4 (PyTorch analogy table) to include the new rows for
  `nn.Parameter → operad.optim.Parameter`,
  `loss.backward() → tape.backward(loss)`,
  `torch.optim.* → operad.optim.*`,
  `torch.utils.data.DataLoader → operad.data.DataLoader`,
  `lightning.Trainer → operad.train.Trainer`,
  `torch.no_grad() → operad.no_grad()`,
  `register_forward_hook → Agent.register_forward_hook`.
- Update §6 (today's layout) to list the new folders.
- Update §7 (upcoming) — move the `Evolutionary`-as-optimizer north
  star from "planned" to "achieved" and push the `AutoResearcher on
  8 slots` milestone forward as the next goal.
- Append a short §10 "Training as the next frontier" capturing the
  TextGrad/OPRO/APE family + meta-optim note + the philosophical
  through-line: *the library now contains both inference and
  training*.

### `FEATURES.md`

- Add §21 "Training & optimization" covering:
  - `Parameter` + `parameters()` + `mark_trainable`.
  - `Loss` protocol + `LossFromMetric` + `CriticLoss`.
  - `tape()` / `backward()` / hooks / `no_grad()`.
  - The optimizer fleet with a one-liner each.
  - `LRScheduler` list with one-liner each.
  - `Trainer` surface: `fit`/`evaluate`/`predict`, callbacks, gradient
    accumulation.
  - `DataLoader` + `random_split`.
  - `state_dict` / `load_state_dict` aliases.
- Add §22 "PromptTraceback" once 5-4 is in (or leave a forward
  reference if 5-4 hasn't merged yet; coordinate in the PR).

### `TRAINING.md` (new file at repo root)

- Tutorial-style walkthrough targeted at a user who already read the
  README but hasn't written a training loop.
- Table of contents:
  1. What are we optimizing? (role / task / rules / examples / sampling)
  2. Constructing your first trainable agent (`mark_trainable`).
  3. Picking a loss.
  4. The fit loop in one page.
  5. Picking an optimizer: when to use which.
  6. Schedulers and when they matter.
  7. Callbacks and checkpointing.
  8. Debugging: hooks, traceback, `no_grad()`.
  9. Reproducibility: cassettes and determinism.
  10. Further reading: `.context/NEXT_ITERATION.md`, papers.
- Roughly 1500-2500 words. Keep it concrete; use real code blocks.

## Scope — out

- Do not change the existing `examples/*.py` narratives beyond
  adding a cross-link in `README.md` to `train_demo.py` once 5-1
  has landed.
- Do not add external images or diagrams. Markdown + code only.
- Do not retitle `VISION.md` or restructure `FEATURES.md` top-level
  sections — append, don't reshuffle.

## Dependencies

- Everything in waves 1-4.
- Preferably 5-1 (demo) has landed so the tutorial can reference it
  by file name.

## Design notes

- **Write for a senior engineer who has not opened the repo.** Avoid
  "trust me" phrases; show specific method calls. Cross-link with
  anchors.
- **Preserve the repo's voice.** Existing docs are terse and direct;
  do not break tone.
- **Accuracy over rhetoric.** When you cite a method signature, make
  sure it matches the actual code. If you're unsure, read the file.
- **Do not invent features.** If the spec from
  `.context/NEXT_ITERATION.md` is not yet implemented, phrase it as
  "planned" with a reference, not "available now."

## Success criteria

- `README.md`, `VISION.md`, `FEATURES.md`, `TRAINING.md` all
  render cleanly as markdown (no broken links, no wrong code-fence
  tags).
- No documentation claims a method that doesn't exist in the code.
- The new `TRAINING.md` is linked from `README.md`.
- No code changes.
