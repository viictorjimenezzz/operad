# 2-5 — `Studio` app: human-feedback labeling + training launcher

**Wave.** 2. **Parallel with.** 2-{1..4}. **Depends on.** 1-3 (`Trainer.save/load`), 1-4 (`auto_tune(kind=...)`).

## Context

Closes the "agents improve because humans tell them what's good"
loop. Combines three things:

1. A `HumanFeedbackCallback` (Trainer-side) that dumps per-row
   `(input, output, run_id, sample_id)` tuples to an NDJSON file
   during `Trainer.fit` / `Trainer.predict`.
2. A `HumanFeedbackLoss` that reads a ratings file (same shape
   augmented with `rating: float`) and scores the agent against the
   latest rating for each `(input, output)` hash.
3. A `Studio` FastAPI app at `apps/studio/` that:
   - Lists labeling jobs (each corresponds to a pending NDJSON),
   - Presents each row with the agent's output and a 1-5 star /
     slider widget,
   - Writes back ratings to the NDJSON,
   - Exposes a "Train" button that launches a `Trainer.fit` on the
     ratings and streams progress via the existing dashboard
     infrastructure.

This is the largest slot in the plan; treat as a small, focused PR
per sub-component rather than one giant diff if the author prefers
(3 sub-PRs: callback+loss, Studio app shell, Studio-to-dashboard
handoff — each owns its own tests).

## Scope — in

### `operad/train/callbacks.py` (extend)

```python
class HumanFeedbackCallback(Callback):
    """Dump (input, output, run_id, sample_id) rows to an NDJSON for human rating.

    Rows written during `on_batch_end` / `on_validation_end`. Each row:
        {"id": str, "run_id": str, "agent_path": str,
         "input": dict, "output": dict, "rating": null,
         "written_at": iso8601}
    The human labeling UI fills `rating` in-place later.
    """

    def __init__(self, path: str | Path, *, on: Literal["train","val"] = "val") -> None: ...
```

### `operad/train/losses_hf.py` (new)

```python
class HumanFeedbackLoss(Loss):
    """Score an agent against a human-rated NDJSON file.

    For each inference, look up the matching `(input_hash, output_hash)`
    row in the ratings file; if rated, return (rating/5, gradient);
    else return null (skip this sample).
    """

    name = "human_feedback"

    def __init__(
        self,
        ratings_path: str | Path,
        *,
        gradient_template: str = "Human rated this {rating}/5 — rating rationale: {rationale}",
    ) -> None: ...
```

### `apps/studio/` (new directory — parallel to `apps/dashboard/`)

Structure mirroring the dashboard:
- `apps/studio/pyproject.toml` — CLI entry point `operad-studio`.
- `apps/studio/operad_studio/app.py` — FastAPI app with:
  - `GET /` — list all NDJSON files in the data dir, with
    unrated-count badges.
  - `GET /jobs/{job_name}` — label-this-job page: paginated rows
    with rating UI (1-5 slider + free-text rationale).
  - `POST /jobs/{job_name}/rows/{row_id}` — persist a single rating.
  - `POST /jobs/{job_name}/train` — kick off a `Trainer.fit` with
    `HumanFeedbackLoss(ratings_path)`; stream progress events back
    via SSE. Training runs in a background task via `asyncio.create_task`.
  - `GET /jobs/{job_name}/train/stream` — SSE of training progress.
  - `GET /jobs/{job_name}/download` — serve the rated NDJSON.
- `apps/studio/operad_studio/templates/` — Jinja: index + job +
  train-status partials.
- `apps/studio/operad_studio/static/` — vanilla JS + CSS.
- `apps/studio/operad_studio/cli.py` — `operad-studio --port 7870
  --data-dir /tmp/operad-feedback --agent-bundle PATH`.
  - `--agent-bundle` points at a `Trainer.save(...)` JSON file.
  - Studio loads the bundle via `Trainer.load(path)` at request
    time.

### Tests

- `tests/train/test_human_feedback.py`:
  - `HumanFeedbackCallback` writes one NDJSON row per sample.
  - `HumanFeedbackLoss.compute` reads ratings and returns sensible
    `(score, gradient)` tuples.
  - Unrated rows → skip (loss returns 0-severity / caller skips).
- `apps/studio/tests/test_studio_app.py`:
  - Index page lists jobs.
  - Rating POST persists to disk.
  - Train endpoint launches `Trainer.fit` and streams events.

## Scope — out

- Do not require an authentication layer. Local-only app.
- Do not persist ratings in a database. NDJSON on disk is enough;
  the data dir is a CLI arg.
- Do not support multi-user conflict resolution. Single-human
  labeling.
- Do not re-implement the dashboard's event streaming; the Studio's
  train launcher forwards events to the running dashboard via
  `operad.dashboard.attach(...)` so both UIs stay in sync.

## Dependencies

- 1-3: `Trainer.save / Trainer.load`.
- 1-4: `Agent.auto_tune(kind=...)` — Studio may also launch via
  `auto_tune` directly (no trainer needed for pure-evo runs).
- Existing: `operad.dashboard.attach`, `WebDashboardObserver`.

## Design notes

- **Data flow.** Callback writes `hf.jsonl`; human rates via Studio;
  Studio train button calls `Trainer.load(bundle) + HumanFeedbackLoss(hf.jsonl)`;
  training progress streams to the existing dashboard (and Studio's
  own status page).
- **Bundle dependency.** Studio needs a `Trainer.save` bundle to
  load from — that's why 1-3 is a dependency. For users who want to
  train from scratch, Studio can also accept `--agent-class
  operad.agents.conversational.Talker` + `--config-json ...` and
  construct a fresh Trainer from those.
- **Rating UI.** 5-step slider (1-5) + free-text rationale textarea
  (the rationale becomes the gradient message).
- **Navigation.** Simple: top nav with "Jobs", "Runs" (links to
  dashboard on the configured port), "Settings".
- **Testing strategy.** Mock out the actual LLM (FakeLeaf); test
  end-to-end that: rate 3 rows → click Train → finished event fires.

## Success criteria

- `uv pip install -e apps/studio/` and `operad-studio --port 7870
  --data-dir /tmp/feedback --agent-bundle /tmp/talker.json` launches
  a working app.
- A human can label ≥ 3 rows, click Train, and watch a training run
  complete (event log visible in Studio and in the dashboard).
- The trained agent's bundle is written back to disk and listed in
  Studio's index for the next round.
- `pytest apps/studio/tests/ tests/train/test_human_feedback.py`
  passes.
