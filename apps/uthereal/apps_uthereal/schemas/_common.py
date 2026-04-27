from __future__ import annotations

"""Vendored shared schema primitives.

Drift is monitored by `make schemas-check` (advisory, not blocking).

Owner: 1-2-vendored-schemas.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


def operad_extra(
    *,
    system: bool | None = None,
    optional: bool | None = None,
    modality: str | None = None,
) -> dict[str, dict[str, bool | str]]:
    """Return YAML field metadata in operad's schema-extension namespace."""

    metadata: dict[str, bool | str] = {}
    if system is not None:
        metadata["system"] = system
    if optional is not None:
        metadata["optional"] = optional
    if modality is not None:
        metadata["modality"] = modality
    return {"operad": metadata}


class ImageRef(BaseModel):
    """Vendored from uthereal_core.agent.image.ImageRef."""

    label: str | None = Field(default=None, description="Optional label for the image.")
    uri: str | None = Field(default=None, description="Local, remote, data, or object-storage URI.")
    data: bytes | None = Field(default=None, description="Inline image bytes.")
    media_type: str = Field(default="image/png", description="Media type of the image.")

    model_config = ConfigDict(frozen=True)


class MessageTurn(BaseModel):
    """One rendered chat-history turn."""

    role: Literal["user", "assistant", "system"] = Field(default="user", description="Turn author.")
    content: str = Field(default="", description="Rendered turn content.")

    model_config = ConfigDict(frozen=True)
