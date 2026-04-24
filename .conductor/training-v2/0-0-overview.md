# training-v2 — orchestration overview

Second iteration on the training layer built by `operad.optim §1..§5`.
Focus: close the "agents that learn → dashboards that show you the
learning" loop. Adds the small backend pieces the dashboards need,
then the UX on top.

## Pick-your-slot cheatsheet

Same format as the `operad.optim` plan: `<wave>-<slot>-<title>.md`.
Within a wave every slot edits disjoint files and can run in
parallel. Advance only when every slot in the current wave is merged.

### Wave 1 — backend (6 parallel tasks, all pure Python)

| Slot | Title                                         | Touches                                          |
| ---- | --------------------------------------------- | ------------------------------------------------ |
| 1-1  | EvoGradient mutation attribution              | `operad/optim/evo.py` + tests                    |
| 1-2  | DataLoader batch events                       | `operad/data/loader.py` + tests                  |
| 1-3  | `Trainer.save` / `Trainer.load`               | `operad/train/trainer.py` + tests                |
| 1-4  | `Agent.auto_tune(kind=...)` dispatcher        | `operad/core/agent.py` + tests                   |
| 1-5  | `UncertaintySampler` for active learning      | `operad/data/active.py` (new) + tests            |
| 1-6  | `Distill(teacher, student)` algorithm         | `operad/algorithms/distill.py` (new) + tests     |

### Wave 2 — consumers, apps, UX (5 parallel tasks)

| Slot | Title                                          | Touches                                                     |
| ---- | ---------------------------------------------- | ----------------------------------------------------------- |
| 2-1  | Dashboard fitness-curve panel                  | `apps/dashboard/operad_dashboard/fitness*` + templates      |
| 2-2  | Dashboard mutation-activity heatmap (needs 1-1)| `apps/dashboard/operad_dashboard/mutations*` + templates    |
| 2-3  | Dashboard PromptDrift timeline                 | `apps/dashboard/operad_dashboard/drift*` + templates        |
| 2-4  | `TrainerProgressObserver` + dashboard widget (needs 1-2) | `operad/train/progress.py` (new), `apps/dashboard/...` |
| 2-5  | `Studio` app: human-feedback labeling + training launcher | `apps/studio/` (new), `operad/train/callbacks.py`, `operad/train/losses_hf.py` (new) |

## Global rules (same as optim plan)

- Every slot ships offline tests. No CI run requires a live model.
- Imports only downward (`operad/optim` may not import
  `operad/train`; `operad/*` may not import from `apps/*`).
- `AlgorithmEvent` schema extensions live in `operad/runtime/events.py`
  and are backward-compatible: only *add* keys to `payload`, never
  remove. Dashboards must degrade gracefully when a key is absent.
- PR naming: `training-v2 §<wave>-<slot>: <title>`.

## Dependency graph

```
1-1 EvoGradient attrib ─────────────────┐
                                        │
1-2 DataLoader batch events ────────┐   │
                                    │   │
1-3 Trainer.save / .load ───────── independent
1-4 auto_tune(kind=...) ────────── independent
1-5 UncertaintySampler ─────────── independent
1-6 Distill ────────────────────── independent
                                    │   │
                                    │   ├──> 2-2 mutation heatmap (needs 1-1)
                                    │   └──> 2-1 fitness curve (no hard dep)
                                    │
                                    └──> 2-4 progress widget (needs 1-2)

                         2-3 PromptDrift timeline ── independent of wave 1
                         2-5 Studio app ────────────  independent of wave 1
```

## Success criteria for the whole iteration

1. `uv run python examples/talker_evolution.py --dashboard` streams a
   live fitness curve + mutation heatmap to the browser.
2. `uv run python examples/talker_evolution.py` prints an epoch-/
   generation-aware Rich progress bar in the terminal.
3. Starting `apps/studio/` and walking through its UI lets a human
   (a) rate a small batch of agent outputs, then (b) click "Train"
   and watch the trainer run fit() with those ratings as a
   `HumanFeedbackLoss`, all without leaving the browser.
4. The four backend primitives (save/load, auto_tune-dispatch,
   UncertaintySampler, Distill) each ship with offline tests and at
   least one docstring example.
