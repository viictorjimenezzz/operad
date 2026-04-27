from __future__ import annotations

"""Capture human feedback for a stored uthereal trace.

Owner: 4-1-cli-run-show-feedback.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from pydantic import ValidationError

from apps_uthereal.commands.show import resolve_trace_path
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.workflow.trace import WorkflowTrace


_ALLOWED_TARGET_PATHS = {
    "context_safeguard",
    "safeguard_talker",
    "reasoner",
    "conv_talker",
    "rule_classifier",
    "retrieval_orchestrator",
    "evidence_planner",
    "fact_filter",
    "rag_talker",
}


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the ``feedback`` subcommand parser."""

    parser = subparsers.add_parser("feedback")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--no-editor", action="store_true")
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Create or validate ``feedback.json`` for a trace."""

    try:
        trace_path = resolve_trace_path(args.trace_id)
        trace = WorkflowTrace.from_jsonl(trace_path)
    except LookupError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(trace.final_answer_text)
    feedback_path = trace_path.parent / "feedback.json"
    created = False
    if not feedback_path.exists():
        _write_template(feedback_path, HumanFeedback.template(trace.trace_id))
        created = True

    if getattr(args, "no_editor", False) and created:
        return 0

    if not getattr(args, "no_editor", False):
        editor = os.environ.get("EDITOR", "vi")
        subprocess.run([editor, str(feedback_path)], check=False)

    try:
        feedback = _read_feedback(feedback_path)
        _validate_target_path(feedback, trace)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    feedback.to_json(feedback_path)
    return 0


def _write_template(path: Path, feedback: HumanFeedback) -> None:
    path.write_text(
        "\n".join(
            [
                "# trace_id: filled in for you",
                "# final_answer_critique: required - what's wrong with the answer",
                "# target_path: optional - null means let the Blamer decide; or set",
                "#   one of: context_safeguard, safeguard_talker, reasoner,",
                "#           conv_talker, rule_classifier, retrieval_orchestrator,",
                "#           evidence_planner, fact_filter, rag_talker.",
                "# severity: 0..1 (default 1.0)",
                "# desired_behavior: optional - what you'd want instead.",
                json.dumps(
                    feedback.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )


def _read_feedback(path: Path) -> HumanFeedback:
    return HumanFeedback.model_validate(json.loads(_strip_leading_comments(path)))


def _strip_leading_comments(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and lines[0].lstrip().startswith("#"):
        lines.pop(0)
    return "\n".join(lines)


def _validate_target_path(feedback: HumanFeedback, trace: WorkflowTrace) -> None:
    if not 0 <= feedback.severity <= 1:
        raise ValueError("severity must be between 0 and 1")
    if not feedback.final_answer_critique.strip():
        raise ValueError("final_answer_critique is required")
    if feedback.target_path is None:
        return
    allowed = set(_ALLOWED_TARGET_PATHS)
    allowed.update(frame.step_name for frame in trace.frames)
    if feedback.target_path not in allowed:
        raise ValueError(f"unknown target_path: {feedback.target_path}")
