#!/usr/bin/env bash
set -euo pipefail

uv run pytest tests/ -q --maxfail=1

for f in \
  examples/01_composition_research_analyst.py \
  examples/02_talker_reasoner_intake.py \
  examples/03_train_config_temperature.py \
  examples/04_evolutionary_best_of_n.py; do
    echo "== $f =="
    uv run python "$f" --offline
done

uv run --extra observers python demo.py --offline

echo "== apps/demos/agent_evolution/run.py =="
uv run python apps/demos/agent_evolution/run.py --offline --generations 2 --population 4 --seed 0

echo "✅ verify complete."
