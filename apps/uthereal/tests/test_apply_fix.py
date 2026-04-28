from __future__ import annotations

"""Tests for targeted prompt fixes.

Owner: 4-2-apply-fix.
"""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from operad import Agent
from operad.optim.parameter import Parameter, TextualGradient

import apps_uthereal.commands.fix as fix_cmd
import apps_uthereal.train.apply_fix as apply_fix_module
from apps_uthereal.cli import main
from apps_uthereal.feedback.blamer import BlamerOutput
from apps_uthereal.feedback.loss import UnactionableFeedback
from apps_uthereal.feedback.schema import HumanFeedback
from apps_uthereal.leaves._common import load_yaml
from apps_uthereal.leaves.conversational_talker import ConversationalTalkerLeaf
from apps_uthereal.leaves.reasoner import ReasonerLeaf
from apps_uthereal.leaves.registry import LEAF_STEP_NAMES
from apps_uthereal.schemas.retrieval import RetrievalResult, RetrievalSpecification
from apps_uthereal.schemas.workflow import (
    ArtemisFinalAnswer,
    ArtemisInput,
    DatasetEntry,
    WorkspaceMetadata,
)
from apps_uthereal.train.apply_fix import FixReport, apply_fix
from apps_uthereal.workflow.trace import WorkflowTrace


FIXTURES = Path(__file__).parent / "fixtures"
YAML_FIXTURES = FIXTURES / "yamls"


class _FakeTape:
    async def backward(
        self,
        grad: TextualGradient,
        *,
        parameters: list[Parameter[Any]],
        propagator_factory: Any = None,
        parameter_grad_factory: Any = None,
    ) -> None:
        for parameter in parameters:
            parameter.grad = TextualGradient(
                message=grad.message,
                severity=grad.severity,
                target_paths=grad.target_paths,
            )


class _FakeTextualGradientDescent:
    def __init__(
        self,
        params: list[Parameter[Any]],
        lr: float = 1.0,
        *,
        config: Any = None,
    ) -> None:
        self.params = params
        self.lr = lr
        self.config = config

    async def step(self) -> None:
        for parameter in self.params:
            if parameter.path == "task" and parameter.grad is not None:
                parameter.write(
                    f"{parameter.read()}\n\nRewrite note: answer more directly."
                )


class _AssertingRetrieval:
    async def retrieve(
        self,
        spec: RetrievalSpecification,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> RetrievalResult:
        raise AssertionError("network retrieval should not be called")

    async def get_workspace_metadata(
        self,
        *,
        id_tenant: str,
        id_workspace: str,
        id_assistant: str,
    ) -> WorkspaceMetadata:
        return WorkspaceMetadata(
            workspace_id=id_workspace,
            id_tenant=id_tenant,
            id_assistant=id_assistant,
        )


class _NoopLeaf(Agent[ArtemisInput, ArtemisFinalAnswer]):
    input = ArtemisInput
    output = ArtemisFinalAnswer
    role = "No-op leaf."
    task = "Return a fixed answer."

    async def forward(self, x: ArtemisInput) -> ArtemisFinalAnswer:
        return ArtemisFinalAnswer(
            utterance="Original answer.",
            intent_decision="DIRECT_ANSWER",
            final_step="conv_talker",
        )


class _MiniRunner(Agent[ArtemisInput, ArtemisFinalAnswer]):
    input = ArtemisInput
    output = ArtemisFinalAnswer

    def __init__(self, selfserve_root: Path) -> None:
        super().__init__(config=None, input=ArtemisInput, output=ArtemisFinalAnswer)
        self.retrieval = _AssertingRetrieval()
        self.noop = _NoopLeaf(config=None)
        self.reasoner = load_yaml(
            selfserve_root / "reasoner/agents/agent_reasoner.yaml",
            ReasonerLeaf,
        )
        self.conv_talker = load_yaml(
            selfserve_root / "reasoner/agents/agent_conversational_talker.yaml",
            ConversationalTalkerLeaf,
        )

    async def forward(self, x: ArtemisInput) -> ArtemisFinalAnswer:
        return (await self.noop(x)).response

    async def run_with_trace(
        self,
        x: ArtemisInput,
    ) -> tuple[ArtemisFinalAnswer, WorkflowTrace]:
        answer = ArtemisFinalAnswer(
            utterance="Original answer.",
            intent_decision="DIRECT_ANSWER",
            final_step="conv_talker",
        )
        return answer, WorkflowTrace(entry_id=x.entry.entry_id).seal()


@pytest.fixture
def selfserve_root(tmp_path: Path) -> Path:
    for relative_path, step_name in LEAF_STEP_NAMES.items():
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(YAML_FIXTURES / f"{step_name}.yaml", destination)
    return tmp_path


@pytest.fixture
def artemis_input() -> ArtemisInput:
    entry = DatasetEntry(workspace_id="workspace-1", user_message="How should I answer?")
    return ArtemisInput(
        entry=entry,
        workspace=WorkspaceMetadata(workspace_id=entry.workspace_id),
    )


@pytest.fixture
def feedback() -> HumanFeedback:
    return HumanFeedback(
        trace_id="trace",
        final_answer_critique="The final answer is too indirect.",
        desired_behavior="Answer directly.",
        severity=0.7,
    )


@pytest.fixture(autouse=True)
def _patch_optimizer(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def fake_tape():
        yield _FakeTape()

    monkeypatch.setattr(apply_fix_module.operad.optim.backprop, "tape", fake_tape)
    monkeypatch.setattr(
        apply_fix_module,
        "TextualGradientDescent",
        _FakeTextualGradientDescent,
    )

    class _OfflineAgent:
        async def abuild(self) -> "_OfflineAgent":
            return self

    def _offline_factory(*_args: Any, **_kwargs: Any) -> _OfflineAgent:
        return _OfflineAgent()

    monkeypatch.setattr(apply_fix_module, "BackpropAgent", _offline_factory)
    monkeypatch.setattr(apply_fix_module, "ParameterGradAgent", _offline_factory)
    monkeypatch.setattr(
        apply_fix_module,
        "tier_to_config",
        lambda *_a, **_kw: None,
    )


@pytest.mark.asyncio
async def test_apply_fix_mutates_only_target(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
) -> None:
    runner = _MiniRunner(selfserve_root)
    off_target_before = runner.conv_talker.state().model_dump(mode="json")

    report = await apply_fix(
        runner=runner,
        artemis_input=artemis_input,
        feedback=feedback,
        target_path="reasoner",
        yaml_root=selfserve_root,
    )

    assert report.diff_text
    assert report.before_state["task"] != report.after_state["task"]
    assert runner.reasoner.task == report.after_state["task"]
    assert runner.conv_talker.state().model_dump(mode="json") == off_target_before


@pytest.mark.asyncio
async def test_apply_fix_dry_run_does_not_write_yaml(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
) -> None:
    runner = _MiniRunner(selfserve_root)
    yaml_path = selfserve_root / "reasoner/agents/agent_reasoner.yaml"
    yaml_before = yaml_path.read_text(encoding="utf-8")
    task_before = runner.reasoner.task

    report = await apply_fix(
        runner=runner,
        artemis_input=artemis_input,
        feedback=feedback,
        target_path="reasoner",
        yaml_root=selfserve_root,
        dry_run=True,
    )

    assert report.yaml_dry_run is True
    assert yaml_path.read_text(encoding="utf-8") == yaml_before
    assert runner.reasoner.task == task_before
    assert report.before_state["task"] != report.after_state["task"]


@pytest.mark.asyncio
async def test_apply_fix_writes_yaml_when_not_dry(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
) -> None:
    runner = _MiniRunner(selfserve_root)

    report = await apply_fix(
        runner=runner,
        artemis_input=artemis_input,
        feedback=feedback,
        target_path="reasoner",
        yaml_root=selfserve_root,
    )

    reloaded = load_yaml(report.yaml_path, ReasonerLeaf)
    assert reloaded.hash_content == runner.reasoner.hash_content


@pytest.mark.asyncio
@pytest.mark.parametrize("target_path", ["control_flow", "data", "no_fault"])
async def test_apply_fix_raises_on_special_targets(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
    target_path: str,
) -> None:
    with pytest.raises(UnactionableFeedback):
        await apply_fix(
            runner=_MiniRunner(selfserve_root),
            artemis_input=artemis_input,
            feedback=feedback,
            target_path=target_path,
            yaml_root=selfserve_root,
        )


@pytest.mark.asyncio
async def test_apply_fix_no_network(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
) -> None:
    report = await apply_fix(
        runner=_MiniRunner(selfserve_root),
        artemis_input=artemis_input,
        feedback=feedback,
        target_path="reasoner",
        yaml_root=selfserve_root,
        dry_run=True,
    )

    assert report.diff_text


@pytest.mark.asyncio
async def test_apply_fix_diff_text_unified_format(
    selfserve_root: Path,
    artemis_input: ArtemisInput,
    feedback: HumanFeedback,
) -> None:
    report = await apply_fix(
        runner=_MiniRunner(selfserve_root),
        artemis_input=artemis_input,
        feedback=feedback,
        target_path="reasoner",
        yaml_root=selfserve_root,
        dry_run=True,
    )

    assert report.diff_text.startswith("--- reasoner:before\n+++ reasoner:after\n")
    assert "@@" in report.diff_text


def test_cmd_fix_uses_blame_json_when_target_absent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, trace = _write_run_dir(tmp_path, with_blame=True)
    captured: dict[str, Any] = {}
    _patch_cli(monkeypatch, tmp_path, captured)

    rc = main(
        [
            "fix",
            "--trace-id",
            trace.trace_id,
            "--selfserve-root",
            str(tmp_path),
            "--dry-run",
        ]
    )

    assert rc == 0
    assert captured["target_path"] == "reasoner"
    assert captured["critique"] == "Rewrite only the reasoner prompt."
    assert (run_dir / "fix.diff").read_text(encoding="utf-8") == "diff\n"


def test_cmd_fix_returns_2_when_no_target_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _run_dir, trace = _write_run_dir(tmp_path, with_blame=False)
    _patch_cli(monkeypatch, tmp_path, {})

    rc = main(
        [
            "fix",
            "--trace-id",
            trace.trace_id,
            "--selfserve-root",
            str(tmp_path),
            "--dry-run",
        ]
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert "no target" in captured.err


def test_cmd_fix_writes_run_dir_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_dir, trace = _write_run_dir(tmp_path, with_blame=False)
    _patch_cli(monkeypatch, tmp_path, {})

    rc = main(
        [
            "fix",
            "--trace-id",
            trace.trace_id,
            "--target",
            "reasoner",
            "--selfserve-root",
            str(tmp_path),
            "--dry-run",
        ]
    )

    assert rc == 0
    assert (run_dir / "fix.diff").read_text(encoding="utf-8") == "diff\n"
    payload = json.loads((run_dir / "fix.json").read_text(encoding="utf-8"))
    assert payload["target_path"] == "reasoner"
    assert "before_state" not in payload
    assert "after_state" not in payload


def _write_run_dir(tmp_path: Path, *, with_blame: bool) -> tuple[Path, WorkflowTrace]:
    run_dir = tmp_path / ".uthereal-runs" / "entry-1"
    run_dir.mkdir(parents=True)
    entry = DatasetEntry(workspace_id="workspace-1", user_message="Question?")
    (run_dir / "entry.json").write_text(
        json.dumps(entry.model_dump(mode="json"), sort_keys=True),
        encoding="utf-8",
    )
    trace = WorkflowTrace(
        entry_id=entry.entry_id,
        final_answer_text="Original answer.",
    ).seal()
    trace.to_jsonl(run_dir / "trace.jsonl")
    HumanFeedback(
        trace_id=trace.trace_id,
        final_answer_critique="Human critique.",
    ).to_json(run_dir / "feedback.json")
    if with_blame:
        blame = BlamerOutput(
            target_path="reasoner",
            rationale="The route rewrite is wrong.",
            leaf_targeted_critique="Rewrite only the reasoner prompt.",
            severity=0.4,
        )
        (run_dir / "blame.json").write_text(
            blame.model_dump_json(),
            encoding="utf-8",
        )
    return run_dir, trace


def _patch_cli(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    captured: dict[str, Any],
) -> None:
    monkeypatch.chdir(tmp_path)

    class FakeRunner:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

        async def abuild(self) -> "FakeRunner":
            return self

    async def fake_apply_fix(**kwargs: Any) -> FixReport:
        captured["target_path"] = kwargs["target_path"]
        captured["critique"] = kwargs["feedback"].final_answer_critique
        return FixReport(
            target_path=kwargs["target_path"],
            before_state={"task": "before"},
            after_state={"task": "after"},
            diff_text="diff\n",
            yaml_path=Path(kwargs["yaml_root"]) / "reasoner/agents/agent_reasoner.yaml",
            yaml_dry_run=kwargs["dry_run"],
            severity=kwargs["feedback"].severity,
        )

    monkeypatch.setattr(fix_cmd, "ArtemisRunner", FakeRunner)
    monkeypatch.setattr(fix_cmd, "apply_fix", fake_apply_fix)
