"""Tests for `operad.runtime.retry.with_retry` and its wiring in `Agent.forward`."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from operad import Agent, AgentEvent, Configuration
from operad.core.build import _TRACER
from operad.runtime.observers import registry as obs_registry
from operad.runtime.observers.base import _RETRY_META
from operad.runtime.retry import with_retry
from operad.utils.errors import BuildError

from .conftest import A, B


pytestmark = pytest.mark.asyncio


class _Collector:
    def __init__(self) -> None:
        self.events: list[AgentEvent] = []

    async def on_event(self, event: AgentEvent) -> None:
        self.events.append(event)


@pytest.fixture(autouse=True)
def _clear_registry() -> Any:
    obs_registry.clear()
    yield
    obs_registry.clear()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop retry delays so unit tests run in milliseconds."""

    async def _instant(_: float) -> None:
        return None

    monkeypatch.setattr(asyncio, "sleep", _instant)


# --- with_retry unit tests --------------------------------------------------


async def test_retry_succeeds_within_budget() -> None:
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("transient")
        return 42

    out = await with_retry(fn, max_retries=3, backoff_base=0.0, timeout=None)
    assert out == 42
    assert calls["n"] == 3


async def test_retry_exhausts_and_raises() -> None:
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        raise RuntimeError("always")

    with pytest.raises(RuntimeError, match="always"):
        await with_retry(fn, max_retries=2, backoff_base=0.0, timeout=None)
    assert calls["n"] == 3  # 1 initial + 2 retries


async def test_max_retries_zero_propagates_first_failure() -> None:
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await with_retry(fn, max_retries=0, backoff_base=0.0, timeout=None)
    assert calls["n"] == 1


async def test_per_attempt_timeout() -> None:
    async def fn() -> int:
        await asyncio.Event().wait()
        return 0

    with pytest.raises(asyncio.TimeoutError):
        await with_retry(fn, max_retries=0, backoff_base=0.0, timeout=0.01)


async def test_build_error_is_not_retried() -> None:
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        raise BuildError("output_mismatch", "nope")

    with pytest.raises(BuildError):
        await with_retry(fn, max_retries=5, backoff_base=0.0, timeout=None)
    assert calls["n"] == 1


async def test_cancelled_is_not_retried() -> None:
    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await with_retry(fn, max_retries=5, backoff_base=0.0, timeout=None)
    assert calls["n"] == 1


async def test_on_attempt_callback_fires_with_last_error() -> None:
    seen: list[tuple[int, str | None]] = []

    def _cb(attempt: int, last: BaseException | None) -> None:
        seen.append((attempt, None if last is None else str(last)))

    calls = {"n": 0}

    async def fn() -> int:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"err-{calls['n']}")
        return 7

    out = await with_retry(
        fn, max_retries=3, backoff_base=0.0, timeout=None, on_attempt=_cb
    )
    assert out == 7
    assert seen == [(1, None), (2, "err-1"), (3, "err-2")]


# --- Agent.forward / invoke integration -------------------------------------


class _RetryLeaf(Agent[Any, Any]):
    """Leaf that exercises the default retry wiring with a fake inner call.

    Mirrors the structure of `Agent.forward` for the provider call but
    substitutes ``fn`` for ``super().invoke_async`` so the test does not
    need a real strands backend.
    """

    def __init__(
        self,
        *,
        config: Configuration,
        input: type,
        output: type,
        fn: Any,
    ) -> None:
        super().__init__(config=config, input=input, output=output)
        self._fn = fn

    async def forward(self, x: Any) -> Any:
        if _TRACER.get() is not None:
            return self.output.model_construct()
        meta = _RETRY_META.get()

        def _record(attempt: int, last: BaseException | None) -> None:
            if meta is not None:
                meta["retries"] = attempt - 1
                meta["last_error"] = None if last is None else repr(last)

        return await with_retry(
            self._fn,
            max_retries=self.config.max_retries,
            backoff_base=self.config.backoff_base,
            timeout=self.config.timeout,
            on_attempt=_record,
        )


async def test_end_event_reports_retry_count() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        temperature=0.0,
        max_tokens=16,
        max_retries=3,
        backoff_base=0.0,
    )
    calls = {"n": 0}

    async def fn() -> B:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError(f"transient-{calls['n']}")
        return B(value=9)

    leaf = await _RetryLeaf(config=cfg, input=A, output=B, fn=fn).abuild()

    col = _Collector()
    obs_registry.register(col)

    out = await leaf(A(text="hi"))
    assert out.response.value == 9
    assert calls["n"] == 3

    end = [e for e in col.events if e.kind == "end"][0]
    assert end.metadata["retries"] == 2
    assert "transient-2" in end.metadata["last_error"]


async def test_end_event_has_zero_retries_on_first_success() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        temperature=0.0,
        max_tokens=16,
        max_retries=3,
        backoff_base=0.0,
    )

    async def fn() -> B:
        return B(value=1)

    leaf = await _RetryLeaf(config=cfg, input=A, output=B, fn=fn).abuild()

    col = _Collector()
    obs_registry.register(col)

    await leaf(A(text="ok"))

    end = [e for e in col.events if e.kind == "end"][0]
    assert end.metadata["retries"] == 0
    assert end.metadata["last_error"] is None


async def test_error_event_reports_retry_count_on_exhaustion() -> None:
    cfg = Configuration(
        backend="llamacpp",
        host="127.0.0.1:0",
        model="test",
        temperature=0.0,
        max_tokens=16,
        max_retries=2,
        backoff_base=0.0,
    )

    async def fn() -> B:
        raise RuntimeError("always")

    leaf = await _RetryLeaf(config=cfg, input=A, output=B, fn=fn).abuild()

    col = _Collector()
    obs_registry.register(col)

    with pytest.raises(RuntimeError, match="always"):
        await leaf(A())

    err = [e for e in col.events if e.kind == "error"][0]
    assert err.metadata["retries"] == 2
    assert "always" in err.metadata["last_error"]
