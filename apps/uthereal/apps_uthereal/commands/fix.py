from __future__ import annotations

"""`apps-uthereal fix` command.

Owner: 4-2-apply-fix.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from operad.utils.cassette import CassetteMiss

from apps_uthereal.commands.run import CassetteRetrievalClient
from apps_uthereal.feedback.blamer import BlamerOutput
from apps_uthereal.feedback.loss import SPECIAL_TARGETS, UnactionableFeedback
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.paths import runs_dir
from apps_uthereal.retrieval.client import RetrievalClient, RetrievalError
from apps_uthereal.schemas.workflow import (
    ArtemisInput,
    DatasetEntry,
)
from apps_uthereal.train.apply_fix import FixReport, apply_fix
from apps_uthereal.workflow.runner import ArtemisRunner
from apps_uthereal.workflow.trace import WorkflowTrace


_DEFAULT_SELFSERVE_ROOT = Path(
    "/Users/viictorjimenezzz/Documents/uthereal/uthereal-src/"
    "uthereal_workflow/agentic_workflows/chat/selfserve"
)
class _UsageError(Exception):
    """Command-line usage error."""


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register the `fix` subcommand."""

    parser = subparsers.add_parser("fix")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--target")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--selfserve-root")
    parser.add_argument("--lr", type=float, default=1.0)
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Run the prompt-fix command."""

    try:
        run_dir, _trace = _run_dir_for_trace(str(args.trace_id))
        feedback = HumanFeedback.from_json(run_dir / "feedback.json")
        target_path, blame = _resolve_target(run_dir, args.target)
        if target_path in SPECIAL_TARGETS:
            raise UnactionableFeedback(
                reason=target_path,
                message=(
                    f"Feedback target {target_path!r} cannot be turned into "
                    "a leaf-targeted gradient."
                ),
            )

        selfserve_root = _resolve_selfserve_root(args.selfserve_root)
        retrieval: RetrievalClient = CassetteRetrievalClient(
            cassette_dir=run_dir / "cassettes" / "rag",
            inner=None,
            mode="replay",
        )
        artemis_input = await _load_artemis_input(run_dir, retrieval)
        runner = ArtemisRunner(selfserve_root=selfserve_root, retrieval=retrieval)
        await runner.abuild()

        feedback = _feedback_for_fix(
            feedback,
            target_path=target_path,
            blame=blame,
        )
        report = await apply_fix(
            runner=runner,
            artemis_input=artemis_input,
            feedback=feedback,
            target_path=target_path,
            yaml_root=selfserve_root,
            dry_run=bool(args.dry_run),
            lr=float(args.lr),
            llm_cassette_path=_llm_cassette_path(run_dir),
        )

        _write_artifacts(run_dir, report)
        _print_report(report)
        return 0
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (FileNotFoundError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (CassetteMiss, RetrievalError, UnactionableFeedback) as exc:
        message = getattr(exc, "message", str(exc))
        print(message, file=sys.stderr)
        return 1


def _run_dir_for_trace(trace_id: str) -> tuple[Path, WorkflowTrace]:
    matches: list[tuple[Path, WorkflowTrace]] = []
    for run_dir in sorted(path for path in runs_dir().iterdir() if path.is_dir()):
        trace_path = run_dir / "trace.jsonl"
        if not trace_path.exists():
            continue
        trace = WorkflowTrace.from_jsonl(trace_path)
        if _matches_trace(trace_id, run_dir, trace):
            matches.append((run_dir, trace))

    if not matches:
        raise _UsageError(f"trace not found: {trace_id}")
    if len(matches) > 1:
        raise _UsageError(f"trace id is ambiguous: {trace_id}")
    return matches[0]


def _matches_trace(trace_id: str, run_dir: Path, trace: WorkflowTrace) -> bool:
    return any(
        value == trace_id or value.startswith(trace_id)
        for value in (run_dir.name, trace.entry_id, trace.trace_id)
        if value
    )


def _resolve_target(
    run_dir: Path,
    manual_target: str | None,
) -> tuple[str, BlamerOutput | None]:
    if manual_target:
        return manual_target, None

    blame_path = run_dir / "blame.json"
    if not blame_path.exists():
        raise _UsageError(
            "no target - run `apps-uthereal blame` first or pass --target"
        )
    blame = BlamerOutput.model_validate_json(blame_path.read_text(encoding="utf-8"))
    return blame.target_path, blame


def _resolve_selfserve_root(raw_path: str | None) -> Path:
    if raw_path:
        return Path(raw_path).expanduser().resolve()
    env_path = os.environ.get("UTHEREAL_SELFSERVE_ROOT")
    if env_path:
        return Path(env_path).expanduser().resolve()
    return _DEFAULT_SELFSERVE_ROOT


async def _load_artemis_input(
    run_dir: Path,
    retrieval: RetrievalClient,
) -> ArtemisInput:
    """Reconstruct the ArtemisInput from disk + the metadata cassette.

    Falls back to a stub WorkspaceMetadata when the metadata cassette
    isn't present so that older runs (recorded before the metadata
    cassette existed) still replay cleanly.
    """

    from apps_uthereal.schemas.workflow import WorkspaceMetadata

    entry = DatasetEntry.from_json(run_dir / "entry.json")
    try:
        workspace = await retrieval.get_workspace_metadata(
            id_tenant=entry.id_tenant,
            id_workspace=entry.workspace_id,
            id_assistant=entry.id_assistant,
        )
    except RetrievalError:
        workspace = WorkspaceMetadata(
            workspace_id=entry.workspace_id,
            id_tenant=entry.id_tenant,
            id_assistant=entry.id_assistant,
        )
    update: dict[str, Any] = {}
    if not workspace.workspace_id:
        update["workspace_id"] = entry.workspace_id
    if not workspace.id_tenant:
        update["id_tenant"] = entry.id_tenant
    if not workspace.id_assistant:
        update["id_assistant"] = entry.id_assistant
    if update:
        workspace = workspace.model_copy(update=update)
    return ArtemisInput(entry=entry, workspace=workspace)


def _feedback_for_fix(
    feedback: HumanFeedback,
    *,
    target_path: str,
    blame: BlamerOutput | None,
) -> HumanFeedback:
    update: dict[str, Any] = {"target_path": target_path}
    if blame is not None:
        update["final_answer_critique"] = blame.leaf_targeted_critique
        update["severity"] = blame.severity
    return feedback.model_copy(update=update)


def _write_artifacts(run_dir: Path, report: FixReport) -> None:
    (run_dir / "fix.diff").write_text(report.diff_text, encoding="utf-8")
    payload = report.model_dump(
        mode="json",
        exclude={"before_state", "after_state"},
    )
    (run_dir / "fix.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _print_report(report: FixReport) -> None:
    if report.diff_text:
        print(report.diff_text, end="" if report.diff_text.endswith("\n") else "\n")
    else:
        print("(no diff)")
    if not report.yaml_dry_run:
        print(f"Wrote {report.yaml_path}")


def _llm_cassette_path(run_dir: Path) -> Path:
    """Resolve the leaf-call cassette produced by ``run``.

    The fix command replays the original leaf calls (recorded as
    ``cassettes/llm/calls.jsonl`` by ``commands/run.py``). We must NOT
    return ``blame.jsonl`` -- that one only holds the Blamer LLM call
    and uses unrelated keys. Prefer ``calls.jsonl`` when present, then
    any other ``*.jsonl`` that isn't ``blame.jsonl``.
    """

    cassette_root = run_dir / "cassettes" / "llm"
    if cassette_root.is_file():
        return cassette_root
    if not cassette_root.exists():
        return cassette_root / "calls.jsonl"
    preferred = cassette_root / "calls.jsonl"
    if preferred.exists():
        return preferred
    existing = sorted(
        path for path in cassette_root.glob("*.jsonl") if path.name != "blame.jsonl"
    )
    if existing:
        return existing[0]
    return preferred


__all__ = ["add_parser", "run"]
