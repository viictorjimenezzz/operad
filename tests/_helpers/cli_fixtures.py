"""Importable Agent fixtures for the CLI tests.

Placed here (not in `conftest.py`) so it can be referenced by
fully-qualified dotted path from a YAML file via `importlib`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from operad.core.agent import Agent


class CLIInput(BaseModel):
    text: str = Field(default="", description="Input text.")


class CLIOutput(BaseModel):
    echoed: str = Field(default="", description="Echoed text.")


class DummyAgent(Agent[CLIInput, CLIOutput]):
    """Offline leaf used by CLI tests: echoes `text` into `echoed`."""

    input = CLIInput
    output = CLIOutput

    async def forward(self, x: CLIInput) -> CLIOutput:  # type: ignore[override]
        return CLIOutput(echoed=x.text)
