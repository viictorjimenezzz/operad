"""Deterministic hash helpers for cassette keying.

These live here temporarily; the ``feature-operad-output`` stream will
own the canonical versions on ``OperadOutput``. The shape must stay
compatible: sha256 over stable JSON, truncated to 16 hex characters.

``hash_model`` excludes ``api_key`` so that the same prompt cassette can
be shared across developers without leaking credentials through the
hash pre-image.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel

from ..core.config import Configuration


def _digest(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def hash_model(cfg: Configuration) -> str:
    """Hash a Configuration for cassette keying. Excludes ``api_key``."""
    data = cfg.model_dump(mode="json", exclude={"api_key"})
    return _digest(_stable_json(data))


def hash_prompt(
    system: str | list[dict[str, str]],
    user: str,
) -> str:
    """Hash a rendered (system, user) prompt pair.

    ``system`` may be either a rendered string (xml/markdown) or a
    list of ``{"role","content"}`` messages (chat renderer); both
    hash deterministically via stable JSON.
    """
    return _digest(_stable_json({"system": system, "user": user}))


def hash_input(x: BaseModel) -> str:
    """Hash a typed input payload via its stable JSON dump."""
    return _digest(_stable_json(x.model_dump(mode="json")))
