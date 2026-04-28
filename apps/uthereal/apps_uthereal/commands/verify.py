from __future__ import annotations

"""Re-run an entry against the patched YAMLs and diff the result.

Owner: 5-1-verify-and-demo.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from operad.utils.cassette import CassetteMiss, cassette_context

from apps_uthereal.commands.run import (
    CassetteRetrievalClient,
    LiveRetrievalClient,
    _cassette_env,
    _resolve_selfserve_root,
)
from apps_uthereal.paths import runs_dir
from apps_uthereal.retrieval.client import RetrievalError
from apps_uthereal.schemas.workflow import (
    ArtemisInput,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.workflow.runner import ArtemisRunner
from apps_uthereal.workflow.trace import WorkflowTrace


class _UsageError(Exception):
    """A user-correctable CLI error."""


def add_parser(subparsers: argparse._SubParsersAction[Any]) -> None:
    """Register the ``verify`` subcommand parser."""

    parser = subparsers.add_parser("verify")
    parser.add_argument("--trace-id", required=True)
    parser.add_argument("--selfserve-root", type=Path, default=None)
    parser.add_argument(
        "--rag-base-url",
        default=None,
        help="RAG service URL. Defaults to $UTHEREAL_RAG_URL when set.",
    )
    parser.set_defaults(func=run)


async def run(args: argparse.Namespace) -> int:
    """Reload, rerun, and produce ``verify.json`` for one trace."""

    try:
        run_dir = _resolve_run_dir(str(args.trace_id))
        before_trace = WorkflowTrace.from_jsonl(run_dir / "trace.jsonl")
        before_answer = (run_dir / "answer.txt").read_text(encoding="utf-8").rstrip("\n")
        target_path = _read_target_path(run_dir / "fix.json")
        entry = DatasetEntry.from_json(run_dir / "entry.json")

        selfserve_root = _resolve_selfserve_root(args.selfserve_root)
        if selfserve_root is None:
            raise _UsageError(
                "selfserve root not found; pass --selfserve-root"
            )

        rag_base_url = args.rag_base_url or os.environ.get("UTHEREAL_RAG_URL")
        live_rag = LiveRetrievalClient(rag_base_url) if rag_base_url else None
        rag_dir = run_dir / "cassettes" / "rag"
        rag_dir.mkdir(parents=True, exist_ok=True)
        retrieval = CassetteRetrievalClient(
            cassette_dir=rag_dir,
            inner=live_rag,
            mode="record-missing",
        )

        workspace = _workspace_from_entry_json(run_dir / "entry.json", entry)
        runner = ArtemisRunner(selfserve_root=selfserve_root, retrieval=retrieval)

        # If the entry didn't ship an inline ``workspace`` block, mirror
        # ``commands/run.py``: pull rules + tags from the metadata cassette
        # (or the live RAG service when configured) so the rerun sees the
        # same workspace the original run did.
        raw_entry = json.loads((run_dir / "entry.json").read_text(encoding="utf-8"))
        if (
            not isinstance(raw_entry, dict)
            or not isinstance(raw_entry.get("workspace"), dict)
        ) and entry.id_tenant and entry.workspace_id:
            try:
                fetched = await retrieval.get_workspace_metadata(
                    id_tenant=entry.id_tenant,
                    id_workspace=entry.workspace_id,
                    id_assistant=entry.id_assistant,
                )
                workspace = _merge_workspace_for_verify(fetched, workspace)
            except RetrievalError:
                pass
        artemis_input = ArtemisInput(entry=entry, workspace=workspace)

        llm_dir = run_dir / "cassettes" / "llm"
        llm_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = llm_dir / "calls.jsonl"
        before_cassette_keys = _cassette_keys(cassette_path)

        try:
            with _cassette_env(llm_dir, "record"):
                with cassette_context(cassette_path, mode="record"):
                    await runner.abuild()
                    after_answer_obj, after_trace = await runner.run_with_trace(
                        artemis_input
                    )
        except (CassetteMiss, RetrievalError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

        after_cassette_keys = _cassette_keys(cassette_path)
        rerecorded_keys = sorted(after_cassette_keys - before_cassette_keys)
        rerecorded_steps = _rerecorded_steps(rerecorded_keys, after_trace)

        verify_payload = {
            "trace_id_before": before_trace.trace_id,
            "trace_id_after": after_trace.trace_id,
            "before_answer": before_answer,
            "after_answer": after_answer_obj.utterance,
            "before_intent": before_trace.intent_decision,
            "after_intent": after_trace.intent_decision,
            "before_final_step": _final_step(before_trace),
            "after_final_step": _final_step(after_trace),
            "target_path": target_path,
            "leaf_output_diff": _leaf_output_diff(
                before_trace, after_trace, target_path
            ),
            "rerecorded_steps": rerecorded_steps,
        }

        verify_path = run_dir / "verify.json"
        verify_path.write_text(
            json.dumps(verify_payload, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        _print_diff(verify_payload)
        return 0
    except _UsageError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (FileNotFoundError, ValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 2


def _resolve_run_dir(trace_id: str) -> Path:
    if not trace_id:
        raise _UsageError("--trace-id must not be empty.")
    matches: list[Path] = []
    for child in sorted(p for p in runs_dir().iterdir() if p.is_dir()):
        identifiers = {child.name}
        identifiers.update(_trace_header_ids(child / "trace.jsonl"))
        if any(value.startswith(trace_id) for value in identifiers if value):
            matches.append(child)
    if not matches:
        raise _UsageError(f"No run found for trace id {trace_id!r}.")
    if len(matches) > 1:
        labels = ", ".join(p.name for p in matches)
        raise _UsageError(
            f"Ambiguous trace id {trace_id!r}; matches: {labels}."
        )
    return matches[0]


def _trace_header_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
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
    except (OSError, json.JSONDecodeError):
        return set()
    return set()


def _merge_workspace_for_verify(
    fetched: WorkspaceMetadata,
    fallback: WorkspaceMetadata,
) -> WorkspaceMetadata:
    update: dict[str, Any] = {}
    if not fetched.workspace_id and fallback.workspace_id:
        update["workspace_id"] = fallback.workspace_id
    if not fetched.id_tenant and fallback.id_tenant:
        update["id_tenant"] = fallback.id_tenant
    if not fetched.id_assistant and fallback.id_assistant:
        update["id_assistant"] = fallback.id_assistant
    if update:
        return fetched.model_copy(update=update)
    return fetched


def _workspace_from_entry_json(
    entry_json: Path,
    entry: DatasetEntry,
) -> WorkspaceMetadata:
    """Build a WorkspaceMetadata from the saved entry payload.

    Mirrors ``commands/run.py::_workspace_from_entry`` so verify reuses the
    same workspace shape the original ``run`` invocation saw, avoiding a
    retrieval call that may not have been cassetted (DIRECT_ANSWER entries
    never call into retrieval).
    """

    raw = json.loads(entry_json.read_text(encoding="utf-8"))
    payload = raw.get("workspace") if isinstance(raw, dict) else None
    if isinstance(payload, dict):
        merged = dict(payload)
        merged.setdefault("workspace_id", entry.workspace_id)
        merged.setdefault("id_tenant", entry.id_tenant)
        merged.setdefault("id_assistant", entry.id_assistant)
        return WorkspaceMetadata.model_validate(merged)
    return WorkspaceMetadata(
        workspace_id=entry.workspace_id,
        id_tenant=entry.id_tenant,
        id_assistant=entry.id_assistant,
    )


def _read_target_path(fix_json: Path) -> str:
    if not fix_json.exists():
        raise _UsageError(
            "fix.json missing; run `apps-uthereal fix` before verifying"
        )
    payload = json.loads(fix_json.read_text(encoding="utf-8"))
    target = payload.get("target_path")
    if not target:
        raise _UsageError("fix.json has no target_path")
    return str(target)


def _final_step(trace: WorkflowTrace) -> str:
    if not trace.frames:
        return ""
    return trace.frames[-1].step_name


def _leaf_output_diff(
    before: WorkflowTrace,
    after: WorkflowTrace,
    target_path: str,
) -> dict[str, dict[str, Any]]:
    return {
        "before": _last_output_for(before, target_path),
        "after": _last_output_for(after, target_path),
    }


def _last_output_for(trace: WorkflowTrace, target_path: str) -> dict[str, Any]:
    for frame in reversed(trace.frames):
        if frame.step_name == target_path:
            return dict(frame.output)
    return {}


def _cassette_keys(cassette_path: Path) -> set[str]:
    if not cassette_path.exists():
        return set()
    keys: set[str] = set()
    for line in cassette_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = record.get("key") or record.get("hash") or record.get("id")
        if isinstance(key, str):
            keys.add(key)
    return keys


def _rerecorded_steps(
    new_keys: list[str],
    after_trace: WorkflowTrace,
) -> list[str]:
    """Best-effort attribution of newly recorded LLM keys to leaf steps.

    The cassette format does not encode step names, so we approximate by
    listing every leaf step that ran in the *after* trace whose hash_input
    or hash_prompt is one of the newly recorded keys.
    """

    if not new_keys:
        return []
    new = set(new_keys)
    rerecorded: list[str] = []
    seen: set[str] = set()
    for frame in after_trace.frames:
        if frame.step_name in seen:
            continue
        if frame.hash_prompt in new or frame.hash_input in new:
            rerecorded.append(frame.step_name)
            seen.add(frame.step_name)
    if rerecorded:
        return rerecorded
    return [frame.step_name for frame in after_trace.frames if frame.step_name]


def _print_diff(payload: dict[str, Any]) -> None:
    print(f"target_path: {payload['target_path']}")
    print(
        f"trace_id: {payload['trace_id_before']} -> {payload['trace_id_after']}"
    )
    print(
        f"intent: {payload['before_intent']} -> {payload['after_intent']}"
    )
    print(
        f"final_step: {payload['before_final_step']} -> {payload['after_final_step']}"
    )
    print(f"rerecorded_steps: {', '.join(payload['rerecorded_steps']) or '(none)'}")
    print()
    print("--- before ---")
    print(payload["before_answer"])
    print()
    print("+++ after +++")
    print(payload["after_answer"])


__all__ = ["add_parser", "run"]
