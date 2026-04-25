"""GET /api/manifest returns mode, version, and langfuseUrl."""

from __future__ import annotations

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
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "development"
        assert "version" in body
        assert body["langfuseUrl"] is None


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
