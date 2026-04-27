# 2-1 — operad leaf classes (one per YAML)

**Batch:** 2 · **Parallelizable with:** 2-2, 2-3, 2-4 · **Depends on:** 1-2, 1-3

You are turning each in-scope YAML into a typed operad `Agent` subclass.
The classes are thin — they pin `input` and `output` types; the loader
populates `role / task / rules / examples / config` at load time.

## Goal

Ship one operad leaf class per in-scope YAML, in `apps_uthereal/leaves/`.
Each class is a 5-to-15-line subclass of `operad.Agent[InputSchema,
OutputSchema]` that pins the vendored schemas from task 1-2. Provide a
small registry mapping YAML paths → leaf classes for the runner (3-1)
to consume.

## Files to create

| Path | YAML it pairs with |
|---|---|
| `apps_uthereal/leaves/context_safeguard.py` | `input/agents/agent_context_safeguard.yaml` |
| `apps_uthereal/leaves/safeguard_talker.py` | `input/agents/agent_safeguard_talker.yaml` |
| `apps_uthereal/leaves/reasoner.py` | `reasoner/agents/agent_reasoner.yaml` |
| `apps_uthereal/leaves/conversational_talker.py` | `reasoner/agents/agent_conversational_talker.yaml` |
| `apps_uthereal/leaves/rule_classifier.py` | `retrieval/agents/agent_rule_classifier.yaml` |
| `apps_uthereal/leaves/retrieval_orchestrator.py` | `retrieval/agents/agent_retrieval_orchestrator.yaml` |
| `apps_uthereal/leaves/evidence_planner.py` | `retrieval/agents/agent_evidence_planner.yaml` |
| `apps_uthereal/leaves/fact_filter.py` | `retrieval/agents/agent_fact_filter.yaml` |
| `apps_uthereal/leaves/rag_talker.py` | `retrieval/agents/agent_talker.yaml` |
| `apps_uthereal/leaves/registry.py` | mapping table + helper |
| `apps_uthereal/tests/test_leaves.py` | per-leaf smoke tests against vendored YAMLs |

## API surface (every leaf follows this exact shape)

```python
# apps_uthereal/leaves/context_safeguard.py
"""Owner: 2-1-operad-leaves."""
from __future__ import annotations
from operad import Agent
from apps_uthereal.schemas.safeguard import (
    ContextSafeguardInput,    # vendored typed input
    ContextSafeguardResponse, # vendored typed output
)


class ContextSafeguardLeaf(Agent[ContextSafeguardInput, ContextSafeguardResponse]):
    """Routes user messages as in-scope / off-topic / exit.

    role / task / rules / examples / config are populated by `load_yaml`;
    this class is structural only.
    """

    input = ContextSafeguardInput
    output = ContextSafeguardResponse
```

The registry:

```python
# apps_uthereal/leaves/registry.py
from __future__ import annotations
from pathlib import Path
from operad import Agent

from apps_uthereal.leaves.context_safeguard import ContextSafeguardLeaf
from apps_uthereal.leaves.safeguard_talker import SafeguardTalkerLeaf
# ... import all nine

# YAML paths are relative to the selfserve root the user provides at runtime.
# The runner resolves absolute paths by `selfserve_root / RELATIVE_PATH`.
LEAF_REGISTRY: dict[str, type[Agent]] = {
    "input/agents/agent_context_safeguard.yaml":   ContextSafeguardLeaf,
    "input/agents/agent_safeguard_talker.yaml":    SafeguardTalkerLeaf,
    "reasoner/agents/agent_reasoner.yaml":         ReasonerLeaf,
    "reasoner/agents/agent_conversational_talker.yaml": ConversationalTalkerLeaf,
    "retrieval/agents/agent_rule_classifier.yaml": RuleClassifierLeaf,
    "retrieval/agents/agent_retrieval_orchestrator.yaml": RetrievalOrchestratorLeaf,
    "retrieval/agents/agent_evidence_planner.yaml": EvidencePlannerLeaf,
    "retrieval/agents/agent_fact_filter.yaml":     FactFilterLeaf,
    "retrieval/agents/agent_talker.yaml":          RAGTalkerLeaf,
}

def load_all_leaves(
    selfserve_root: Path,
    *,
    config_overrides: dict | None = None,
) -> dict[str, Agent]:
    """For each YAML in LEAF_REGISTRY, return {step_name: loaded_leaf}.

    `step_name` is derived from the relative YAML path (e.g.
    `"context_safeguard"` from `agent_context_safeguard.yaml`). Use
    these step names consistently with `runner.get_submodule(...)` and
    `TraceFrame.step_name` (C10).
    """
```

The step-name mapping (frozen — do not change without a contract amendment):

| YAML | step_name |
|---|---|
| `agent_context_safeguard.yaml` | `context_safeguard` |
| `agent_safeguard_talker.yaml` | `safeguard_talker` |
| `agent_reasoner.yaml` | `reasoner` |
| `agent_conversational_talker.yaml` | `conv_talker` |
| `agent_rule_classifier.yaml` | `rule_classifier` |
| `agent_retrieval_orchestrator.yaml` | `retrieval_orchestrator` |
| `agent_evidence_planner.yaml` | `evidence_planner` |
| `agent_fact_filter.yaml` | `fact_filter` |
| `agent_talker.yaml` | `rag_talker` |

## Implementation notes

- **No prompt content in the class body.** Everything that is text
  (`role`, `task`, `rules`, `examples`) comes from YAML. The class
  exists purely to pin the typed boundaries and to expose a stable
  Python identity for `runner.get_submodule(...)` lookups.
- **`config = None` is wrong here.** Each leaf has a real
  `Configuration` populated by the loader. Don't shadow it.
- **`Agent.__init__` signature.** Operad agents accept `config`, `input`,
  `output` plus `role`, `task`, `rules`, `examples`, `default_sampling`
  as kwargs. The loader passes those positionally; the class just
  declares `input` and `output`.
- **The `examples` tuple.** Operad expects `tuple[Example[In, Out], ...]`.
  The loader (1-3) produces them. If your leaf class adds class-level
  `examples = (...)` defaults, the loader's overrides win — that's fine.
  Prefer empty class-level defaults (`examples: tuple = ()`) so the
  class is unambiguously YAML-driven.
- **Cassette fingerprints.** `hash_content` on each loaded leaf must be
  stable across processes. This is a property of the loader and of the
  leaf's declared schema; you don't need to do anything special, but
  test it.

## Acceptance criteria

- [ ] All 9 leaf classes exist and import cleanly.
- [ ] For each YAML in `LEAF_REGISTRY`,
      `load_yaml(yaml_path, leaf_cls).abuild()` succeeds (offline; no
      LLM call needed at build time — operad's `abuild` only traces).
- [ ] After load, `leaf.role`, `leaf.task`, `leaf.rules` are non-empty.
- [ ] `load_all_leaves(selfserve_root)` returns a dict keyed by the
      frozen step_name mapping above; values are built agents.
- [ ] Two consecutive loads of the same YAML produce leaves with equal
      `hash_content`.
- [ ] No imports from `uthereal_*`.
- [ ] No prompt text inlined in any leaf class body.

## Tests

- For each leaf class:
  - `test_<leaf_name>_class_pins_correct_schemas` — assert `Leaf.input is <In>`, `Leaf.output is <Out>`.
  - `test_<leaf_name>_loads_from_vendored_yaml` — invoke `load_yaml` on
    a fixture YAML (vendor a copy under `tests/fixtures/yamls/`) and
    assert `role/task/rules` are populated.
- `test_load_all_leaves_returns_all_step_names` — assert exact set of
  keys in result.
- `test_load_all_leaves_step_name_matches_runner_get_submodule_lookup`
  — this test fixture exercises that the runner (whose dotted path
  matches the registry's step_name) can resolve the leaf via
  `getattr(runner, step_name)`. (You don't depend on the runner; you
  test that step_names follow valid Python identifier rules.)
- `test_hash_content_stable_across_loads`.

## Vendoring the YAMLs for tests

Copy each in-scope YAML from selfserve into
`apps/uthereal/tests/fixtures/yamls/<step_name>.yaml`. These are
checked-in test fixtures. The runner (3-1) will be configured to read
from a `--selfserve-root` argument at runtime; your tests use the
fixtures.

## References

- `operad/agents/safeguard/components/context.py` — full leaf with
  prompt content. Your classes are just the structural shell of this.
- `operad/agents/memory/components/beliefs.py` — example of a leaf with
  rich structured output.
- `apps_uthereal/leaves/_common.py` (1-3) — `load_yaml` you use here.

## Notes

(Append discoveries here as you implement. Particularly: any YAMLs
whose `input:` block doesn't cleanly map to a Pydantic schema field,
and how you resolved that.)
