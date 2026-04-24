"""Shared config for network-backed examples.

All examples that talk to a real model server import `local_config()`.
Override via env vars if you have a different setup:

    OPERAD_LLAMACPP_HOST=127.0.0.1:9000
    OPERAD_LLAMACPP_MODEL=google/gemma-4-e4b
"""
from __future__ import annotations

import os
import socket

from operad import Configuration

DEFAULT_HOST = "127.0.0.1:9000"
DEFAULT_MODEL = "google/gemma-4-e4b"


def local_config(**overrides) -> Configuration:
    """Build a Configuration for the canonical local llama-server."""
    base: dict = dict(
        backend="llamacpp",
        host=os.environ.get("OPERAD_LLAMACPP_HOST", DEFAULT_HOST),
        model=os.environ.get("OPERAD_LLAMACPP_MODEL", DEFAULT_MODEL),
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
