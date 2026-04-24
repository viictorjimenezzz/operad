# 2 · 4 — Typed `Tool[Args, Result]`

**Addresses.** C4 (strong typing at the tool-call boundary).

**Depends on.** 1-1-restructure.

---

## Required reading

- `METAPROMPT.md`, `VISION.md` §3 (typed contracts everywhere).
- `operad/agents/reasoning/schemas.py` — existing `ToolCall`, `ToolResult`
  (both untyped: `args: dict[str, Any]`, `result: Any`).
- `operad/agents/reasoning/components/tool_user.py` — `Tool` Protocol +
  `ToolUser` leaf.
- `tests/test_tool_user.py` — existing coverage.
- `examples/sandbox_tooluser.py`, `examples/sandbox_add_tool.py`,
  `examples/sandbox_pool_demo.py` — all call sites of the dict-typed API.
- `operad/utils/hashing.py` (post-1-1) — `hash_schema` keys Pydantic
  classes for cassettes.

---

## Proposal

The current `ToolCall`/`ToolResult` pair use untyped dicts. A typed agent
framework has two downsides here:

- callers can't get IDE completion on tool args;
- `hash_schema(Tool.args)` is the same for every tool, so cassettes keyed
  on the call boundary can't distinguish two tools with identical names
  but different args shapes.

Parametrise both edge classes on the concrete `Args`/`Result` types.

### API

```python
# operad/agents/reasoning/schemas.py

from typing import Generic, TypeVar
from pydantic import BaseModel

Args = TypeVar("Args", bound=BaseModel)
Result = TypeVar("Result", bound=BaseModel)


class ToolCall(BaseModel, Generic[Args]):
    """A typed request to invoke `tool_name` with structured args."""
    tool_name: str
    args: Args

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolResult(BaseModel, Generic[Result]):
    """A typed tool return, success-biased."""
    ok: bool
    result: Result | None = None
    error: str = ""

    model_config = ConfigDict(arbitrary_types_allowed=True)
```

Delete the untyped fallback (`args: dict[str, Any]`, `result: Any`). No
backwards-compat shim.

### `Tool` protocol

Parametrise + expose declared schemas so the registry can key cassettes
on them:

```python
# operad/agents/reasoning/components/tool_user.py

class Tool(Protocol, Generic[Args, Result]):
    name: str
    args_schema: type[Args]
    result_schema: type[Result]

    async def call(self, args: Args) -> Result: ...
```

### `ToolUser`

```python
class ToolUser(Agent[ToolCall[Any], ToolResult[Any]]):
    input = ToolCall
    output = ToolResult
    ...

    async def forward(self, x: ToolCall[Any]) -> ToolResult[Any]:
        tool = self._tools.get(x.tool_name)
        if tool is None:
            return ToolResult(ok=False, error=f"unknown tool {x.tool_name!r}")
        try:
            # Validate args against the tool's declared schema before call.
            typed = tool.args_schema.model_validate(
                x.args if isinstance(x.args, dict) else x.args.model_dump()
            )
            raw = await tool.call(typed)
            typed_result = (
                raw if isinstance(raw, BaseModel)
                else tool.result_schema.model_validate(raw)
            )
            return ToolResult(ok=True, result=typed_result)
        except Exception as e:
            return ToolResult(ok=False, error=str(e))
```

The parameterisation at the `Agent[In, Out]` level stays `Any` (we can't
express heterogeneous per-call types in the class attribute contract).
That's fine: the contract is enforced per-call against `tool.args_schema`
in `forward`.

### Example registry

Typical user code after this PR:

```python
class AddArgs(BaseModel):
    a: int
    b: int

class AddResult(BaseModel):
    sum: int

class AddTool:
    name = "add"
    args_schema = AddArgs
    result_schema = AddResult
    async def call(self, args: AddArgs) -> AddResult:
        return AddResult(sum=args.a + args.b)

user = ToolUser(tools={"add": AddTool()})
await user.build().invoke(ToolCall[AddArgs](tool_name="add", args=AddArgs(a=1, b=2)))
```

---

## Required tests

`tests/test_typed_tool.py` (new; supersedes the dict-style checks in
`test_tool_user.py` that become obsolete):

1. **Typed args round-trip.** Construct `ToolCall[AddArgs](…, args=AddArgs(…))`;
   `ToolUser` forward returns `ToolResult[AddResult]` with a populated
   `result` of the declared type.
2. **Distinct schemas produce distinct hashes.** `hash_schema(
   AddTool.args_schema) != hash_schema(SearchTool.args_schema)` — document
   this property because the cassette key relies on it.
3. **Unknown-tool path.** `ToolCall(tool_name="missing", args=…)` yields
   `ToolResult(ok=False, error=...)`; `result` is `None`.
4. **Validation error path.** `ToolCall[AddArgs](tool_name="add", args=AddArgs(a=1, b=2))`
   where the tool's `call` raises; `ToolResult.ok` is `False`, `error`
   contains the exception message, `result` is `None`.
5. **`Agent[ToolCall[Any], ToolResult[Any]]` builds.** `ToolUser(...).build()`
   succeeds without type errors.

Existing `tests/test_tool_user.py` — update or retire; the assertions on
`args: dict` move to the typed shape.

---

## Scope

**New files.**
- `tests/test_typed_tool.py`.

**Edited files.**
- `operad/agents/reasoning/schemas.py` — parametrise `ToolCall`,
  `ToolResult`.
- `operad/agents/reasoning/components/tool_user.py` — parametrise `Tool`,
  per-call validation + typed return wrapping in `forward`.
- `operad/agents/reasoning/components/__init__.py` — re-export updated
  symbols (no change in names).
- `tests/test_tool_user.py` — update expectations for the typed shape;
  remove tests that no longer apply.
- `examples/sandbox_tooluser.py`, `examples/sandbox_add_tool.py`,
  `examples/sandbox_pool_demo.py` — migrate call sites to the typed API.

**Must NOT touch.**
- Other reasoning components (`reasoner.py`, `actor.py`, `critic.py`, etc).
- Other `agents/<domain>/`.
- `operad/core/` entirely.
- `operad/runtime/`, `operad/metrics/`.

---

## Acceptance

- `uv run pytest tests/test_typed_tool.py tests/test_tool_user.py` green.
- `uv run pytest tests/` green (full suite).
- `uv run python examples/sandbox_tooluser.py` runs offline.
- `uv run python examples/sandbox_add_tool.py` runs offline.
- `uv run python examples/sandbox_pool_demo.py` runs offline.

---

## Watch-outs

- **Generic base models in Pydantic.** `BaseModel, Generic[Args]` works
  but serialisation needs either a concrete parameterisation at the call
  site or `model_config = ConfigDict(arbitrary_types_allowed=True)`.
  Prefer the former — always construct `ToolCall[AddArgs](...)` from
  user code.
- **Structured-output with `Any`.** Strands' structured-output hook may
  reject `Any`-valued fields. `ToolUser` overrides `forward`, so it
  never hits strands' structured-output — no issue there. If a caller
  subclasses `ToolUser` with a default-forward leaf, they must
  parametrise at the class level.
- **Cassette keys.** `hash_schema(ToolCall[AddArgs]) !=
  hash_schema(ToolCall[SearchArgs])` is the load-bearing property for
  cassette distinctness. `hash_schema` already walks nested Pydantic
  models, so this holds without extra plumbing — document it in the
  test body so a future refactor doesn't accidentally cache-collapse.
- **Example duplication.** `Example[ToolCall, ToolResult](...)` in the
  class attributes no longer type-checks cleanly under the generic. Use
  `Example[ToolCall[AddArgs], ToolResult[AddResult]](...)` if you keep
  the class-level example, or move it to the constructor's `examples=`
  slot. Lightweight fix: replace the class-level `examples` tuple with
  a docstring-only example to dodge the generic-parameter wart.
- **No new public names.** The API surface at `from operad.agents.reasoning
  import ...` stays the same — `ToolCall`, `ToolResult`, `Tool`,
  `ToolUser`. Only the type parameters are new.
