#!/usr/bin/env bash
set -euo pipefail

uv run pytest tests/ -q --maxfail=1

for f in \
  examples/mermaid_export.py \
  examples/custom_agent.py \
  examples/eval_loop.py \
  examples/evolutionary_demo.py \
  examples/train_demo.py \
  examples/observer_demo.py \
  examples/sweep_demo.py \
  examples/sandbox_pool_demo.py \
  examples/sandbox_tooluser.py; do
    echo "== $f =="
    uv run python "$f" --offline
done

uv run --extra observers python demo.py --offline

echo "== apps/demos/agent_evolution/run.py =="
uv run python apps/demos/agent_evolution/run.py --offline --generations 2 --population 4 --seed 0

echo "✅ verify complete."
