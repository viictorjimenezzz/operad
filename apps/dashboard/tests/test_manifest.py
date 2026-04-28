"""GET /api/manifest returns runtime dashboard flags and paths."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


@pytest.fixture
def app_and_obs():
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    return app, obs


def test_manifest_default(app_and_obs, monkeypatch) -> None:
    monkeypatch.delenv("OPERAD_ENV", raising=False)
    monkeypatch.delenv("OPERAD_CASSETTE", raising=False)
    monkeypatch.delenv("OPERAD_CASSETTE_PATH", raising=False)
    monkeypatch.delenv("OPERAD_TRACE", raising=False)
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "development"
        assert "version" in body
        assert body["langfuseUrl"] is None
        assert body["cassetteMode"] is False
        assert body["cassettePath"] is None
        assert body["cassetteStale"] is False
        assert body["tracePath"] is None


def test_manifest_production_mode(app_and_obs, monkeypatch) -> None:
    monkeypatch.setenv("OPERAD_ENV", "production")
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.json()["mode"] == "production"


def test_manifest_langfuse_url(monkeypatch) -> None:
    monkeypatch.delenv("OPERAD_ENV", raising=False)
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False, langfuse_url="https://langfuse.example.com")
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.json()["langfuseUrl"] == "https://langfuse.example.com"


def test_manifest_includes_cassette_and_trace_paths(tmp_path: Path, monkeypatch) -> None:
    cassette = tmp_path / "trace.jsonl"
    cassette.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("OPERAD_CASSETTE", "record")
    monkeypatch.setenv("OPERAD_CASSETTE_PATH", str(cassette))
    monkeypatch.setenv("OPERAD_TRACE", "/tmp/operad-trace.jsonl")
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    with TestClient(app) as client:
        body = client.get("/api/manifest").json()
    assert body["cassetteMode"] is True
    assert body["cassettePath"] == str(cassette)
    assert body["tracePath"] == "/tmp/operad-trace.jsonl"


def test_manifest_marks_stale_cassette_when_older_than_sources(tmp_path: Path, monkeypatch) -> None:
    cassette = tmp_path / "old-cassette.jsonl"
    cassette.write_text("{}", encoding="utf-8")
    os.utime(cassette, (1, 1))
    monkeypatch.setenv("OPERAD_CASSETTE_PATH", str(cassette))
    obs = WebDashboardObserver()
    app = create_app(observer=obs, auto_register=False)
    with TestClient(app) as client:
        body = client.get("/api/manifest").json()
    assert body["cassetteStale"] is True
