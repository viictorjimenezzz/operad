# operad.configs — YAML loader

A thin deserializer that bridges YAML/JSON files to the Python API.
Drives the `operad` CLI (`run`, `trace`, `graph`). Not a separate
language; not a DSL; nothing here lives that you couldn't write in
Python directly.

---

## Files

| File         | Role                                                                              |
| ------------ | --------------------------------------------------------------------------------- |
| `loader.py`  | `load(path)`, `instantiate(...)`, `apply_runtime(...)`, `ConfigError`.            |
| `schema.py`  | `RunConfig`, `RuntimeSpec`, `SlotSpec`, `OverrideSpec` Pydantic schemas.          |

## Public API

```python
from operad.configs import (
    load, instantiate, apply_runtime, ConfigError,
    RunConfig, RuntimeSpec, SlotSpec, OverrideSpec,
)
```

## Smallest meaningful YAML

```yaml
# examples/config-react.yaml
agent: operad.agents.reasoning.react.ReAct
config:
  backend: llamacpp
  host: 127.0.0.1:8080
  model: qwen2.5-7b-instruct
  temperature: 0.3
runtime:
  slots:
    - backend: llamacpp
      host: 127.0.0.1:8080
      limit: 8
overrides:
  stage_0.role: "Be skeptical of every claim."
```

```bash
uv run operad run   examples/config-react.yaml --input examples/task.json
uv run operad trace examples/config-react.yaml
uv run operad graph examples/config-react.yaml --format json
```

## Programmatic flow

```python
from operad.configs import load, instantiate, apply_runtime

run_config = load("examples/config-react.yaml")    # parse YAML -> RunConfig
agent      = instantiate(run_config)               # Build Agent from agent FQN + config
apply_runtime(run_config.runtime)                  # set_limit() per slot spec
await agent.abuild()
```

## How to extend

| What                       | Where                                                                          |
| -------------------------- | ------------------------------------------------------------------------------ |
| A new top-level config field | Add to `RunConfig` in `schema.py`; thread through `instantiate()`.            |
| A new override target      | Extend `OverrideSpec`; `apply_runtime()` reads it.                             |
| A new runtime knob         | Add to `RuntimeSpec`; `apply_runtime()` calls into `runtime/slots`.            |

## Related

- [`../../README.md#cli--yaml`](../../README.md#cli--yaml) — user-facing CLI surface.
- [`../core/config.py`](../core/config.py) — what the YAML's `config:`
  block deserializes into.
- [`../runtime/slots.py`](../runtime/slots.py) — what the `runtime.slots:`
  block configures.
- Top-level [`../../INVENTORY.md`](../../INVENTORY.md) §18 — CLI catalog.
