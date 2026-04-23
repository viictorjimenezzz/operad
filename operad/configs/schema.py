"""Pydantic schema for `operad run` YAML configs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..core.config import Backend, Configuration


class SlotSpec(BaseModel):
    backend: Backend
    host: str | None = None
    limit: int

    model_config = ConfigDict(extra="forbid")


class RuntimeSpec(BaseModel):
    slots: list[SlotSpec] = []

    model_config = ConfigDict(extra="forbid")


class OverrideSpec(BaseModel):
    role: str | None = None
    task: str | None = None
    rules: list[str] | None = None

    model_config = ConfigDict(extra="forbid")


class RunConfig(BaseModel):
    """Full YAML config: which agent, with what `Configuration` and overrides."""

    agent: str
    config: Configuration
    runtime: RuntimeSpec = RuntimeSpec()
    overrides: OverrideSpec = OverrideSpec()

    model_config = ConfigDict(extra="forbid")
