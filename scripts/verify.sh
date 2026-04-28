#!/usr/bin/env bash
set -euo pipefail

uv run pytest tests/ -q --maxfail=1

for f in \
  examples/01_agent.py \
  examples/02_algorithm.py \
  examples/03_training.py \
  examples/04_evolutionary.py \
  examples/05_algorithm_gallery.py \
  examples/06_training_dashboard.py; do
    echo "== $f =="
    uv run python "$f" --offline
done

uv run --extra observers python demo.py --offline

echo "== apps/demos/agent_evolution/run.py =="
uv run python apps/demos/agent_evolution/run.py --offline --generations 2 --population 4 --seed 0

echo "== examples/benchmark (offline, 5 examples) =="
uv run python -m examples.benchmark.run \
    --offline --max-examples 5 --seeds 0 \
    --methods no_train,hand_edit,sweep,evo \
    --out /dev/null

echo "== apps/dashboard tests =="
( cd apps/dashboard && uv run pytest tests/ -q )

echo "== apps/studio tests =="
( cd apps/studio && uv run pytest tests/ -q )

if command -v pnpm >/dev/null 2>&1; then
    echo "== apps/frontend (typecheck, lint, vitest) =="
    (
        cd apps/frontend
        pnpm install --frozen-lockfile
        pnpm typecheck
        pnpm lint
        pnpm test
        if [ -n "${OPERAD_E2E:-}" ]; then pnpm test:e2e; fi
    )
else
    echo "[skip] pnpm not installed; skipping apps/frontend gates."
fi

echo "✅ verify complete."
