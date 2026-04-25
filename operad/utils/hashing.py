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

import base64
import hashlib
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import PurePath
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from ..core.config import Configuration


def hash_str(s: str) -> str:
    """SHA-256 of `s`, truncated to 16 hex chars."""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def _canonicalize(obj: Any) -> Any:
    """JSON ``default`` that produces environment-independent representations.

    Stable types and their canonical forms:
    - ``datetime`` → ISO 8601 UTC (naive datetimes are assumed UTC)
    - ``date`` → ISO 8601 (YYYY-MM-DD)
    - ``Path`` / ``PurePath`` → POSIX string (forward slashes)
    - ``UUID`` → canonical hyphenated lowercase string
    - ``Decimal`` → exact decimal string
    - ``bytes`` / ``bytearray`` → base-64 string
    - ``set`` / ``frozenset`` → sorted list (elements must be JSON-native)
    - ``BaseModel`` → ``model_dump()`` (Python mode so nested types recurse here)

    Raises ``TypeError`` for any other type so that platform-specific
    ``str()`` representations never silently pollute a hash.
    """
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            return obj.replace(tzinfo=timezone.utc).isoformat()
        return obj.astimezone(timezone.utc).isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, PurePath):
        return obj.as_posix()
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, (bytes, bytearray)):
        return base64.b64encode(bytes(obj)).decode()
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    if isinstance(obj, BaseModel):
        # Python-mode dump keeps datetime/Path/etc. as Python objects so they
        # flow back through _canonicalize for UTC normalization and POSIX paths.
        return obj.model_dump()
    raise TypeError(
        f"Object of type {type(obj).__name__} is not JSON-serializable with a"
        " stable canonical form. Convert to a supported type before hashing."
    )


def hash_json(obj: Any) -> str:
    """Stable, environment-independent hash of a JSON-serialisable object.

    Uses a typed canonicalizer instead of ``default=str`` so that
    cross-platform ``str()`` differences (timezone names, locale separators,
    OS path separators) cannot affect the digest.  Raises ``TypeError`` for
    types with no deterministic representation.
    """
    return hash_str(json.dumps(obj, sort_keys=True, default=_canonicalize, separators=(",", ":")))


def _stable_json(obj: object) -> str:
    return json.dumps(obj, sort_keys=True, default=_canonicalize, separators=(",", ":"))


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
