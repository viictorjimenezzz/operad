"""OpenTelemetry observer: one span per leaf invocation.

Optional: the `opentelemetry` packages are only required at
construction time. If they aren't installed, the constructor raises
`RuntimeError` with a clear install hint. Core operad stays importable
without the extra.

Trace-id alignment with operad ``run_id``: at the root span, the
observer injects a ``SpanContext`` whose ``trace_id`` equals the
``run_id`` parsed as a 128-bit integer. UUID4 hex is exactly 32 hex
chars = 128 bits, so the conversion is lossless. Downstream OTel
backends therefore see a trace whose ID matches operad's ``run_id``
verbatim, enabling deterministic deep-links of the form
``{backend_url}/trace/{run_id}`` from operad UIs.
"""

from __future__ import annotations

import secrets
from typing import Any

from ...core.output import OperadOutput
from ...utils.hashing import hash_json
from ..events import AlgorithmEvent
from .base import AgentEvent, Event


_INSTALL_HINT = (
    "OtelObserver requires the `[otel]` extra. "
    "Install with: `pip install operad[otel]`."
)


class OtelObserver:
    """Emit one OpenTelemetry span per operad `start`/`end` pair.

    Chunk events bump a per-span counter flushed as `operad.chunks`
    on `end`. Errors record the exception and set span status ERROR.
    Only hashes are attached as attributes — never raw payloads.

    Algorithm events open a parallel span per `algo_start`/`algo_end`
    pair, keyed by `(run_id, algorithm_path)`. Per-boundary events
    (`generation`, `round`, ...) attach as span events on the
    enclosing algorithm span.
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
        self._algo_spans: dict[tuple[str, str], Any] = {}
        self._algo_tokens: dict[tuple[str, str], Any] = {}

    async def on_event(self, event: Event) -> None:
        if isinstance(event, AlgorithmEvent):
            self._on_algorithm_event(event)
            return
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
        meta = event.metadata or {}
        is_root = bool(meta.get("is_root"))

        if is_root:
            span = self._start_root_span(event.run_id, event.agent_path)
        else:
            span = self._tracer.start_span(event.agent_path)

        token = self._context.attach(self._trace.set_span_in_context(span))
        self._spans[key] = span
        self._tokens[key] = token
        self._chunks[key] = 0

        span.set_attribute("operad.run_id", event.run_id)
        span.set_attribute("operad.agent_path", event.agent_path)
        span.set_attribute("operad.is_root", is_root)
        span.set_attribute("operad.hash_graph", str(meta.get("hash_graph", "")))
        if event.input is not None:
            span.set_attribute(
                "operad.hash_input",
                hash_json(event.input.model_dump(mode="json")),
            )

    def _start_root_span(self, run_id: str, agent_path: str) -> Any:
        """Start a root span whose OTel trace_id derives from ``run_id``.

        Builds a non-recording parent ``SpanContext`` carrying the
        derived trace_id; OTel propagates that trace_id into the child
        span we actually start. If ``run_id`` does not parse as hex,
        falls back to OTel's default trace_id generation.
        """
        from opentelemetry.trace import (
            NonRecordingSpan,
            SpanContext,
            TraceFlags,
        )

        try:
            trace_id = int(run_id, 16)
        except ValueError:
            trace_id = 0
        if trace_id == 0:
            return self._tracer.start_span(agent_path)

        parent_span_id = secrets.randbits(64) or 1
        parent_ctx = SpanContext(
            trace_id=trace_id,
            span_id=parent_span_id,
            is_remote=False,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
        parent = NonRecordingSpan(parent_ctx)
        ctx = self._trace.set_span_in_context(parent)
        return self._tracer.start_span(agent_path, context=ctx)

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

    def _on_algorithm_event(self, event: AlgorithmEvent) -> None:
        key = (event.run_id, event.algorithm_path)
        if event.kind == "algo_start":
            span = self._tracer.start_span(event.algorithm_path)
            token = self._context.attach(self._trace.set_span_in_context(span))
            self._algo_spans[key] = span
            self._algo_tokens[key] = token
            span.set_attribute("operad.run_id", event.run_id)
            span.set_attribute("operad.algorithm_path", event.algorithm_path)
            for k, v in _otel_attrs(event.payload).items():
                span.set_attribute(k, v)
        elif event.kind == "algo_end":
            span = self._algo_spans.pop(key, None)
            token = self._algo_tokens.pop(key, None)
            if span is None:
                return
            try:
                for k, v in _otel_attrs(event.payload).items():
                    span.set_attribute(f"end.{k}", v)
                from opentelemetry.trace import Status, StatusCode

                span.set_status(Status(StatusCode.OK))
            finally:
                if token is not None:
                    self._context.detach(token)
                span.end()
        elif event.kind == "algo_error":
            span = self._algo_spans.pop(key, None)
            token = self._algo_tokens.pop(key, None)
            inline = False
            if span is None:
                span = self._tracer.start_span(event.algorithm_path)
                inline = True
            try:
                for k, v in _otel_attrs(event.payload).items():
                    span.set_attribute(f"error.{k}", v)
                from opentelemetry.trace import Status, StatusCode

                desc = str(event.payload.get("type", "error"))
                span.set_status(Status(StatusCode.ERROR, description=desc))
            finally:
                if token is not None and not inline:
                    self._context.detach(token)
                span.end()
        else:
            span = self._algo_spans.get(key)
            if span is None:
                return
            span.add_event(event.kind, attributes=_otel_attrs(event.payload))

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

        # OTel `gen_ai.*` semantic conventions — picked up by Langfuse and
        # other LLM observability backends to render the span as a typed
        # "generation" with model + token usage in the UI.
        if out.backend:
            span.set_attribute("gen_ai.system", out.backend)
        if out.model:
            span.set_attribute("gen_ai.request.model", out.model)
        if out.prompt_tokens is not None:
            span.set_attribute("gen_ai.usage.prompt_tokens", out.prompt_tokens)
        if out.completion_tokens is not None:
            span.set_attribute("gen_ai.usage.completion_tokens", out.completion_tokens)
        if out.prompt_tokens is not None and out.completion_tokens is not None:
            span.set_attribute(
                "gen_ai.usage.total_tokens",
                out.prompt_tokens + out.completion_tokens,
            )


def _otel_attrs(payload: dict[str, Any]) -> dict[str, Any]:
    """Sanitise payload keys into OTel-compatible attribute values.

    OTel attributes accept str, bool, int, float, or sequences thereof.
    Non-conforming values are stringified.
    """
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if v is None:
            out[k] = ""
        elif isinstance(v, (str, bool, int, float)):
            out[k] = v
        elif isinstance(v, (list, tuple)) and all(
            isinstance(x, (str, bool, int, float)) for x in v
        ):
            out[k] = list(v)
        else:
            out[k] = str(v)
    return out
