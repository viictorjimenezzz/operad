from __future__ import annotations

"""Tests for uthereal tier configuration mapping.

Owner: 1-1-skeleton.
"""

import pytest

from apps_uthereal.errors import LoaderError
from apps_uthereal.tiers import (
    TIER_FAST,
    TIER_THINKING_HIGH,
    TIER_THINKING_LOW,
    tier_to_config,
)


@pytest.mark.parametrize(
    "tier",
    [TIER_FAST, TIER_THINKING_LOW, TIER_THINKING_HIGH],
)
def test_tier_to_config_returns_gemini_for_each_tier(tier: str) -> None:
    cfg = tier_to_config(tier)

    assert cfg.backend == "gemini"
    assert cfg.sampling.temperature == 0.0
    assert cfg.sampling.max_tokens == 2048


def test_tier_to_config_unknown_tier_raises_LoaderError() -> None:
    with pytest.raises(LoaderError) as exc_info:
        tier_to_config("nonsense")

    assert exc_info.value.reason == "unknown_tier"
    assert exc_info.value.details == {"tier": "nonsense"}


def test_tier_to_config_overrides_apply() -> None:
    cfg = tier_to_config(
        TIER_FAST,
        overrides={"sampling.temperature": 0.5},
    )

    assert cfg.sampling.temperature == 0.5
