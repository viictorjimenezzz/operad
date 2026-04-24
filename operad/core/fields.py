"""System/user routing for Pydantic input fields.

An input field is marked as *system* by setting
``json_schema_extra={"operad": {"system": True}}`` on its ``Field(...)``.
System-flagged fields are rendered into the system prompt at call time;
unmarked fields render into the user message. Back-compat: when no field
carries the marker, :func:`split_fields` returns ``([], all_names)`` and
behaviour is identical to the pre-marker renderer.

The marker namespace is ``"operad"`` so it cannot collide with unrelated
``json_schema_extra`` keys a user might add for their own schema tooling.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic.fields import FieldInfo


_NAMESPACE = "operad"


def is_system_field(info: FieldInfo) -> bool:
    """True iff ``info`` carries the ``operad.system`` marker."""
    extra = info.json_schema_extra
    if not isinstance(extra, dict):
        return False
    bucket = extra.get(_NAMESPACE)
    if not isinstance(bucket, dict):
        return False
    return bool(bucket.get("system"))


def split_fields(model_cls: type[BaseModel]) -> tuple[list[str], list[str]]:
    """Return ``(system_field_names, user_field_names)`` in declaration order."""
    sys_names: list[str] = []
    usr_names: list[str] = []
    for name, info in model_cls.model_fields.items():
        (sys_names if is_system_field(info) else usr_names).append(name)
    return sys_names, usr_names


__all__ = ["is_system_field", "split_fields"]
