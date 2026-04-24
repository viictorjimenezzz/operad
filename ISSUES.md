# ISSUES — Known risks, footguns, and gaps

Catalogue of problems identified in the codebase. Each issue carries a
severity tag and a strategy pointer; full implementation direction
lives in the per-stream briefs under `.conductor/`.

**Status log.**
- **2026-04-23** — All remaining issues have been fixed.
- **2026-04-24** — Three pre-existing issues surfaced during PR C; all
  predate PR A (reproduced on `main`). Left unfixed per "No feature
  changes" rule in the refactor plan.
  - **F-1 (Med)** `tests/runtime/test_tracing_watch.py::test_watch_missing_rich_degrades`
    failed deterministically on `main`: the test monkey-patched
    `importlib.import_module` but `operad.tracing.watch` uses a
    `from X import Y` statement that doesn't route through
    `importlib.import_module`, so the warning never fired. Fixed in
    PR C with a one-line `monkeypatch.delattr(obs_pkg,
    "RichDashboardObserver", raising=False)` — blocked the
    `scripts/verify.sh` goalpost.
  - **F-2 (Med)** `Agent.abuild()` replaces `self._children`
    values with their *classes* (not instances). This breaks
    `agent.clone()` and `agent.diff(other)` after a build: `state()`
    then tries to call `state` on what is now a class attribute
    (`JSONSerializableDict`). `demo.py` stage 5 now rebuilds a fresh
    pair of unbuilt agents to avoid the issue; the underlying framework
    bug remains.
  - **F-3 (Low)** `examples/evolutionary_demo.py::RuleCountMetric` did
    not implement the `Metric` protocol's `score_batch` method; called
    by `evaluate()` it raised `AttributeError`. Fixed in PR C by
    inheriting from `operad.metrics.base.MetricBase`.

Severity key:
- **High** — silent correctness risk; user sees wrong behaviour without warning.
- **Med** — honest failure modes but rough DX, dead knobs, or inconsistencies.
- **Low** — polish, docs, or test coverage.

---

## How to use this file

- When you open a PR, cite the issue numbers you address in the
  description.
- If you find a new issue while working, add it here in the matching
  section (most likely §E or a new §F) and include the update in
  your PR.
- If a fix is out of scope for your stream, leave a one-line note in
  `.conductor/notes/` (create the folder if needed) and keep moving.
- When every active issue is resolved, mark the §E entries "RESOLVED"
  with a commit hash and append a new section for the next round.
