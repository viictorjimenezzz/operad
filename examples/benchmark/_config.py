"""Default Configuration for benchmark tasks.

Reads from environment variables so users can override without touching code:

    OPERAD_BACKEND   (default: anthropic)
    OPERAD_MODEL     (default: claude-haiku-4-5-20251001)
    OPERAD_API_KEY   (falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY etc.)

Any variable may be omitted; the Configuration constructor handles per-backend
key resolution automatically.
"""

from __future__ import annotations

import os

from operad import Configuration
from operad.core.config import Sampling


def default_config() -> Configuration:
    backend = os.environ.get("OPERAD_BACKEND", "anthropic")
    model = os.environ.get("OPERAD_MODEL", "claude-haiku-4-5-20251001")
    api_key = os.environ.get("OPERAD_API_KEY") or None
    return Configuration(
        backend=backend,
        model=model,
        api_key=api_key,
        sampling=Sampling(temperature=0.0, max_tokens=256),
    )
