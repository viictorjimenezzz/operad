from __future__ import annotations

"""Filesystem paths shared by uthereal CLI commands.

Owner: 1-1-skeleton.
"""

from pathlib import Path


def runs_dir() -> Path:
    """Return the workspace-local uthereal runs directory, creating it lazily."""

    path = (Path.cwd() / ".uthereal-runs").resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_dir(entry_id: str) -> Path:
    """Return the run directory for ``entry_id``, creating it lazily."""

    path = runs_dir() / entry_id
    path.mkdir(parents=True, exist_ok=True)
    return path
