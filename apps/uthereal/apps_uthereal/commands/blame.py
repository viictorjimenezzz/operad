from __future__ import annotations

"""Owner: 4-3-cli-blame."""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from operad.utils.cassette import cassette_context
from pydantic import ValidationError

from apps_uthereal.errors import LoaderError
from apps_uthereal.feedback.blamer import (
    KNOWN_LEAF_PATHS,
    SPECIAL_TARGETS,
    Blamer,
    BlamerOutput,
    render_blamer_input,
)
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.leaves.registry import load_all_leaves
from apps_uthereal.paths import runs_dir
from apps_uthereal.workflow.trace import WorkflowTrace


_DEFAULT_SELFSERVE_ROOT = (
    Path.home()
    / "Documents"
    / "uthereal"
    / "uthereal-src"
    / "uthereal_workflow"
    / "agentic_workflows"
    / "chat"
    / "selfserve"
)
_VALID_TARGETS = KNOWN_LEAF_PATHS + SPECIAL_TARGETS


class _UsageError(Exception):
    """A user-correctable CLI error."""


def add_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Register the `blame` subcommand."""

    parser = subparsers.add_parser("blame")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--feedback")
    parser.add_argument("--target")
    parser.add_argument("--no-confirm", action="store_true")
    parser.add_argument("--selfserve-root")
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Run blame localization for a stored uthereal trace."""

    try:
        run_dir = _resolve_run_dir(str(args.trace_id))
        trace = _read_trace(run_dir / "trace.jsonl")
        feedback_path = _feedback_path(args, run_dir)
        feedback = _read_feedback(feedback_path)

        if args.target:
            verdict = _manual_verdict(str(args.target), feedback)
        else:
            selfserve_root = _selfserve_root(getattr(args, "selfserve_root", None))
            verdict = await _blamer_verdict(
                trace=trace,
                feedback=feedback,
                run_dir=run_dir,
                selfserve_root=selfserve_root,
            )

        _print_context(trace, verdict)
        if getattr(args, "no_confirm", False):
            _write_blame(run_dir, verdict)
            return 0

        choice = input("Apply this blame? [Y/n/edit] ").strip().lower()
        if choice in {"", "y", "yes"}:
            _write_blame(run_dir, verdict)
            return 0
        if choice in {"n", "no"}:
            return 0
        if choice == "edit":
            _write_blame(run_dir, _edit_verdict(verdict))
            return 0
        raise _UsageError("Expected Y, n, or edit.")
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _resolve_run_dir(trace_id: str) -> Path:
    if not trace_id:
        raise _UsageError("--trace-id must not be empty.")

    candidates: list[tuple[Path, set[str]]] = []
    for child in sorted(path for path in runs_dir().iterdir() if path.is_dir()):
        identifiers = {child.name}
        identifiers.update(_trace_header_ids(child / "trace.jsonl"))
        identifiers = {identifier for identifier in identifiers if identifier}
        if any(identifier.startswith(trace_id) for identifier in identifiers):
            candidates.append((child, identifiers))

    exact = [path for path, identifiers in candidates if trace_id in identifiers]
    if len(exact) == 1:
        return exact[0]
    if len(candidates) == 1:
        return candidates[0][0]
    if candidates:
        labels = ", ".join(path.name for path, _ids in candidates)
        raise _UsageError(f"Ambiguous trace id {trace_id!r}; matches: {labels}.")
    raise _UsageError(f"No run found for trace id {trace_id!r}.")


def _trace_header_ids(path: Path) -> set[str]:
    with suppress(OSError, json.JSONDecodeError):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if "step_name" in record:
                return set()
            return {
                str(value)
                for value in (record.get("trace_id"), record.get("entry_id"))
                if value
            }
    return set()


def _read_trace(path: Path) -> WorkflowTrace:
    try:
        return WorkflowTrace.from_jsonl(path)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError) as exc:
        raise _UsageError(f"Could not read trace {path}: {exc}") from exc


def _feedback_path(args: argparse.Namespace, run_dir: Path) -> Path:
    value = getattr(args, "feedback", None)
    return Path(value).expanduser() if value else run_dir / "feedback.json"


def _read_feedback(path: Path) -> HumanFeedback:
    if not path.exists():
        raise _UsageError(f"Feedback file not found: {path}.")
    try:
        return HumanFeedback.from_json(path)
    except (OSError, ValidationError) as exc:
        raise _UsageError(f"Malformed feedback file {path}: {exc}") from exc


def _manual_verdict(target: str, feedback: HumanFeedback) -> BlamerOutput:
    _validate_target(target)
    return BlamerOutput(
        target_path=target,
        rationale=f"Manual override via --target {target}.",
        leaf_targeted_critique=feedback.final_answer_critique,
        severity=feedback.severity,
    )


async def _blamer_verdict(
    *,
    trace: WorkflowTrace,
    feedback: HumanFeedback,
    run_dir: Path,
    selfserve_root: Path,
) -> BlamerOutput:
    try:
        leaf_directory = load_all_leaves(selfserve_root)
    except (OSError, LoaderError, ValidationError) as exc:
        message = f"Could not load leaves from {selfserve_root}: {exc}"
        raise _UsageError(message) from exc

    blamer_input = render_blamer_input(
        trace=trace,
        feedback=feedback,
        leaf_directory=leaf_directory,
    )
    cassette_path = run_dir / "cassettes" / "llm" / "blame.jsonl"
    with cassette_context(cassette_path, mode="record"):
        blamer = await Blamer().abuild()
        return (await blamer(blamer_input)).response


def _validate_target(target: str) -> None:
    if target in _VALID_TARGETS:
        return
    valid = ", ".join(_VALID_TARGETS)
    raise _UsageError(f"Unknown target {target!r}. Valid targets: {valid}.")


def _selfserve_root(value: str | None) -> Path:
    if value:
        return Path(value).expanduser()
    env_value = os.environ.get("UTHEREAL_SELFSERVE_ROOT")
    if env_value:
        return Path(env_value).expanduser()
    return _DEFAULT_SELFSERVE_ROOT


def _print_context(trace: WorkflowTrace, verdict: BlamerOutput) -> None:
    print("Final answer:")
    print(trace.final_answer_text)
    print()
    print("Blame verdict:")
    print(f"target_path: {verdict.target_path}")
    print(f"rationale: {verdict.rationale}")
    print(f"leaf_targeted_critique: {verdict.leaf_targeted_critique}")
    print(f"severity: {verdict.severity}")


def _write_blame(run_dir: Path, verdict: BlamerOutput) -> None:
    path = run_dir / "blame.json"
    path.write_text(
        json.dumps(
            verdict.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _edit_verdict(verdict: BlamerOutput) -> BlamerOutput:
    data = verdict.model_dump(mode="json")
    data["_comment_target_path"] = "Known leaf path, control_flow, data, or no_fault."
    data["_comment_leaf_targeted_critique"] = (
        "Critique that should be passed to the selected leaf prompt."
    )
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        suffix=".json",
        delete=False,
    ) as file:
        path = Path(file.name)
        file.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
        file.write("\n")

    try:
        editor = os.environ.get("EDITOR", "vi")
        result = subprocess.run([editor, str(path)], check=False)
        if result.returncode != 0:
            raise _UsageError(f"Editor exited with status {result.returncode}.")
        edited = BlamerOutput.model_validate_json(path.read_text(encoding="utf-8"))
        _validate_target(edited.target_path)
        return edited
    except (OSError, ValidationError) as exc:
        raise _UsageError(f"Edited blame did not validate: {exc}") from exc
    finally:
        path.unlink(missing_ok=True)
