# Feature · Sandbox-per-tool launcher (simple first cut)

A minimal subprocess-based sandbox that wraps a `ToolUser` tool's
execution in a bounded child process with timeout and memory caps.
Start simple; this is the "launchers/process" hint in VISION §7
reduced to its essential shape.

**Covers Part-3 item.** #10 (sandbox-per-tool), starting simple per
feedback.

---

## Required reading

`METAPROMPT.md`, `ISSUES.md`, `VISION.md` §7 (`launchers/`), and:
- `.conductor/2-E-reasoning-leaves.md` — `ToolUser` and the `Tool`
  protocol. Hard dependency.

---

## Proposal sketch

### Shape

```python
class SandboxedTool:
    """Wraps a `Tool` so its `.call()` runs in a subprocess.

    Communication is JSON over stdin/stdout. Failures (non-zero
    exit, timeout, OOM) surface as ToolResult(ok=False, error=...).
    The inner tool runs in a fresh Python interpreter importing only
    its own module — no shared state with the host process.
    """

    def __init__(
        self,
        tool: Tool,
        *,
        timeout_seconds: float = 10.0,
        memory_mb: int | None = 256,
    ) -> None: ...

    @property
    def name(self) -> str:
        return self.tool.name

    async def call(self, args: dict[str, Any]) -> Any: ...
```

`SandboxedTool(inner)` is a drop-in for `Tool` — satisfies the same
Protocol. Users wrap tools they don't trust:

```python
ToolUser(tools={
    "search": search_tool,                    # trusted in-process
    "shell":  SandboxedTool(shell_tool),       # sandboxed
})
```

### Implementation shape

```python
async def call(self, args):
    cmd = [sys.executable, "-m", "operad.runtime.launchers.sandbox_worker",
           f"--tool={self.tool.__module__}:{self.tool.__class__.__name__}"]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
        preexec_fn=_set_limits(self.memory_mb) if self.memory_mb else None,
    )
    payload = json.dumps(args).encode()
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(payload), timeout=self.timeout_seconds
        )
    except TimeoutError:
        proc.kill()
        raise RuntimeError(f"sandbox timeout after {self.timeout_seconds}s")
    if proc.returncode != 0:
        raise RuntimeError(f"sandbox exited {proc.returncode}: {stderr.decode()}")
    return json.loads(stdout.decode())
```

### Worker

`operad/runtime/launchers/sandbox_worker.py` is a tiny script:

1. Parse `--tool=module:Class`.
2. Import and instantiate the tool.
3. Read JSON args from stdin, call `await tool.call(args)`, write
   result JSON to stdout.
4. Exit 0 on success, 1 with error on failure.

---

## Research directions

- **`resource.setrlimit` on macOS/Linux.** `RLIMIT_AS` bounds
  address space on Linux; macOS honours it but behaves slightly
  differently. Document the platform caveats. On Windows, bail
  (macOS and Linux only for v1).
- **Process pool.** Spawning a fresh Python interpreter per call
  costs ~40–100 ms. A pool of reusable workers is a clear v2; stay
  out of scope for v1.
- **Serialisation limits.** JSON over stdin/stdout works for simple
  types. Large binary payloads (images) should not go through this
  path — document the limitation.
- **Signal handling.** On timeout, `proc.kill()` sends SIGKILL;
  consider a SIGTERM / SIGKILL pattern with a short grace period.
- **Typed tool calls.** The `Tool` protocol passes `args:
  dict[str, Any]` today. When Stream E specifies a typed variant
  (e.g. `Tool[Args, Result]` with Pydantic Args/Result), this
  sandbox gets typed too — but for v1, dict in, any out.

---

## Integration & compatibility requirements

- **Hard dependency on Stream E.** `ToolUser` and the `Tool`
  protocol must exist. Do not start until E is merged.
- **No new dependencies.** `asyncio`, `subprocess`, `json`, `sys`,
  `resource` — all stdlib.
- **Does not touch `Agent.invoke`** or any core module. Lives
  entirely under `operad/runtime/launchers/`.
- **Graceful degradation on Windows.** If `platform.system() ==
  "Windows"`, document that sandbox is unavailable; raise clearly
  on instantiation.
- **Tests mock the subprocess layer.** CI must not actually spawn
  real sandboxed workers; offline tests use
  `asyncio.create_subprocess_exec` mocks. Keep a single opt-in
  `tests/integration/test_sandbox.py` for actual subprocess
  execution.

---

## Acceptance

- `uv run pytest tests/` green.
- `tests/test_sandbox.py`: wrapping a simple in-process tool and
  calling it returns the same result.
- `tests/test_sandbox.py`: a tool that hangs is killed after
  `timeout_seconds`.
- `tests/test_sandbox.py`: a tool that raises causes
  `SandboxedTool.call` to raise a `RuntimeError` with the error
  message.
- `examples/sandbox_tooluser.py` runs a synthetic tool with the
  sandbox and prints the result.

---

## Watch-outs

- Do NOT run untrusted code without a sandbox. This module is the
  sandbox; keep it simple and correct.
- `resource.setrlimit` is POSIX-only; `preexec_fn` on Windows is
  not supported. Platform-gate cleanly.
- JSON-only communication means tool args and results must be
  JSON-serialisable. Document this prominently.
- Do NOT add a retry loop on timeout — failures should propagate.
  The caller decides whether to retry.
- This is v1. Future work (process pool, seccomp, cgroup limits,
  signed manifest of allowed imports) stays explicitly out of
  scope.
