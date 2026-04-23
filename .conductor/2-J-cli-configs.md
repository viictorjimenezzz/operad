# Phase 2 · Stream J — CLI & YAML configs

**Goal.** Ship `operad run config.yaml` and `operad trace config.yaml`
so end-users can run a graph without writing Python.

**Owner.** One agent.
**Depends on.** Nothing hard; plays well with Stream K (examples).
**Addresses:** C-7.

---

## Scope

### Files you will create
- `operad/configs/__init__.py`
- `operad/configs/schema.py` — Pydantic config schema.
- `operad/configs/loader.py` — YAML → schema → instantiated Agent.
- `operad/cli.py` — `argparse`-based entrypoint (avoid adding a new
  CLI dep).
- `examples/config-react.yaml`
- `examples/task.json`
- `tests/test_configs.py`, `tests/test_cli.py`.

### Files you will edit
- `pyproject.toml` — add `[project.scripts]` entry:
  `operad = "operad.cli:main"` and add `pyyaml` to base deps.
- `README.md` — add a short "Run from YAML" section at the bottom.

### Files to leave alone
- Everything not listed above.

---

## Design direction

### YAML shape

```yaml
agent: operad.agents.ReAct         # fully-qualified importable class
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
  role: "You are a tireless research assistant."
  task: "..."
  rules:
    - "Stay under 200 words."
```

### Pydantic schema

```python
class SlotSpec(BaseModel):
    backend: Backend
    host: str | None = None
    limit: int

class RuntimeSpec(BaseModel):
    slots: list[SlotSpec] = []

class OverrideSpec(BaseModel):
    role: str | None = None
    task: str | None = None
    rules: list[str] | None = None

class RunConfig(BaseModel):
    agent: str                     # importable path
    config: Configuration
    runtime: RuntimeSpec = RuntimeSpec()
    overrides: OverrideSpec = OverrideSpec()
```

### Loader

```python
def load(path: Path) -> RunConfig: ...

def instantiate(rc: RunConfig) -> Agent[Any, Any]:
    cls = _import_by_path(rc.agent)          # operad.agents.ReAct
    kwargs = {"config": rc.config}
    if rc.overrides.role is not None: kwargs["role"] = rc.overrides.role
    ...
    return cls(**kwargs)

def apply_runtime(rc: RunConfig) -> None:
    for s in rc.runtime.slots:
        set_limit(backend=s.backend, host=s.host, limit=s.limit)
```

### CLI subcommands

```
operad run   <config.yaml> --input <input.json>    # print Out as JSON
operad trace <config.yaml>                         # print Mermaid
operad graph <config.yaml> --format json           # print AgentGraph as JSON
```

Parse input JSON into the agent's `input` Pydantic model; if the file
doesn't validate, exit with a clear error.

---

## Tests

- `load` parses a known-good YAML.
- `instantiate` returns an Agent of the expected class.
- `operad trace` on a YAML pointing to a pipeline prints non-empty
  Mermaid.
- Bad YAML → friendly error with exit code 2.

---

## Acceptance

- `uv run operad run examples/config-react.yaml --input examples/task.json`
  works against a local model.
- `uv run operad trace examples/config-react.yaml` prints Mermaid.

---

## Watch-outs

- Do NOT invent a DSL. YAML → Pydantic → class instantiation is enough.
- Do NOT support arbitrary Pipeline composition in YAML for v1. A named
  Agent class with optional overrides is the whole surface.
- Keep `pyproject.toml` scripts entry exactly one line.
- Friendly errors: a missing file, a bad class path, or a bad input
  schema should all print a single-line message and exit non-zero.
- Don't import anything heavy at `operad/cli.py` top-level; the CLI
  should start fast.
