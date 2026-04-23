# Feature · Retry/backoff implementation

**Addresses.** E-4 (ISSUES.md) + `TODO_RETRY_BACKOFF_IMPL` in
`missing.py`.

`Configuration.timeout`, `max_retries`, and `backoff_base` are
declared and partially threaded to the OpenAI SDK only. No retry loop
runs in `Agent.forward`. Real-world usage against flaky endpoints
blows up on first transient error.

---

## Required reading

- `METAPROMPT.md`, `ISSUES.md` §E-4.
- `operad/core/agent.py::Agent.forward` (line 356–368).
- `operad/core/config.py` (`timeout`, `max_retries`, `backoff_base`).
- `operad/runtime/observers/base.py` (metadata emission).

---

## Proposal

### Retry wrapper in `Agent.forward`

```python
# operad/runtime/retry.py (new)
import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")

async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    max_retries: int,
    backoff_base: float,
    timeout: float | None,
    on_attempt: Callable[[int, Exception | None], None] | None = None,
) -> T:
    """Run `fn` with exponential-backoff retry + optional timeout.

    Delay before attempt i is `backoff_base * 2 ** (i - 1)` with small
    random jitter. Timeout applies per attempt.
    """
    last: Exception | None = None
    for i in range(max_retries + 1):
        if on_attempt:
            on_attempt(i + 1, last)
        try:
            if timeout is None:
                return await fn()
            return await asyncio.wait_for(fn(), timeout=timeout)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            last = e
            if i == max_retries:
                raise
            delay = backoff_base * (2 ** i) + random.uniform(0, backoff_base)
            await asyncio.sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover
```

### Wiring in `Agent.forward`

```python
async def forward(self, x: In) -> Out:
    async with _acquire_slot(self.config):
        async def _call():
            return await super().invoke_async(
                self.format_user_message(x),
                structured_output_model=self.output,
            )
        result = await with_retry(
            _call,
            max_retries=self.config.max_retries,
            backoff_base=self.config.backoff_base,
            timeout=self.config.timeout,
        )
    return result.structured_output
```

### Observer metadata

Each retry should surface in the trace. Add to `AgentEvent.metadata`
on the terminal event:

```python
metadata["retries"] = attempt_count - 1   # 0 if first call succeeded
metadata["last_error"] = str(last_exception) if last_exception else None
```

Thread through from `on_attempt` callback in `with_retry`.

---

## Scope

- New: `operad/runtime/retry.py`.
- Edit: `operad/core/agent.py::Agent.forward`.
- Edit: `operad/runtime/observers/base.py` if `AgentEvent` needs
  richer metadata typing (probably not — it's already `dict[str, Any]`).
- New: `tests/test_retry.py`.

Do NOT:
- Re-implement timeouts inside the OpenAI adapter. Let the generic
  `with_retry(timeout=...)` own it.
- Retry on `BuildError` or `asyncio.CancelledError` — they're not
  transient.
- Retry on validation errors from structured output parsing — those
  are programmer errors, not network flakes.

---

## Tests

- `tests/test_retry.py`:
  - Mock leaf whose first N-1 calls raise transient errors; assert
    `Agent.forward` succeeds on attempt N when `max_retries >= N`.
  - With `max_retries=0`, the error propagates on first failure.
  - `timeout=0.01` on a slow mock raises `TimeoutError`.
  - `AgentEvent.metadata["retries"]` reflects the actual retry count.

---

## Acceptance

- `uv run pytest tests/` green.
- An agent with `Configuration(max_retries=3, backoff_base=0.1)` can
  survive two transient failures and deliver on the third try.
- Traces (via `TraceObserver`) show `retries` count per step.
- `README.md` mentions retry/backoff under "Configuration".

---

## Watch-outs

- `asyncio.wait_for` cancels the inner coroutine on timeout — make
  sure `_acquire_slot` release is honoured via `async with`.
- Jitter helps against synchronized retry storms across sibling
  agents — keep it in.
- Don't retry inside `_init_strands` at `build()` time. Retry is
  runtime-only.
- Classify which exceptions are retriable. Start conservatively:
  everything except `BuildError` and `CancelledError` is retried.
  Refine later if `RateLimitError` deserves different backoff.
