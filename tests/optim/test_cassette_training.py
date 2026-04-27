"""Cassette-replay validation for training runs (wave 5-5).

Proves that a full `Trainer.fit()` pass is byte-for-byte reproducible
against a recorded cassette: given the same seeds the final agent
state, every per-epoch `EpochReport`, every `Parameter.value`, and the
optimizer `state_dict` round-trip identically.

Two phases:

- **record** (manual, gated on ``OPERAD_INTEGRATION=llamacpp``):

      OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp \
          uv run pytest tests/optim/test_cassette_training.py -v

  Runs the loop against a real backend, appends to ``cassette_train.jsonl``,
  and writes the observed values to ``cassette_train.expected.json``.
  Both files are committed in the same PR.

- **replay** (CI default): runs the loop under the committed cassette,
  loads the sidecar, asserts byte-for-byte equality. Drift is reported
  as a structured diff naming the first diverging hash or parameter.

If the cassette or expected-values file is absent on a clean checkout,
the test skips rather than fails — recording is an opt-in manual step.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

import pytest
from pydantic import BaseModel, Field

from operad import Agent, Configuration
from operad.agents.reasoning.components.critic import Critic
from operad.benchmark.dataset import Dataset
from operad.benchmark.entry import Entry
from operad.core.config import Sampling
from operad.data.loader import DataLoader
from operad.optim.losses import JudgeLoss
from operad.optim.optimizers.tgd import TextualGradientDescent
from operad.train import Trainer
from operad.utils.cassette import cassette_context


SEED = 42
EPOCHS = 2
BATCH_SIZE = 2

CASSETTE_DIR = Path(__file__).parent / "_cassettes"
CASSETTE_PATH = CASSETTE_DIR / "cassette_train.jsonl"
EXPECTED_PATH = CASSETTE_DIR / "cassette_train.expected.json"


class Question(BaseModel):
    """A trivia prompt."""

    text: str = Field(default="", description="A factual trivia question.")


class Answer(BaseModel):
    """A concise factual answer."""

    text: str = Field(default="", description="A one-sentence factual answer.")


class FactualQA(Agent[Question, Answer]):
    """Minimal single-leaf trainable agent used by this test."""

    input = Question
    output = Answer
    role = "You are a factual assistant."
    task = "Answer the question in a single concise sentence."
    rules = (
        "Answer in one sentence.",
        "Do not include caveats or filler.",
    )


def _mode() -> Literal["record", "replay"]:
    m = os.environ.get("OPERAD_CASSETTE", "replay")
    if m not in ("record", "replay"):
        raise ValueError(
            f"OPERAD_CASSETTE must be 'record' or 'replay', got {m!r}"
        )
    return m  # type: ignore[return-value]


def _cfg() -> Configuration:
    return Configuration(
        backend="llamacpp",
        host="127.0.0.1:8080",
        model="test",
        sampling=Sampling(temperature=0.0, max_tokens=64, seed=SEED),
    )


def _dataset() -> Dataset[Question, Answer]:
    items = [
        ("What is the capital of France?", "Paris."),
        ("What planet is known as the Red Planet?", "Mars."),
        ("Who wrote the play 'Hamlet'?", "William Shakespeare."),
        ("What is the largest ocean on Earth?", "The Pacific Ocean."),
    ]
    entries = [
        Entry(input=Question(text=q), expected_output=Answer(text=a))
        for q, a in items
    ]
    return Dataset(entries, name="cassette_train_qa", version="v1")


def _canonical(obj: Any) -> Any:
    """Recursively sort dict keys so JSON bytes compare stably."""
    if isinstance(obj, BaseModel):
        return _canonical(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _canonical(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, (list, tuple)):
        return [_canonical(x) for x in obj]
    return obj


def _canonical_param_values(agent: Agent[Any, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, param in agent.named_parameters():
        out[path] = _canonical(param.value)
    return dict(sorted(out.items()))


def _observations(
    agent: Agent[Any, Any],
    optimizer: TextualGradientDescent,
    report: Any,
) -> dict[str, Any]:
    return _canonical(
        {
            "seed_hash_content": report.seed_hash_content,
            "best_hash_content": report.best_hash_content,
            "best_epoch": report.best_epoch,
            "epochs": [
                {
                    "epoch": e.epoch,
                    "train_loss": e.train_loss,
                    "val_loss": e.val_loss,
                    "val_metrics": dict(e.val_metrics),
                    "lr": list(e.lr),
                    "hash_content": e.hash_content,
                }
                for e in report.epochs
            ],
            "final_param_values": _canonical_param_values(agent),
            "optimizer_state": optimizer.state_dict(),
        }
    )


def _structured_diff(observed: dict[str, Any], expected: dict[str, Any]) -> str:
    """Name the first diverging hash / parameter for a failed replay."""
    lines: list[str] = []
    for key in ("seed_hash_content", "best_hash_content", "best_epoch"):
        if observed.get(key) != expected.get(key):
            lines.append(
                f"{key}: observed={observed.get(key)!r} "
                f"expected={expected.get(key)!r}"
            )
    obs_epochs = observed.get("epochs", [])
    exp_epochs = expected.get("epochs", [])
    if len(obs_epochs) != len(exp_epochs):
        lines.append(
            f"epoch count: observed={len(obs_epochs)} expected={len(exp_epochs)}"
        )
    for i, (o, e) in enumerate(zip(obs_epochs, exp_epochs)):
        if o != e:
            lines.append(f"first diverging epoch: {i}")
            for field in ("hash_content", "train_loss", "val_loss", "val_metrics"):
                if o.get(field) != e.get(field):
                    lines.append(
                        f"  {field}: observed={o.get(field)!r} "
                        f"expected={e.get(field)!r}"
                    )
            break
    obs_params = observed.get("final_param_values", {})
    exp_params = expected.get("final_param_values", {})
    for path in sorted(set(obs_params) | set(exp_params)):
        if obs_params.get(path) != exp_params.get(path):
            lines.append(
                f"param {path!r}: observed={obs_params.get(path)!r} "
                f"expected={exp_params.get(path)!r}"
            )
            break
    if observed.get("optimizer_state") != expected.get("optimizer_state"):
        lines.append("optimizer_state: diverged")
    return "\n".join(lines) if lines else "(no structural diff; bytes differ elsewhere)"


def _assert_or_record(
    mode: Literal["record", "replay"],
    observed: dict[str, Any],
    path: Path,
) -> None:
    if mode == "record":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(observed, indent=2, sort_keys=True) + "\n")
        return
    if not path.exists():
        pytest.skip(
            f"expected values file {path} not found; record first with "
            "OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp"
        )
    expected = json.loads(path.read_text())
    if observed != expected:
        raise AssertionError(
            "training-cassette replay drift:\n"
            + _structured_diff(observed, expected)
        )


@pytest.mark.asyncio
async def test_cassette_training_is_byte_deterministic() -> None:
    mode = _mode()
    if mode == "record" and os.environ.get("OPERAD_INTEGRATION") != "llamacpp":
        pytest.skip("record phase requires OPERAD_INTEGRATION=llamacpp")
    if mode == "replay" and not CASSETTE_PATH.exists():
        pytest.skip(
            f"cassette {CASSETTE_PATH} not found; record first with "
            "OPERAD_CASSETTE=record OPERAD_INTEGRATION=llamacpp"
        )

    cfg = _cfg()
    agent = FactualQA(config=cfg)
    agent.mark_trainable(role=True)
    await agent.abuild()

    critic = await Critic(config=cfg).abuild()

    dataset = _dataset()
    loader = DataLoader(
        dataset, batch_size=BATCH_SIZE, shuffle=True, seed=SEED
    )
    optimizer = TextualGradientDescent(
        agent.parameters(), lr=1.0, config=cfg
    )
    loss_fn = JudgeLoss(critic, null_threshold=1.0)
    trainer = Trainer(agent, optimizer, loss_fn)

    with cassette_context(CASSETTE_PATH, mode=mode):
        report = await trainer.fit(loader, val_ds=dataset, epochs=EPOCHS)

    observed = _observations(agent, optimizer, report)
    _assert_or_record(mode, observed, EXPECTED_PATH)


def test_cassette_training_file_has_no_secrets() -> None:
    """Committed cassette files must store hashes only, not prompts."""
    if not CASSETTE_DIR.exists():
        return
    for p in CASSETTE_DIR.glob("*.jsonl"):
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            assert set(entry.keys()) == {
                "key",
                "hash_model",
                "hash_prompt",
                "hash_input",
                "response_json",
                "recorded_at",
            }, f"unexpected fields in {p}: {sorted(entry.keys())}"
