"""End-to-end smoke test against a local HuggingFace model.

Opt-in: only runs when `OPERAD_INTEGRATION=huggingface`. Downloads a
tiny 135M-param model on first run.

    OPERAD_INTEGRATION=huggingface \\
    OPERAD_HF_MODEL=HuggingFaceTB/SmolLM2-135M \\
    uv run pytest tests/integration/test_huggingface.py -v
"""

from __future__ import annotations

import os

import pytest

from operad import Configuration
from operad.core.models import resolve_model


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "huggingface",
        reason="set OPERAD_INTEGRATION=huggingface to enable",
    ),
]


async def test_huggingface_tiny_generation() -> None:
    pytest.importorskip("transformers")
    pytest.importorskip("torch")

    cfg = Configuration(
        backend="huggingface",
        model=os.environ.get("OPERAD_HF_MODEL", "HuggingFaceTB/SmolLM2-135M"),
        temperature=0.0,
        max_tokens=16,
    )
    model = resolve_model(cfg)
    out = await model.forward("The capital of France is")
    assert isinstance(out, str)
    assert len(out) > 0
