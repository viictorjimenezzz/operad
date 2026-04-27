from __future__ import annotations

"""Map uthereal LLM tiers onto operad Gemini configurations.

The phase-1 tier model strings are:
- fast: gemini-2.5-flash
- thinking_low: gemini-2.5-pro
- thinking_high: gemini-2.5-pro-thinking

Owner: 1-1-skeleton.
"""

import os
from typing import Any

from operad import Configuration
from operad.core.config import Sampling

from apps_uthereal.errors import LoaderError


TIER_FAST: str = "fast"
TIER_THINKING_LOW: str = "thinking_low"
TIER_THINKING_HIGH: str = "thinking_high"
RECOGNIZED_TIERS: frozenset[str] = frozenset(
    {TIER_FAST, TIER_THINKING_LOW, TIER_THINKING_HIGH}
)

_MODEL_BY_TIER: dict[str, str] = {
    TIER_FAST: "gemini-2.5-flash",
    TIER_THINKING_LOW: "gemini-2.5-pro",
    TIER_THINKING_HIGH: "gemini-2.5-pro-thinking",
}


def tier_to_config(
    tier: str,
    *,
    overrides: dict[str, Any] | None = None,
) -> Configuration:
    """Map a uthereal `llm_tier` to a Gemini-backed operad Configuration.

    Raises `LoaderError(reason="unknown_tier", tier=tier)` for unknown values.
    `overrides` is a flat dict of attribute paths, such as
    `{"sampling.temperature": 0.0}`, applied after the base config is built.
    """

    model = _MODEL_BY_TIER.get(tier)
    if model is None:
        raise LoaderError(reason="unknown_tier", tier=tier)

    kwargs: dict[str, Any] = {
        "backend": "gemini",
        "model": model,
        "sampling": Sampling(temperature=0.0, max_tokens=2048),
    }
    if not os.environ.get("GOOGLE_API_KEY") and not os.environ.get(
        "GOOGLE_VERTEX_AI_SERVICE_ACCOUNT"
    ):
        kwargs["api_key"] = "apps-uthereal-placeholder"

    config = Configuration(**kwargs)
    for path, value in (overrides or {}).items():
        _set_path(config, path, value)
    return config


def _set_path(root: object, path: str, value: Any) -> None:
    parent: object = root
    segments = path.split(".")
    for segment in segments[:-1]:
        parent = getattr(parent, segment)
    setattr(parent, segments[-1], value)
