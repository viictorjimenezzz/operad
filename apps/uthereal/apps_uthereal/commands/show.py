from __future__ import annotations

"""Pretty-print a stored uthereal workflow trace.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from apps_uthereal.paths import runs_dir
from apps_uthereal.workflow.trace import TraceFrame, WorkflowTrace


_MAX_FIELD_CHARS = 600


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``show`` subcommand parser."""

    parser = subparsers.add_parser("show")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--frame", default=None)
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Print a deterministic terminal summary for one trace."""

    try:
        trace_path = resolve_trace_path(args.trace_id)
        trace = WorkflowTrace.from_jsonl(trace_path)
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    frame_name = getattr(args, "frame", None)
    if frame_name:
        try:
            frames = [trace.find_step(frame_name)]
        except KeyError:
            print(f"frame not found: {frame_name}", file=sys.stderr)
            return 2
    else:
        frames = trace.frames

    print(render_trace(trace, frames=frames))
    return 0


def resolve_trace_path(trace_id: str) -> Path:
    """Resolve a trace id or entry id prefix to a stored ``trace.jsonl`` path."""

    prefix = trace_id.strip()
    if not prefix:
        raise LookupError("trace id is empty")

    matches: list[Path] = []
    for path in sorted(runs_dir().glob("*/trace.jsonl")):
        if path.parent.name.startswith(prefix):
            matches.append(path)
            continue
        trace = WorkflowTrace.from_jsonl(path)
        if trace.trace_id.startswith(prefix):
            matches.append(path)

    unique_matches = sorted(set(matches))
    if not unique_matches:
        raise LookupError(f"trace not found: {trace_id}")
    if len(unique_matches) > 1:
        names = ", ".join(path.parent.name for path in unique_matches)
        raise LookupError(f"trace id is ambiguous: {trace_id} ({names})")
    return unique_matches[0]


def render_trace(
    trace: WorkflowTrace,
    *,
    frames: list[TraceFrame] | None = None,
) -> str:
    """Render a trace as deterministic plain text."""

    selected_frames = trace.frames if frames is None else frames
    lines = [
        f"trace_id: {trace.trace_id}",
        f"entry_id: {trace.entry_id}",
        f"intent_decision: {trace.intent_decision}",
        f"final_step: {_final_step(trace)}",
        f"started_at: {_format_optional(trace.started_at)}",
        f"finished_at: {_format_optional(trace.finished_at)}",
    ]
    for frame in selected_frames:
        lines.extend(["", *_render_frame(frame)])
    return "\n".join(lines)


def _render_frame(frame: TraceFrame) -> list[str]:
    return [
        f"[{frame.step_name}]",
        f"agent_class: {frame.agent_class}",
        f"latency_ms: {frame.latency_ms:.3f}",
        f"input: {_truncate(_canonical_json(frame.input))}",
        f"output: {_truncate(_canonical_json(frame.output))}",
    ]


def _final_step(trace: WorkflowTrace) -> str:
    if trace.frames:
        return trace.frames[-1].step_name
    return ""


def _format_optional(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _truncate(value: str) -> str:
    if len(value) <= _MAX_FIELD_CHARS:
        return value
    return f"{value[:_MAX_FIELD_CHARS]}...[truncated, total={len(value)} chars]"
