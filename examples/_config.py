"""Shared config for network-backed examples.

All examples that talk to a real model server import `local_config()`.
Override via env vars if you have a different setup:

    OPERAD_LLAMACPP_HOST=127.0.0.1:9000
    OPERAD_LLAMACPP_MODEL=google/gemma-4-e2b
"""
from __future__ import annotations

import os
import socket

from operad import Configuration

DEFAULT_HOST = "127.0.0.1:9000"
DEFAULT_MODEL = "google/gemma-4-e2b"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"


def local_config(**overrides) -> Configuration:
    """Build a Configuration for the canonical local llama-server.

    Accepts nested sub-model kwargs (``sampling=Sampling(...)``,
    ``resilience=Resilience(...)``, ``io=IOConfig(...)``,
    ``runtime=Runtime(...)``) as well as the top-level fields
    ``backend``, ``model``, ``host``, ``api_key``, ``batch``.
    """
    backend = os.environ.get("OPERAD_BACKEND", "llamacpp")
    base: dict = dict(
        backend=backend,
    )
    if backend == "gemini":
        base["model"] = os.environ.get(
            "OPERAD_GEMINI_MODEL",
            os.environ.get("OPERAD_MODEL", DEFAULT_GEMINI_MODEL),
        )
    else:
        base["host"] = os.environ.get("OPERAD_LLAMACPP_HOST", DEFAULT_HOST)
        base["model"] = os.environ.get(
            "OPERAD_LLAMACPP_MODEL",
            os.environ.get("OPERAD_MODEL", DEFAULT_MODEL),
        )
    base.update(overrides)
    return Configuration(**base)


def server_reachable(host: str, timeout: float = 0.5) -> bool:
    """Return True if a TCP connection to ``host`` (``h:p``) succeeds."""
    h, _, p = host.partition(":")
    try:
        with socket.create_connection((h, int(p)), timeout=timeout):
            return True
    except OSError:
        return False
