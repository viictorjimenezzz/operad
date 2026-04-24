"""OpenTelemetry observer: one span per leaf invocation.

Optional: the `opentelemetry` packages are only required at
construction time. If they aren't installed, the constructor raises
`RuntimeError` with a clear install hint. Core operad stays importable
without the extra.
"""

from __future__ import annotations

from typing import Any

from ...core.output import OperadOutput
from ...utils.hashing import hash_json
from .base import AgentEvent


_INSTALL_HINT = (
    "OtelObserver requires the `[otel]` extra. "
    "Install with: `pip install operad[otel]`."
)


class OtelObserver:
    """Emit one OpenTelemetry span per operad `start`/`end` pair.

    Chunk events bump a per-span counter flushed as `operad.chunks`
    on `end`. Errors record the exception and set span status ERROR.
    Only hashes are attached as attributes — never raw payloads.
    """

    def __init__(self, *, tracer_name: str = "operad") -> None:
        try:
            from opentelemetry import context as _ot_context
            from opentelemetry import trace as _ot_trace
        except ImportError as e:
            raise RuntimeError(_INSTALL_HINT) from e

        self._trace = _ot_trace
        self._context = _ot_context
        self._tracer = _ot_trace.get_tracer(tracer_name)
        self._spans: dict[tuple[str, str], Any] = {}
        self._chunks: dict[tuple[str, str], int] = {}
        self._tokens: dict[tuple[str, str], Any] = {}

    async def on_event(self, event: AgentEvent) -> None:
        key = (event.run_id, event.agent_path)
        if event.kind == "start":
            self._on_start(key, event)
        elif event.kind == "chunk":
            self._chunks[key] = self._chunks.get(key, 0) + 1
        elif event.kind == "end":
            self._on_end(key, event)
        elif event.kind == "error":
            self._on_error(key, event)

    def _on_start(self, key: tuple[str, str], event: AgentEvent) -> None:
        span = self._tracer.start_span(event.agent_path)
        token = self._context.attach(self._trace.set_span_in_context(span))
        self._spans[key] = span
        self._tokens[key] = token
        self._chunks[key] = 0

        span.set_attribute("operad.run_id", event.run_id)
        span.set_attribute("operad.agent_path", event.agent_path)
        meta = event.metadata or {}
        span.set_attribute("operad.is_root", bool(meta.get("is_root")))
        span.set_attribute("operad.hash_graph", str(meta.get("hash_graph", "")))
        if event.input is not None:
            span.set_attribute(
                "operad.hash_input",
                hash_json(event.input.model_dump(mode="json")),
            )

    def _on_end(self, key: tuple[str, str], event: AgentEvent) -> None:
        span = self._spans.pop(key, None)
        token = self._tokens.pop(key, None)
        chunks = self._chunks.pop(key, 0)
        if span is None:
            return
        try:
            if isinstance(event.output, OperadOutput):
                self._set_envelope_attributes(span, event.output)
            span.set_attribute("operad.chunks", chunks)
            from opentelemetry.trace import Status, StatusCode

            span.set_status(Status(StatusCode.OK))
        finally:
            if token is not None:
                self._context.detach(token)
            span.end()

    def _on_error(self, key: tuple[str, str], event: AgentEvent) -> None:
        span = self._spans.pop(key, None)
        token = self._tokens.pop(key, None)
        chunks = self._chunks.pop(key, 0)
        inline = False
        if span is None:
            span = self._tracer.start_span(event.agent_path)
            inline = True
        try:
            span.set_attribute("operad.chunks", chunks)
            if event.error is not None:
                span.record_exception(event.error)
            from opentelemetry.trace import Status, StatusCode

            desc = type(event.error).__name__ if event.error is not None else "error"
            span.set_status(Status(StatusCode.ERROR, description=desc))
        finally:
            if token is not None and not inline:
                self._context.detach(token)
            span.end()

    def _set_envelope_attributes(self, span: Any, out: OperadOutput) -> None:
        span.set_attribute("operad.hash_operad_version", out.hash_operad_version)
        span.set_attribute("operad.hash_python_version", out.hash_python_version)
        span.set_attribute("operad.hash_model", out.hash_model)
        span.set_attribute("operad.hash_prompt", out.hash_prompt)
        span.set_attribute("operad.hash_graph", out.hash_graph)
        span.set_attribute("operad.hash_input", out.hash_input)
        span.set_attribute("operad.hash_output_schema", out.hash_output_schema)
        span.set_attribute("operad.latency_ms", out.latency_ms)
        if out.prompt_tokens is not None:
            span.set_attribute("operad.prompt_tokens", out.prompt_tokens)
        if out.completion_tokens is not None:
            span.set_attribute("operad.completion_tokens", out.completion_tokens)
