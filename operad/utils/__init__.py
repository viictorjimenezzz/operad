"""Small cross-cutting helpers shared by the foundation and plugins."""

from __future__ import annotations

from .errors import BuildError, BuildReason
from .hashing import (
    hash_config,
    hash_input,
    hash_json,
    hash_model,
    hash_prompt,
    hash_schema,
    hash_str,
)
from .ops import (
    AppendExample,
    AppendRule,
    CompoundOp,
    DropExample,
    DropRule,
    EditTask,
    Op,
    ReplaceRule,
    SetBackend,
    SetModel,
    SetTemperature,
    TweakRole,
)
from .paths import _resolve

__all__ = [
    "AppendExample",
    "AppendRule",
    "BuildError",
    "BuildReason",
    "CompoundOp",
    "DropExample",
    "DropRule",
    "EditTask",
    "Op",
    "ReplaceRule",
    "SetBackend",
    "SetModel",
    "SetTemperature",
    "TweakRole",
    "_resolve",
    "hash_config",
    "hash_input",
    "hash_json",
    "hash_model",
    "hash_prompt",
    "hash_schema",
    "hash_str",
]
