# 1-2 Operad core: inverted-graph export (`to_io_graph`)

## Scope

You are adding a single, additive feature to operad core: a new
graph-export function that emits the dashboard's preferred view of
an `AgentGraph` — **input/output types as nodes, agents as edges**.

This is the only piece of operad-side work required for the agent
view rewrite. Don't touch any other operad surface.

### You own

- `operad/core/graph.py` — add `to_io_graph()` and the supporting
  type-walker. Keep `to_mermaid` and `to_json` untouched.
- `operad/core/fields.py` — extend if you need a richer field
  walker (e.g. one that handles nested Pydantic models, enums,
  literals). Don't break `is_system_field`.
- `tests/core/test_graph_inversion.py` (new) — exhaustive unit
  tests for the new function.
- `INVENTORY.md` — add a one-paragraph entry under §4 describing
  `to_io_graph`. Brief, factual.

### Out of scope

- Anything in `apps/`. The dashboard endpoint that consumes this
  function is owned by stream 1-3; you only have to ship the
  function and its contract.

---

## Vision

The current `AgentGraph` Mermaid render shows agents as nodes with
type-pair labels — a fine engineering view but a poor *reasoning*
view. What users actually want to see is data flow: a `Question`
arrives, gets transformed into a `Reflection` by some agent, then
into an `Answer` by another. Types are the objects of the
category; agents are the morphisms.

Surfacing this view server-side (rather than computing it
client-side) keeps the renderer-agnostic shape correct and lets
non-dashboard consumers (CLI, freeze artifacts, future viewers)
reuse it.

---

## Contract

```python
# operad/core/graph.py

def to_io_graph(graph: AgentGraph) -> dict[str, Any]:
    """Inverted view: input/output types as nodes, agents as edges.

    Each leaf in the AgentGraph contributes one edge from its
    input-type node to its output-type node. Type nodes are
    deduplicated by qualified name. Composite nodes do not get
    their own edge or node — their children carry the structure —
    but their path is surfaced on every descendant edge as
    ``composite_path`` so the UI can group edges by parent.

    Returns a dict with this shape:

    .. code-block:: python

        {
          "root": "<root agent class name>",
          "nodes": [
            {
              "key":         "<module.qualname>",  # stable id
              "name":        "<class __name__>",
              "fields": [
                {"name": "...",
                 "type": "...",                    # Python type name, best-effort
                 "description": "...",
                 "system": True | False},
                ...
              ]
            },
            ...
          ],
          "edges": [
            {
              "agent_path":      "Root.stage_0.branch_1",
              "class_name":      "<runtime class>",
              "kind":            "leaf",
              "from":            "<input qualified name>",
              "to":              "<output qualified name>",
              "composite_path":  "Root.stage_0" | None,  # nearest composite ancestor, if any
            },
            ...
          ]
        }
    """
```

### Field walker

`fields` come from a Pydantic walker that you should ship as a
small helper inside `graph.py` (or extend `core/fields.py`):

- For each entry in `model_cls.model_fields.items()`:
  - `name` = field name
  - `type` = best-effort `__name__` of `info.annotation`. For
    `Optional[X]`, `list[X]`, `Literal[...]`, etc., emit a clean
    short string (e.g. `Optional[Reflection]`, `list[str]`,
    `Literal['a','b']`). Don't ship `repr()` garbage.
  - `description` = `info.description or ""`.
  - `system` = `is_system_field(info)` (already exists in
    `operad/core/fields.py`).
- Non-Pydantic types (rare; e.g. plain dataclass) emit
  `{"name": <type.__name__>, "fields": []}`. Don't crash.

### Composite handling

Walk `graph.nodes` once to identify composites (`kind ==
"composite"`). For each leaf edge, set `composite_path` to the
nearest ancestor in the path string (the longest prefix that
matches a composite path). If the leaf's parent is the root, set
to `None`.

Don't try to be clever about Switch / Parallel — just emit the
edges that the existing `AgentGraph.edges` would imply. The
dashboard handles fan-out visualisation.

---

## Tests

`tests/core/test_graph_inversion.py` should cover, at minimum:

- A pure leaf agent → one edge, two type nodes.
- A `Pipeline(a, b, c)` → three edges, four type nodes (assuming
  three distinct In/Out types). If two stages share a type, the
  node is deduplicated.
- A `Parallel({"x": leaf_a, "y": leaf_b})` → two edges from the
  same input-type node to two different output-type nodes.
- A `Switch(router=…, branches={"in": leaf_in, "out": leaf_out})`
  → router edge + branch edges, all sharing the input type node.
- An agent whose `In` has a `system`-flagged field — the field
  appears with `system=True`.
- An agent whose `In` has fields with no description — they
  appear with `description=""`.
- Round-trip: `to_io_graph(graph)` is JSON-serialisable.

Use the offline test fixtures in `tests/conftest.py` and
`FakeLeaf` rather than touching real models.

---

## Implementation pointers

- Read `operad/core/build.py` (lines 170–210) for the `AgentGraph`,
  `Node`, `Edge` shape.
- Read `operad/core/graph.py` end-to-end before writing — your
  function is a sibling of `to_json`, it should slot in cleanly.
- Read `operad/core/fields.py` for `is_system_field` /
  `split_fields`.
- The "best-effort short type name" is the only mildly tricky bit.
  Look at `typing.get_origin` / `get_args` to decompose generics.
  Be defensive: if the resolution fails, fall back to
  `repr(annotation)` rather than raising.
- Composites have `kind == "composite"` on the `Node`; their input
  and output types are still recorded but they don't *invoke*. We
  still want them attributed to descendants via `composite_path`.

---

## Be creative

- The contract above lists fields the UI definitely needs; if you
  spot something else worth surfacing (e.g. `is_required` per
  field, default values, enum vocabulary), include it. Add it to
  the docstring and to the test.
- This function will be hashed and shipped to clients on every
  request. If the walker is expensive, memoise per `(graph_id,
  type)`. Don't over-engineer; just be aware.

---

## Verification

```bash
uv run pytest tests/core/test_graph_inversion.py -v
uv run pytest tests/                                      # full offline suite stays green
uv run python -c "import operad; from operad.core.graph import to_io_graph; print(to_io_graph)"
```
