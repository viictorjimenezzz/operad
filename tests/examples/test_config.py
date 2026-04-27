"""Tests for shared example configuration helpers."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


EXAMPLES_DIR = Path(__file__).resolve().parent.parent.parent / "examples"


def _load_config_module() -> Any:
    path = EXAMPLES_DIR / "_config.py"
    spec = importlib.util.spec_from_file_location("examples._config", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_host_port_accepts_bare_host_and_url_forms() -> None:
    cfg = _load_config_module()

    assert cfg._host_port("127.0.0.1") == ("127.0.0.1", 9000)
    assert cfg._host_port("127.0.0.1:8080") == ("127.0.0.1", 8080)
    assert cfg._host_port("http://localhost:7777") == ("localhost", 7777)
    assert cfg._host_port("http://localhost") == ("localhost", 9000)


def test_server_reachable_returns_false_for_bad_host_port() -> None:
    cfg = _load_config_module()

    assert cfg.server_reachable("127.0.0.1:not-a-port") is False
    assert cfg.server_reachable("") is False


def test_server_reachable_uses_default_port_for_bare_host(monkeypatch: Any) -> None:
    cfg = _load_config_module()
    calls: list[tuple[tuple[str, int], float]] = []

    class _Socket:
        def __enter__(self) -> "_Socket":
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    def _connect(target: tuple[str, int], *, timeout: float) -> _Socket:
        calls.append((target, timeout))
        return _Socket()

    monkeypatch.setattr(cfg.socket, "create_connection", _connect)

    assert cfg.server_reachable("127.0.0.1") is True
    assert calls == [(("127.0.0.1", 9000), 0.5)]
