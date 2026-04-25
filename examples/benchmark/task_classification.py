"""Task: intent classification.

10 banking intents, ~100 synthesized examples.
Primary metric: ExactMatch (label-level accuracy).
"""

from __future__ import annotations

from typing import Any

from operad import Agent
from operad.metrics import ExactMatch
from operad.optim.loss import LossFromMetric

from ._shared import (
    OFFLINE_CFG,
    IntentIn,
    IntentOut,
    OfflineIntentLeaf,
    make_classification_dataset,
)

DATASET = make_classification_dataset(n=100, seed=42)

METRICS = [ExactMatch()]

LOSS_FN = LossFromMetric(METRICS[0])


# ---------------------------------------------------------------------------
# Seed agent: minimal prompt, no rules
# ---------------------------------------------------------------------------

class _IntentClassifier(Agent[IntentIn, IntentOut]):
    input = IntentIn
    output = IntentOut
    role = "You are a customer-support intent classifier."
    task = (
        "Classify the customer message into exactly one of the following intents: "
        "check_balance, transfer_funds, report_card_lost, activate_card, change_pin, "
        "dispute_charge, close_account, open_account, update_address, request_statement."
    )
    rules: list[str] = []


class _IntentClassifierHandEdit(Agent[IntentIn, IntentOut]):
    input = IntentIn
    output = IntentOut
    role = "You are a precise customer-support intent classifier for a banking assistant."
    task = (
        "Given a customer message, output the single most appropriate intent label. "
        "Choose from exactly these ten labels: check_balance, transfer_funds, "
        "report_card_lost, activate_card, change_pin, dispute_charge, close_account, "
        "open_account, update_address, request_statement. Output the label verbatim."
    )
    rules = [
        "Output only the exact label string — no explanation, no punctuation.",
        "If the message mentions losing or theft, prefer report_card_lost over dispute_charge.",
        "If the message asks for transaction history or account records, use request_statement.",
    ]


def make_seed_agent(offline: bool = False) -> Agent[IntentIn, IntentOut]:
    if offline:
        return OfflineIntentLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _IntentClassifier(config=None)


def make_hand_edit_agent(offline: bool = False) -> Agent[IntentIn, IntentOut]:
    if offline:
        return OfflineIntentLeaf(config=OFFLINE_CFG.model_copy(deep=True))
    return _IntentClassifierHandEdit(config=None)


def make_sweep_grid() -> dict[str, list[Any]]:
    return {
        "config.sampling.temperature": [0.0, 0.3, 0.7],
        "task": [
            _IntentClassifier.task,
            _IntentClassifierHandEdit.task,
            (
                "Read the customer message and assign it one intent from this list: "
                "check_balance, transfer_funds, report_card_lost, activate_card, "
                "change_pin, dispute_charge, close_account, open_account, "
                "update_address, request_statement. Return only the label."
            ),
        ],
    }
