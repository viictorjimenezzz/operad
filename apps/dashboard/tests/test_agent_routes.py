"""Tests for `/runs/{id}/...` agent-view endpoints."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from operad import Agent, Configuration
from operad_dashboard import agent_routes
from operad_dashboard.app import create_app
from operad_dashboard.observer import WebDashboardObserver


class A(BaseModel):
    text: str


class B(BaseModel):
    value: int = 0


class FakeLeaf(Agent[A, B]):
    input = A
    output = B

    async def forward(self, x: A) -> B:
        return B(value=7)


_GRAPH_JSON = {
    "root": "Sequential",
    "nodes": [
        {
            "path": "Sequential",
            "input": "tests._helpers.fake_leaf.A",
            "output": "tests._helpers.fake_leaf.B",
            "kind": "composite",
        },
        {
            "path": "Sequential.stage_0",
            "input": "tests._helpers.fake_leaf.A",
            "output": "tests._helpers.fake_leaf.B",
            "kind": "leaf",
        },
    ],
    "edges": [
        {
            "caller": "Sequential",
            "callee": "Sequential.stage_0",
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
        "state_snapshot": {
            "class_name": "FakeLeaf",
            "role": "Role",
            "task": "Task",
            "style": "",
            "context": "",
            "rules": ["r1", "r2"],
            "examples": [{"input": {"text": "x"}, "output": {"value": 1}}],
            "config": {
                "backend": "llamacpp",
                "host": "127.0.0.1:8080",
                "model": "test",
                "sampling": {"temperature": 0.0},
                "resilience": {},
                "io": {"renderer": renderer},
                "runtime": {},
            },
            "input_type_name": "tests._helpers.fake_leaf.A",
            "output_type_name": "tests._helpers.fake_leaf.B",
            "children": {},
        },
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
        "parameters": [
            {
                "path": "role",
                "type": "TextParameter",
                "value": "Role",
                "requires_grad": True,
                "grad": {
                    "message": "clarify role constraints",
                    "severity": 0.4,
                    "target_paths": ["role"],
                    "by_field": {"role": "clarify role constraints"},
                },
                "constraint": {"kind": "text", "max_length": 200, "forbidden": []},
            },
            {
                "path": "task",
                "type": "TextParameter",
                "value": "Task",
                "requires_grad": True,
                "grad": None,
                "constraint": None,
            },
            {
                "path": "style",
                "type": "TextParameter",
                "value": "",
                "requires_grad": False,
                "grad": None,
                "constraint": None,
            },
        ],
        "prompt_system": prompt_system,
        "prompt_user": prompt_user,
    }


def _run_envelopes(run_id: str = "run-live") -> list[dict]:
    meta_first = _component_meta(prompt_system="<role>a</role>", prompt_user="<input>q1</input>")
    meta_first["hash_content"] = "hash-a"
    if isinstance(meta_first.get("state_snapshot"), dict):
        meta_first["state_snapshot"]["role"] = "Role v1"
    if isinstance(meta_first.get("parameters"), list):
        meta_first["parameters"][0]["value"] = "Role v1"
    meta_second = _component_meta(prompt_system="<role>b</role>", prompt_user="<input>q2</input>")
    meta_second["hash_content"] = "hash-b"
    if isinstance(meta_second.get("state_snapshot"), dict):
        meta_second["state_snapshot"]["role"] = "Role v2"
        meta_second["state_snapshot"]["rules"] = ["r1", "r2", "r3"]
    if isinstance(meta_second.get("parameters"), list):
        meta_second["parameters"][0]["value"] = "Role v2"
        meta_second["parameters"][0]["grad"] = {
            "message": "tighten role wording",
            "severity": 0.7,
            "target_paths": ["role"],
            "by_field": {"role": "tighten role wording"},
        }
    return [
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Sequential",
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
            "agent_path": "Sequential.stage_0",
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
            "agent_path": "Sequential.stage_0",
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
            "metadata": meta_first,
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Sequential.stage_0",
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
            "agent_path": "Sequential.stage_0",
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
            "metadata": meta_second,
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": run_id,
            "agent_path": "Sequential",
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
        assert io_graph.json()["root"] == "Sequential"
        assert io_graph.json()["edges"][0]["agent_path"] == "Sequential.stage_0"

        root_inv = client.get("/runs/run-live/invocations")
        assert root_inv.status_code == 200
        assert root_inv.json()["agent_path"] == "Sequential"
        assert len(root_inv.json()["invocations"]) == 1
        assert root_inv.json()["invocations"][0]["langfuse_url"] == "http://lf.example/trace/run-live"
        assert root_inv.json()["invocations"][0]["config"]["model"] == "test"
        assert root_inv.json()["invocations"][0]["prompt_system"] == "<role>root</role>"
        assert root_inv.json()["invocations"][0]["prompt_user"] == "<input>seed</input>"

        inv = client.get("/runs/run-live/agent/Sequential.stage_0/invocations")
        assert inv.status_code == 200
        rows = inv.json()["invocations"]
        assert len(rows) == 2
        assert rows[0]["hash_prompt"] == "p1"
        assert rows[1]["hash_prompt"] == "p2"
        assert rows[0]["config"]["io"]["renderer"] == "xml"
        assert rows[0]["prompt_system"] == "<role>a</role>"
        assert rows[0]["prompt_user"] == "<input>q1</input>"

        meta = client.get("/runs/run-live/agent/Sequential.stage_0/meta")
        assert meta.status_code == 200
        body = meta.json()
        assert body["class_name"] == "FakeLeaf"
        assert body["kind"] == "leaf"
        assert body["forward_in_overridden"] is False
        assert body["forward_in_doc"] == "input hook docs"
        assert body["forward_out_doc"] == "output hook docs"
        assert body["trainable_paths"] == ["role", "task"]
        assert body["langfuse_search_url"] == "http://lf.example/traces?search=Sequential.stage_0"

        prompts = client.get("/runs/run-live/agent/Sequential.stage_0/prompts")
        assert prompts.status_code == 200
        payload = prompts.json()
        assert payload["renderer"] == "xml"
        assert len(payload["entries"]) == 2
        assert payload["entries"][0]["replayed"] is True
        assert payload["entries"][0]["system"] == "<role>a</role>"

        values = client.get("/runs/run-live/agent/Sequential.stage_0/values?attr=text&side=in")
        assert values.status_code == 200
        vals = values.json()["values"]
        assert [v["value"] for v in vals] == ["q1", "q2"]

        events = client.get("/runs/run-live/agent/Sequential.stage_0/events?limit=1")
        assert events.status_code == 200
        assert len(events.json()["events"]) == 1
        assert events.json()["events"][0]["kind"] == "end"

        params = client.get("/runs/run-live/agent/Sequential.stage_0/parameters")
        assert params.status_code == 200
        assert params.json()["agent_path"] == "Sequential.stage_0"
        rows = params.json()["parameters"]
        assert len(rows) == 2
        assert rows[0]["path"] == "role"
        assert rows[0]["type"] == "TextParameter"
        assert rows[0]["requires_grad"] is True
        assert rows[0]["constraint"] == {"kind": "text", "max_length": 200, "forbidden": []}
        assert "tape_link" in rows[0]
        assert "gradient" in rows[0]

        diff = client.get(
            "/runs/run-live/agent/Sequential.stage_0/diff?from=Sequential.stage_0:0&to=Sequential.stage_0:1"
        )
        assert diff.status_code == 200
        body = diff.json()
        assert body["from_invocation"] == "Sequential.stage_0:0"
        assert body["to_invocation"] == "Sequential.stage_0:1"
        assert body["from_hash_content"] == "hash-a"
        assert body["to_hash_content"] == "hash-b"
        assert len(body["changes"]) > 0


def test_group_summaries_are_runtime_enriched_and_duration_uses_finished_at(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)

        summary = client.get("/runs/run-live/summary")
        assert summary.status_code == 200
        assert summary.json()["duration_ms"] == pytest.approx(21_000.0)

        group = client.get("/api/agents/deadbeefcafefeed")
        assert group.status_code == 200
        body = group.json()
        assert body["latencies"] == [pytest.approx(21_000.0)]
        run = body["runs"][0]
        assert run["backend"] == "llamacpp"
        assert run["model"] == "test"
        assert run["sampling"] == {"temperature": 0.0}
        assert run["hash_content"] == "deadbeefcafefeed"
        assert run["hash_prompt"] == "pr"
        assert run["hash_input"] == "ir"
        assert run["hash_config"]


def test_agent_group_reproducibility_returns_common_hashes_only(app_and_obs) -> None:
    app, _ = app_and_obs
    first = _run_envelopes("run-a")
    second = _run_envelopes("run-b")
    for env in second:
        if env.get("agent_path") != "Sequential" or env.get("kind") != "end":
            continue
        output = env.get("output")
        if isinstance(output, dict):
            output["hash_prompt"] = "prompt-varies"
            output["hash_input"] = "input-varies"

    with TestClient(app) as client:
        assert client.post("/_ingest", json=first).status_code == 200
        assert client.post("/_ingest", json=second).status_code == 200

        response = client.get("/api/agents/deadbeefcafefeed/reproducibility")

    assert response.status_code == 200
    body = response.json()
    hashes = body["hashes"]
    assert body["count"] == 2
    assert hashes["hash_content"] == "deadbeefcafefeed"
    assert hashes["hash_prompt_template"]
    assert hashes["hash_input_schema"]
    assert hashes["hash_config"]
    assert "hash_prompt" not in hashes
    assert "hash_input" not in hashes


def test_agent_invocations_flat_includes_evo_metadata(app_and_obs) -> None:
    app, _ = app_and_obs
    envelopes = _run_envelopes("evo-run")
    envelopes.insert(
        0,
        {
            "type": "algo_event",
            "run_id": "evo-run",
            "algorithm_path": "EvoGradient",
            "kind": "generation",
            "payload": {
                "gen_index": 0,
                "population_scores": [0.4, 0.9],
                "survivor_indices": [1],
                "selected_lineage_id": "l1",
                "individuals": [
                    {
                        "individual_id": 0,
                        "lineage_id": "l0",
                        "parent_lineage_id": None,
                        "score": 0.4,
                        "selected": False,
                        "op": "append_rule",
                        "path": "rules",
                        "improved": False,
                        "parameter_deltas": [],
                    },
                    {
                        "individual_id": 1,
                        "lineage_id": "l1",
                        "parent_lineage_id": None,
                        "score": 0.9,
                        "selected": True,
                        "op": "replace_rule",
                        "path": "rules",
                        "improved": True,
                        "parameter_deltas": [],
                    },
                ],
                "mutations": [],
                "op_attempt_counts": {"append_rule": 1, "replace_rule": 1},
                "op_success_counts": {"replace_rule": 1},
            },
            "started_at": 9.0,
            "finished_at": None,
            "metadata": {},
        },
    )
    for env in envelopes:
        if env.get("agent_path") != "Sequential.stage_0":
            continue
        metadata = env.setdefault("metadata", {})
        if isinstance(metadata, dict):
            metadata.update(
                {
                    "invoke_id": "candidate-1",
                    "gen_index": 0,
                    "individual_id": 1,
                    "lineage_id": "l1",
                    "operator": "replace_rule",
                    "mutation_path": "rules",
                }
            )

    with TestClient(app) as client:
        assert client.post("/_ingest", json=envelopes).status_code == 200
        response = client.get("/runs/evo-run/agent-invocations")
        assert response.status_code == 200
        rows = [
            row
            for row in response.json()["invocations"]
            if row["agent_path"] == "Sequential.stage_0"
        ]
        assert rows
        row = rows[0]
        assert row["gen_index"] == 0.0
        assert row["individual_id"] == 1.0
        assert row["lineage_id"] == "l1"
        assert row["operator"] == "replace_rule"
        assert row["score"] == 0.9
        assert row["selected"] is True


def test_algorithm_agent_graph_falls_back_to_terminal_agents(app_and_obs) -> None:
    app, _ = app_and_obs
    events = [
        {
            "type": "algo_event",
            "run_id": "algo-run",
            "algorithm_path": "SelfRefine",
            "kind": "algo_start",
            "payload": {"max_iter": 2},
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {},
        },
        {
            "type": "agent_event",
            "run_id": "algo-run",
            "agent_path": "Reasoner",
            "kind": "end",
            "input": {"text": "q"},
            "output": {"response": {"value": 1}},
            "started_at": 2.0,
            "finished_at": 3.0,
            "metadata": _component_meta(
                prompt_system="<role>reason</role>",
                prompt_user="<input>q</input>",
            ),
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": "algo-run",
            "agent_path": "Reflector",
            "kind": "end",
            "input": {"text": "draft"},
            "output": {"response": {"value": 2}},
            "started_at": 4.0,
            "finished_at": 5.0,
            "metadata": {
                **_component_meta(
                    prompt_system="<role>reflect</role>",
                    prompt_user="<input>draft</input>",
                ),
                "class_name": "Reflector",
            },
            "error": None,
        },
    ]

    with TestClient(app) as client:
        assert client.post("/_ingest", json=events).status_code == 200
        response = client.get("/runs/algo-run/agent_graph")

    assert response.status_code == 200
    body = response.json()
    assert body["root"] == "SelfRefine"
    paths = [node["path"] for node in body["nodes"]]
    assert paths == ["SelfRefine", "Reasoner", "Reflector"]
    assert body["nodes"][1]["parent_path"] == "SelfRefine"
    assert {edge["callee"] for edge in body["edges"]} == {"Reasoner", "Reflector"}


def test_agent_graph_falls_back_when_graph_json_is_malformed(app_and_obs, monkeypatch) -> None:
    app, _ = app_and_obs
    monkeypatch.setattr(
        agent_routes,
        "to_agent_graph_from_json",
        lambda _graph: (_ for _ in ()).throw(ValueError("bad graph")),
    )
    events = [
        {
            "type": "agent_event",
            "run_id": "bad-graph",
            "agent_path": "Root",
            "kind": "start",
            "input": None,
            "output": None,
            "started_at": 1.0,
            "finished_at": None,
            "metadata": {"is_root": True, "graph": {"root": "Root", "nodes": [], "edges": []}},
            "error": None,
        },
        {
            "type": "agent_event",
            "run_id": "bad-graph",
            "agent_path": "Leaf",
            "kind": "end",
            "input": None,
            "output": {"response": {}},
            "started_at": 2.0,
            "finished_at": 3.0,
            "metadata": {"class_name": "Leaf", "kind": "leaf"},
            "error": None,
        },
    ]

    with TestClient(app) as client:
        assert client.post("/_ingest", json=events).status_code == 200
        response = client.get("/runs/bad-graph/agent_graph")

    assert response.status_code == 200
    body = response.json()
    assert body["root"] == "Root"
    assert [node["path"] for node in body["nodes"]] == ["Root", "Leaf"]


def test_parameters_and_parameter_evolution_include_gradient_context(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        previous = _run_envelopes("run-prev")
        for env in previous:
            if env.get("agent_path") != "Sequential.stage_0":
                continue
            if env.get("kind") != "end":
                continue
            metadata = env.get("metadata")
            if not isinstance(metadata, dict):
                continue
            parameters = metadata.get("parameters")
            if not isinstance(parameters, list):
                continue
            first = parameters[0] if parameters else None
            if isinstance(first, dict):
                first["value"] = "Role v0"
        assert client.post("/_ingest", json=previous).status_code == 200
        _seed_live(client, run_id="run-live")

        gradient_prev = {
            "type": "algo_event",
            "run_id": "run-prev",
            "algorithm_path": "Trainer",
            "kind": "gradient_applied",
            "payload": {
                "message": "improve role framing",
                "severity": 0.2,
                "target_paths": ["Sequential.stage_0.role"],
                "epoch": 0,
                "batch": 1,
                "iter": 2,
                "optimizer_step": 3,
            },
            "started_at": 20.5,
            "finished_at": 20.6,
            "metadata": {},
        }
        gradient_live = {
            "type": "algo_event",
            "run_id": "run-live",
            "algorithm_path": "Trainer",
            "kind": "gradient_applied",
            "payload": {
                "message": "tighten role wording",
                "severity": 0.9,
                "target_paths": ["role"],
                "epoch": 1,
                "batch": 2,
                "iter": 3,
                "optimizer_step": 4,
            },
            "started_at": 20.7,
            "finished_at": 20.8,
            "metadata": {},
        }
        assert client.post("/_ingest", json=[gradient_prev, gradient_live]).status_code == 200

        params = client.get("/runs/run-live/agent/Sequential.stage_0/parameters")
        assert params.status_code == 200
        role = next(row for row in params.json()["parameters"] if row["path"] == "role")
        assert role["gradient"]["severity"] == "high"
        assert role["gradient"]["message"] == "tighten role wording"
        assert role["tape_link"] == {"epoch": 1, "batch": 2, "iter": 3, "optimizer_step": 4}

        evolution = client.get("/runs/run-live/parameter-evolution/Sequential.stage_0.role")
        assert evolution.status_code == 200
        body = evolution.json()
        assert body["path"] == "Sequential.stage_0.role"
        assert body["type"] == "text"
        points = body["points"]
        assert len(points) == 2
        assert [point["run_id"] for point in points] == ["run-prev", "run-live"]
        assert points[0]["value"] == "Role v0"
        assert points[1]["value"] == "Role v2"
        assert points[0]["gradient"]["severity"] == "low"
        assert points[1]["gradient"]["severity"] == "high"
        assert points[1]["source_tape_step"]["optimizer_step"] == 4


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
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/meta").status_code == 200
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/invocations").status_code == 200
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/prompts").status_code == 200
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/values?attr=text&side=in").status_code == 200
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/events").status_code == 200
        assert client.get("/runs/run-arch/agent/Sequential.stage_0/parameters").status_code == 200
        assert (
            client.get(
                "/runs/run-arch/agent/Sequential.stage_0/diff?from=Sequential.stage_0:0&to=Sequential.stage_0:1"
            ).status_code
            == 200
        )


def test_404_unknown_path_and_attribute(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        r1 = client.get("/runs/run-live/agent/nope/meta")
        assert r1.status_code == 404
        assert r1.json()["error"] == "not_found"
        assert "reason" in r1.json()

        r2 = client.get("/runs/run-live/agent/Sequential.stage_0/values?attr=missing&side=in")
        assert r2.status_code == 404
        assert r2.json()["error"] == "not_found"

        r3 = client.get("/runs/nope/io_graph")
        assert r3.status_code == 404
        assert r3.json()["error"] == "not_found"

        r4 = client.get(
            "/runs/run-live/agent/Sequential.stage_0/diff?from=Sequential.stage_0:0&to=Sequential.stage_0:404"
        )
        assert r4.status_code == 404
        assert r4.json()["error"] == "not_found"


def test_values_wrong_side_returns_clear_404(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        r = client.get("/runs/run-live/agent/Sequential.stage_0/values?attr=text&side=out")
        assert r.status_code == 404
        assert r.json()["error"] == "not_found"


def test_runs_by_hash_returns_live_matches(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        r = client.get("/runs/by-hash?hash_content=deadbeef")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body.get("matches"), list)
        assert any(m.get("run_id") == "run-live" for m in body["matches"])


def test_runs_by_hash_skips_malformed_live_runs(app_and_obs, monkeypatch) -> None:
    app, obs = app_and_obs
    with TestClient(app) as client:
        _seed_live(client)
        good_runs = obs.registry.list()

        class BadRun:
            @staticmethod
            def summary() -> dict:
                raise RuntimeError("bad summary")

            @property
            def events(self) -> list[dict]:
                raise RuntimeError("bad events")

        monkeypatch.setattr(obs.registry, "list", lambda: [BadRun(), *good_runs])
        r = client.get("/runs/by-hash?hash_content=deadbeef")
        assert r.status_code == 200
        assert any(m.get("run_id") == "run-live" for m in r.json()["matches"])


def test_io_graph_empty_when_graph_missing(app_and_obs) -> None:
    app, _ = app_and_obs
    with TestClient(app) as client:
        r = client.post(
            "/_ingest",
            json={
                "type": "agent_event",
                "run_id": "nograph",
                "agent_path": "Sequential",
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


def _live_experiment_leaf() -> FakeLeaf:
    return FakeLeaf(
        config=Configuration(backend="llamacpp", model="fake", host="127.0.0.1:8080"),
        task="return canned value",
    )


def test_invoke_experiment_gate_and_resolver_errors(tmp_path: Path) -> None:
    live = _live_experiment_leaf()
    app_disabled = create_app(
        observer=WebDashboardObserver(),
        auto_register=False,
        data_dir=tmp_path / "disabled",
        allow_experiment=False,
        experiment_resolver=lambda _run, _path: live,
    )
    with TestClient(app_disabled) as client:
        disabled = client.post(
            "/runs/r1/agent/Sequential.stage_0/invoke",
            json={"input": {"text": "hello"}},
        )
        assert disabled.status_code == 403
        assert disabled.json()["error"] == "experiment_disabled"

    app_missing = create_app(
        observer=WebDashboardObserver(),
        auto_register=False,
        data_dir=tmp_path / "missing",
        allow_experiment=True,
    )
    with TestClient(app_missing) as client:
        missing = client.post(
            "/runs/r1/agent/Sequential.stage_0/invoke",
            json={"input": {"text": "hello"}},
        )
        assert missing.status_code == 409
        assert missing.json()["error"] == "experiment_unavailable"

    app_unavailable = create_app(
        observer=WebDashboardObserver(),
        auto_register=False,
        data_dir=tmp_path / "unavailable",
        allow_experiment=True,
        experiment_resolver=lambda _run, _path: None,
    )
    with TestClient(app_unavailable) as client:
        unavailable = client.post(
            "/runs/r1/agent/Sequential.stage_0/invoke",
            json={"input": {"text": "hello"}},
        )
        assert unavailable.status_code == 409
        assert unavailable.json()["error"] == "experiment_unavailable"


def test_invoke_experiment_validation_success_and_log(tmp_path: Path) -> None:
    live = _live_experiment_leaf()
    obs = WebDashboardObserver()
    app = create_app(
        observer=obs,
        auto_register=False,
        data_dir=tmp_path,
        allow_experiment=True,
        experiment_resolver=lambda _run, path: live if path == "Sequential.stage_0" else None,
    )

    with TestClient(app) as client:
        invalid = client.post(
            "/runs/r1/agent/Sequential.stage_0/invoke",
            json={"input": {"wrong": "shape"}},
        )
        assert invalid.status_code == 400
        assert invalid.json()["error"] == "bad_request"
        assert "text" in invalid.json()["reason"]

        ok = client.post(
            "/runs/r1/agent/Sequential.stage_0/invoke",
            json={
                "input": {"text": "hello"},
                "overrides": {"role": "New role", "task": "New task"},
                "stream": True,
            },
        )
        assert ok.status_code == 200
        body = ok.json()
        assert body["metadata"]["experiment"] is True
        assert body["metadata"]["agent_path"] == "Sequential.stage_0"
        assert body["metadata"]["run_id"] == "r1"
        assert body["response"]["value"] == 7
        assert body["hash_prompt"]

        # Override mutated only the clone.
        assert live.role != "New role"
        assert live.task != "New task"

        # Suppressed notifications: no experiment run leaked into dashboard registry.
        assert obs.registry.list() == []

    log_path = app.state.experiment_log_path
    assert log_path.exists()
    lines = [line for line in log_path.read_text(encoding="utf-8").splitlines() if line]
    assert len(lines) >= 2
    assert '"status": "invalid"' in lines[0]
    assert any('"status": "ok"' in line for line in lines)
