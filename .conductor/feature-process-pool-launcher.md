# Feature · Process-pool launcher for ToolUser

**Addresses.** E-15 (ISSUES.md) + `TODO_PROCESS_POOL_LAUNCHER` in
`missing.py`.

`SandboxedTool` (current) spawns a fresh Python interpreter per call
(~100 ms cold-start). For any real agent-with-tools workload that
dispatches many tool calls, this is prohibitive. Add a reusable worker
pool that amortises the spawn cost.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-15.
- `operad/runtime/launchers/sandbox.py`, `sandbox_worker.py`.
- VISION §7 "launchers/".

---

## Proposal

### `PooledSandboxedTool`

A drop-in alternative to `SandboxedTool` that holds a pool of
long-lived workers.

```python
# operad/runtime/launchers/pool.py (new)

class SandboxPool:
    """A pool of long-lived sandbox worker subprocesses.

    Workers speak a tiny JSON-lines request/response protocol on
    stdin/stdout. The pool multiplexes tool calls across `size` workers;
    each worker can host multiple tool classes and dispatches by name.
    """

    def __init__(
        self,
        *,
        size: int = 4,
        timeout_seconds: float = 10.0,
        memory_mb: int | None = 256,
    ) -> None: ...

    async def start(self) -> None: ...
    async def close(self) -> None: ...

    async def call(self, tool_qualified: str, args: dict) -> Any:
        """Dispatch a tool call to an available worker.

        `tool_qualified` is "module:Class" (same format as the
        single-shot launcher's `--tool=` flag).
        """

    async def __aenter__(self) -> "SandboxPool": ...
    async def __aexit__(self, *exc) -> None: ...


class PooledSandboxedTool:
    """Tool wrapper that dispatches through a shared `SandboxPool`."""

    def __init__(self, tool, *, pool: SandboxPool) -> None: ...

    @property
    def name(self) -> str: ...

    async def call(self, args: dict) -> Any:
        return await self.pool.call(
            f"{type(self.tool).__module__}:{type(self.tool).__name__}",
            args,
        )
```

### Protocol

Worker reads JSON lines from stdin, each:

```json
{"id": "uuid", "tool": "module:Class", "args": {...}}
```

Writes JSON lines to stdout:

```json
{"id": "uuid", "ok": true, "result": ...}
{"id": "uuid", "ok": false, "error": "..."}
```

Worker is a long-lived loop, not a single-shot script. It imports
tools lazily — first call for `module:Class` imports and caches.

Update `operad/runtime/launchers/sandbox_worker.py` to run in pool
mode when invoked with `--pool` flag. Keep single-shot mode for
backwards compatibility with `SandboxedTool`.

### Usage

```python
async with SandboxPool(size=4) as pool:
    tool_user = ToolUser(tools={
        "search": PooledSandboxedTool(search_tool, pool=pool),
        "math":   PooledSandboxedTool(math_tool, pool=pool),
    })
    await tool_user(ToolCall(tool_name="search", args={"q": "cats"}))
```

---

## Required tests

`tests/test_sandbox_pool.py` (offline; mocks the subprocess layer):

1. `SandboxPool(size=2)` spawns exactly 2 worker processes.
2. 10 concurrent `call()` invocations complete without spawning more
   than 2 workers.
3. `pool.close()` terminates all workers; subsequent `call()` raises.
4. Worker timeout on a single call kills that worker but leaves
   others intact.

`tests/integration/test_sandbox_pool.py` (opt-in, real subprocess):

1. Real round-trip: pool size 2, serve a trivial add-tool, 100 calls
   complete in well under 100ms × 100 (cold start amortised).

---

## Scope

- New: `operad/runtime/launchers/pool.py`.
- Edit: `operad/runtime/launchers/sandbox_worker.py` (add pool mode).
- Edit: `operad/runtime/launchers/__init__.py` re-exports.
- New: `examples/sandbox_pool_demo.py`.
- New: `tests/test_sandbox_pool.py`, `tests/integration/test_sandbox_pool.py`.

Do NOT:
- Replace `SandboxedTool`. Keep both — the single-shot is simpler
  for one-off calls and needs no lifecycle management.
- Share tool state across workers. Each worker is isolated.
- Auto-restart crashed workers in v1. If a worker dies, drop it
  from the pool and raise on the pending call. Restart logic is a
  follow-up.

---

## Acceptance

- `uv run pytest tests/` green (offline with mocks).
- `OPERAD_INTEGRATION=sandbox uv run pytest tests/integration/test_sandbox_pool.py`
  shows cold-start amortisation.
- `examples/sandbox_pool_demo.py` runs a tiny tool under a 2-worker
  pool.

---

## Watch-outs

- POSIX-only (like single-shot sandbox). Windows: bail at pool
  construction.
- Process lifecycle: use `asyncio.create_subprocess_exec`; carefully
  drain stdout in a reader task per worker to avoid deadlock.
- Message correlation: the worker MUST echo `id` back; the pool
  matches responses to pending futures by `id`.
- Careful with `resource.setrlimit` in pool mode — limits apply to
  the whole worker, not per-call. Document this.
