"""Deterministic hash helpers.

Two flavours of helpers live here:

- Generic primitives (``hash_str``, ``hash_json``) and reproducibility
  hashers (``hash_config``, ``hash_schema``) used by ``OperadOutput``
  envelope construction.
- Cassette keyers (``hash_model``, ``hash_prompt``, ``hash_input``) used
  by the record/replay layer.

All outputs are SHA-256 over stable JSON, truncated to 16 hex chars —
for correlation and audit, not cryptographic integrity.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from pydantic import BaseModel

from ..core.config import Configuration


def hash_str(s: str) -> str:
    """SHA-256 of `s`, truncated to 16 hex chars."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def hash_json(obj: Any) -> str:
    """Stable hash of a JSON-serialisable object."""
    return hash_str(json.dumps(obj, sort_keys=True, default=str))


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


# Matches a `user:pass@` authority prefix, with or without a leading scheme.
# Credentials embedded in `host` would otherwise be hashed verbatim, making
# identical deployments hash differently based on operator.
_HOST_AUTH_RE = re.compile(r"^(?P<scheme>[a-z][a-z0-9+.-]*://)?[^/@]+@")


def hash_config(config: Configuration | None) -> str:
    """Hash a `Configuration` with `api_key` excluded.

    The `host` field is additionally scrubbed of any embedded
    `user:pass@` authority so credentials never bleed into the
    reproducibility hash.
    """
    if config is None:
        return ""
    dumped = config.model_dump(mode="json", exclude={"api_key"})
    host = dumped.get("host")
    if isinstance(host, str):
        m = _HOST_AUTH_RE.match(host)
        if m:
            dumped["host"] = (m.group("scheme") or "") + host[m.end():]
    return hash_json(dumped)


def hash_schema(cls: type[BaseModel]) -> str:
    """Hash the JSON schema of a Pydantic model."""
    return hash_json(cls.model_json_schema())


def hash_model(cfg: Configuration) -> str:
    """Hash a Configuration for cassette keying. Excludes ``api_key``."""
    data = cfg.model_dump(mode="json", exclude={"api_key"})
    return hash_str(_stable_json(data))


def hash_prompt(
    system: str | list[dict[str, str]],
    user: str,
) -> str:
    """Hash a rendered (system, user) prompt pair.

    ``system`` may be either a rendered string (xml/markdown) or a
    list of ``{"role","content"}`` messages (chat renderer); both
    hash deterministically via stable JSON.
    """
    return hash_str(_stable_json({"system": system, "user": user}))


def hash_input(x: BaseModel) -> str:
    """Hash a typed input payload via its stable JSON dump."""
    return hash_str(_stable_json(x.model_dump(mode="json")))


__all__ = [
    "hash_config",
    "hash_input",
    "hash_json",
    "hash_model",
    "hash_prompt",
    "hash_schema",
    "hash_str",
]
