"""Tests for `/runs/{id}/...` agent-view endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


_GRAPH_JSON = {
    "root": "Pipeline",
    "nodes": [
        {
            "path": "Pipeline",
            "input": "tests._helpers.fake_leaf.A",
            "output": "tests._helpers.fake_leaf.B",
            "kind": "composite",
        },
        {
            "path": "Pipeline.stage_0",
            "input": "tests._helpers.fake_leaf.A",
            "output": "tests._helpers.fake_leaf.B",
            "kind": "leaf",
        },
    ],
    "edges": [
        {
            "caller": "Pipeline",
            "callee": "Pipeline.stage_0",
            "input": "tests._helpers.fake_leaf.A",
            "output": "tests._helpers.fake_leaf.B",
        }
    ],
}


def _component_meta(*, prompt_system: str, prompt_user: str, renderer: str = "xml") -> dict:
    return {
        "class_name": "FakeLeaf",
        "kind": "leaf",
        "hash_content": "deadbeefcafefeed",
        "role": "Role",
        "task": "Task",
        "rules": ["r1", "r2"],
        "examples": [{"input": {"text": "x"}, "output": {"value": 1}}],
        "config": {
            "backend": "llamacpp",
            "model": "test",
            "sampling": {"temperature": 0.0},
            "resilience": {},
            "io": {"renderer": renderer},
            "runtime": {},
        },
        "forward_in_overridden": False,
        "forward_out_overridden": False,
        "forward_in_doc": "input hook docs",
        "forward_out_doc": "output hook docs",
        "trainable_paths": ["role", "task"],
        "prompt_system": prompt_system,
        "prompt_user": prompt_user,
    }


def _run_envelopes(run_id: str = "run-live") -> list[dict]:
    return [
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline",
            "kind": "start",
            "input": {"text": "seed"},
            "output": None,
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {"is_root": True, "script": "demo.py", "graph": _GRAPH_JSON},
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline.stage_0",
            "kind": "start",
            "input": {"text": "q1"},
            "output": None,
            "started_at": 10.0,
            "finished_at": None,
            "metadata": {},
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline.stage_0",
            "kind": "end",
            "input": {"text": "q1"},
            "output": {
                "response": {"value": 1},
                "hash_prompt": "p1",
                "hash_input": "i1",
                "prompt_tokens": 10,
                "completion_tokens": 5,
            },
            "started_at": 10.0,
            "finished_at": 11.0,
            "metadata": _component_meta(prompt_system="<role>a</role>", prompt_user="<input>q1</input>"),
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline.stage_0",
            "kind": "start",
            "input": {"text": "q2"},
            "output": None,
            "started_at": 20.0,
            "finished_at": None,
            "metadata": {},
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline.stage_0",
            "kind": "end",
            "input": {"text": "q2"},
            "output": {
                "response": {"value": 2},
                "hash_prompt": "p2",
                "hash_input": "i2",
                "prompt_tokens": 20,
                "completion_tokens": 6,
            },
            "started_at": 20.0,
            "finished_at": 21.0,
            "metadata": _component_meta(prompt_system="<role>b</role>", prompt_user="<input>q2</input>"),
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Pipeline",
            "kind": "end",
            "input": {"text": "seed"},
            "output": {
                "response": {"value": 2},
                "hash_prompt": "pr",
                "hash_input": "ir",
                "prompt_tokens": 1,
                "completion_tokens": 1,
            },
            "started_at": 1.0,
            "finished_at": 22.0,
            "metadata": {
                "is_root": True,
                "output_type": "tests._helpers.fake_leaf.B",
                **_component_meta(prompt_system="<role>root</role>", prompt_user="<input>seed</input>"),
            },
            "error": None,
        },
    ]


@pytest.fixture
def app_and_obs(tmp_path: Path):
    obs = WebDashboardObserver()
    app = create_app(
        observer=obs,
        auto_register=False,
        data_dir=tmp_path,
        langfuse_url="http://lf.example",
    )
    return app, obs


def _seed_live(client: TestClient, run_id: str = "run-live") -> None:
    r = client.post("/_ingest", json=_run_envelopes(run_id))
    assert r.status_code == 200


def test_live_io_graph_invocations_meta_prompts_values_events(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)

        io_graph = client.get("/runs/run-live/io_graph")
        assert io_graph.status_code == 200
        assert io_graph.json()["root"] == "Pipeline"
        assert io_graph.json()["edges"][0]["agent_path"] == "Pipeline.stage_0"

        root_inv = client.get("/runs/run-live/invocations")
        assert root_inv.status_code == 200
        assert root_inv.json()["agent_path"] == "Pipeline"
        assert len(root_inv.json()["invocations"]) == 1
        assert root_inv.json()["invocations"][0]["langfuse_url"] == "http://lf.example/trace/run-live"

        inv = client.get("/runs/run-live/agent/Pipeline.stage_0/invocations")
        assert inv.status_code == 200
        rows = inv.json()["invocations"]
        assert len(rows) == 2
        assert rows[0]["hash_prompt"] == "p1"
        assert rows[1]["hash_prompt"] == "p2"

        meta = client.get("/runs/run-live/agent/Pipeline.stage_0/meta")
        assert meta.status_code == 200
        body = meta.json()
        assert body["class_name"] == "FakeLeaf"
        assert body["kind"] == "leaf"
        assert body["forward_in_overridden"] is False
        assert body["forward_in_doc"] == "input hook docs"
        assert body["forward_out_doc"] == "output hook docs"
        assert body["trainable_paths"] == ["role", "task"]
        assert body["langfuse_search_url"] == "http://lf.example/traces?search=Pipeline.stage_0"

        prompts = client.get("/runs/run-live/agent/Pipeline.stage_0/prompts")
        assert prompts.status_code == 200
        payload = prompts.json()
        assert payload["renderer"] == "xml"
        assert len(payload["entries"]) == 2
        assert payload["entries"][0]["replayed"] is True
        assert payload["entries"][0]["system"] == "<role>a</role>"

        values = client.get("/runs/run-live/agent/Pipeline.stage_0/values?attr=text&side=in")
        assert values.status_code == 200
        vals = values.json()["values"]
        assert [v["value"] for v in vals] == ["q1", "q2"]

        events = client.get("/runs/run-live/agent/Pipeline.stage_0/events?limit=1")
        assert events.status_code == 200
        assert len(events.json()["events"]) == 1
        assert events.json()["events"][0]["kind"] == "end"


def test_archived_run_parity(app_and_obs) -> None:
    app, obs = app_and_obs
    with TestClient(app) as client:
        _seed_live(client, run_id="run-arch")
        info = obs.registry.get("run-arch")
        assert info is not None
        app.state.archive_store.upsert_snapshot(info)
        obs.registry.clear()

        assert client.get("/runs/run-arch/io_graph").status_code == 200
        assert client.get("/runs/run-arch/invocations").status_code == 200
        assert client.get("/runs/run-arch/agent/Pipeline.stage_0/meta").status_code == 200
        assert client.get("/runs/run-arch/agent/Pipeline.stage_0/invocations").status_code == 200
        assert client.get("/runs/run-arch/agent/Pipeline.stage_0/prompts").status_code == 200
        assert client.get("/runs/run-arch/agent/Pipeline.stage_0/values?attr=text&side=in").status_code == 200
        assert client.get("/runs/run-arch/agent/Pipeline.stage_0/events").status_code == 200


def test_404_unknown_path_and_attribute(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        r1 = client.get("/runs/run-live/agent/nope/meta")
        assert r1.status_code == 404
        assert r1.json()["error"] == "not_found"
        assert "reason" in r1.json()

        r2 = client.get("/runs/run-live/agent/Pipeline.stage_0/values?attr=missing&side=in")
        assert r2.status_code == 404
        assert r2.json()["error"] == "not_found"

        r3 = client.get("/runs/nope/io_graph")
        assert r3.status_code == 404
        assert r3.json()["error"] == "not_found"


def test_values_wrong_side_returns_clear_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        r = client.get("/runs/run-live/agent/Pipeline.stage_0/values?attr=text&side=out")
        assert r.status_code == 404
        assert r.json()["error"] == "not_found"


def test_io_graph_empty_when_graph_missing(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.post(
            "/_ingest",
            json={
                "type": "agent_event",
                "run_id": "nograph",
                "agent_path": "Pipeline",
                "kind": "start",
                "input": {"text": "x"},
                "output": None,
                "started_at": 1.0,
                "finished_at": None,
                "metadata": {"is_root": True},
                "error": None,
            },
        )
        assert r.status_code == 200
        out = client.get("/runs/nograph/io_graph")
        assert out.status_code == 200
        assert out.json() == {"root": None, "nodes": [], "edges": []}
