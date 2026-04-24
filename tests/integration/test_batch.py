"""End-to-end batch submission against the OpenAI Batch API.

Opt-in: only runs when `OPERAD_INTEGRATION=batch`. Submits a tiny
batch and polls until done; requires a pre-uploaded input file.

    OPERAD_INTEGRATION=batch \\
    OPENAI_API_KEY=sk-... \\
    OPERAD_BATCH_INPUT_FILE_ID=file-... \\
    uv run pytest tests/integration/test_batch.py -v
"""

from __future__ import annotations

import asyncio
import os

import pytest

from operad import Configuration
from operad.core.models import BatchHandle, poll_batch, resolve_model


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("OPERAD_INTEGRATION") != "batch",
        reason="set OPERAD_INTEGRATION=batch to enable",
    ),
]


async def test_openai_batch_submit_and_poll() -> None:
    pytest.importorskip("openai")

    cfg = Configuration(
        backend="openai",
        model=os.environ.get("OPERAD_OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.environ["OPENAI_API_KEY"],
        batch=True,
    )
    model = resolve_model(cfg)
    handle = await model.forward(
        {
            "input_file_id": os.environ["OPERAD_BATCH_INPUT_FILE_ID"],
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
        }
    )
    assert isinstance(handle, BatchHandle)
    assert handle.provider == "openai"
    assert handle.provider_batch_id

    # Poll up to ~10 minutes (batches can take much longer; exit early if
    # still running — the purpose is wiring coverage, not completion time).
    for _ in range(60):
        result = await poll_batch(handle)
        if result is not None:
            assert result.status in {"completed", "failed", "cancelled"}
            return
        await asyncio.sleep(10)
