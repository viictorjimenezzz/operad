# Phase 2 · Stream E — New reasoning leaves: Retriever, Reflector, Router, ToolUser

**Goal.** Grow the leaf vocabulary with the four primitives named in
VISION §7. `Router` is the delicate one; read its section carefully
and coordinate with Stream A on the sentinel semantics.

**Owner:** one agent.
**Depends on.** Stream A (error taxonomy, sentinel proxy behaviour).
**Required by.** Streams G, H, I (domains compose these).
**Addresses:** C-1.

---

## Scope

### Files you will create
- `operad/agents/reasoning/components/retriever.py`
- `operad/agents/reasoning/components/reflector.py`
- `operad/agents/reasoning/components/router.py`
- `operad/agents/reasoning/components/tool_user.py`
- `operad/agents/reasoning/switch.py` — composite paired with Router.
- `tests/test_retriever.py`, `test_reflector.py`, `test_router.py`,
  `test_tool_user.py`, `test_switch.py`.
- `examples/router_switch.py`.

### Files you will edit
- `operad/agents/reasoning/components/__init__.py` — re-exports.
- `operad/agents/reasoning/__init__.py` — re-exports.
- `operad/agents/__init__.py` — re-exports.
- `operad/__init__.py` — re-exports.

### Files to leave alone
- Existing leaves (Reasoner, Actor, Extractor, Evaluator, Classifier,
  Planner, Critic). Seeding their `examples=` lives in Stream K.

---

## Design direction

### `Retriever`

Leaf with a pluggable async `lookup` callable, so it stays
offline-testable. Not an LLM call by default — override `forward`.

```python
class Hit(BaseModel): ...
class Query(BaseModel): ...
class Hits(BaseModel): items: list[Hit]

class Retriever(Agent[Query, Hits]):
    role = "You retrieve the most relevant items for a query."
    task = "Return the hits sorted by relevance, with scores."
    rules = ("Prefer precision over recall.",
             "Discard hits below the relevance threshold.")

    def __init__(self, *, lookup: Callable[[Query], Awaitable[list[Hit]]],
                 input: type = Query, output: type = Hits) -> None:
        super().__init__(config=None, input=input, output=output)
        self._lookup = lookup

    async def forward(self, x: Query) -> Hits:
        items = await self._lookup(x)
        return Hits(items=items)
```

Because `forward` is overridden, `_is_default_forward` returns False,
so `_validate` does NOT require `config`, and `_init_strands` skips it.
Confirm this by reading `operad/core/build.py`.

### `Reflector`

Standard default-forward leaf:

```python
class ReflectionInput(BaseModel):
    original_request: str
    candidate_answer: str

class Reflection(BaseModel):
    needs_revision: bool
    deficiencies: list[str]
    suggested_revision: str

class Reflector(Agent[ReflectionInput, Reflection]):
    role = "You are a careful self-reviewer."
    task = "Inspect the prior answer for errors and propose a revision."
    rules = (
        "Cite specific deficiencies.",
        "If no deficiency exists, set needs_revision=False and leave suggested_revision empty.",
    )
```

### `Router` + `Switch` (the delicate one)

**`Router` is a leaf.** It emits a typed `Choice` with a
`Literal[...]` label:

```python
class RouteInput(BaseModel):
    query: str
    # plus whatever else the specific use-case needs

class Choice[T](BaseModel):
    label: T
    reasoning: str = ""

class Router(Agent[RouteInput, Choice[str]]):
    role = "You route requests to the correct handler."
    task = "Pick exactly one label from the allowed set."
```

**`Switch` is a composite.** It owns a `Router` leaf and a mapping
`{label: branch_agent}`. Its `forward`:

```python
async def forward(self, x: In) -> Out:
    # Tracing: visit every branch so build() covers all edges
    tracer = _TRACER.get()
    if tracer is not None:
        # invoke router, then invoke each branch once with x
        _ = await self._router(x)
        for branch in self._branches.values():
            await branch(x)
        return next(iter(self._branches.values())).output.model_construct()

    # Runtime: route by router's choice
    choice = await self._router(x)
    branch = self._branches.get(choice.label)
    if branch is None:
        raise BuildError("router_miss", f"no branch for {choice.label!r}")
    return await branch(x)
```

This is the one composite that legitimately needs tracer awareness.
Coordinate with Stream A so the sentinel proxy exempts Switch's
router-output read (it's output of a previous child, not input-field
branching). If the simplest path is "only intercept reads on the
`forward` sentinel, not on child return values," confirm that with
Stream A before merging.

Add `BuildReason("router_miss", ...)` if Stream A hasn't already.

### `ToolUser`

Leaf dispatching to a typed tool registry. The tool-*selection* is out
of scope for v1 — that's a future composed pattern.

```python
class ToolCall(BaseModel):
    tool_name: str
    args: dict[str, Any]

class ToolResult(BaseModel):
    ok: bool
    result: Any = None
    error: str = ""

class Tool(Protocol):
    name: str
    async def call(self, args: dict[str, Any]) -> Any: ...

class ToolUser(Agent[ToolCall, ToolResult]):
    role = "You dispatch typed tool calls."
    task = "Invoke the named tool with the given arguments and return the result."

    def __init__(self, *, tools: dict[str, Tool],
                 input: type = ToolCall, output: type = ToolResult) -> None:
        super().__init__(config=None, input=input, output=output)
        self._tools = tools

    async def forward(self, x: ToolCall) -> ToolResult:
        tool = self._tools.get(x.tool_name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool {x.tool_name!r}")
        try:
            return ToolResult(ok=True, result=await tool.call(x.args))
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
```

Override-forward, no config required, no strands init.

---

## Tests

- `Retriever` with a fake async `lookup` returns expected hits.
- `Reflector` with `FakeLeaf`-style canned output produces a typed
  `Reflection`.
- `Router` builds and is callable in isolation.
- `Switch`'s build traces every branch; runtime dispatch picks the
  correct branch based on the router's output; unknown label raises.
- `ToolUser` dispatches by name; unknown tool returns
  `ToolResult(ok=False)`; tool raising returns
  `ToolResult(ok=False, error=...)`.

---

## Acceptance

- `uv run pytest tests/` green.
- `examples/router_switch.py` demonstrates a two-branch Switch against
  a local model.

---

## Watch-outs

- Do NOT put payload-field branching inside `Switch.forward` without
  the tracer guard.
- `Choice[Literal[...]]` parametrisation in Pydantic v2 can be fiddly;
  test early.
- `Router`'s output type must be narrow — the set of allowable labels
  is part of the type, not a string.
- Don't invent a plugin discovery system for `ToolUser.tools`. A dict
  passed at construction is enough.
- Every new leaf ships with at least one `Example(...)` in `examples=`.
  This finally uses the feature.
