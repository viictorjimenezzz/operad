"""Studio FastAPI app — index, job view, rating POST, train launcher."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from fastapi.testclient import TestClient

from operad_studio.app import create_app
from operad_studio.training import TrainingLauncher


def _row(id_: str, rating: int | None = None) -> dict:
    return {
        "id": id_,
        "run_id": "r",
        "agent_path": "Talker",
        "input": {"text": "hi"},
        "expected": None,
        "predicted": {"text": "hello"},
        "rating": rating,
        "rationale": None,
        "written_at": "",
    }


def _seed_job(data_dir: Path, name: str, rows: list[dict]) -> Path:
    path = data_dir / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def test_jobs_api_lists_seeded_jobs(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a"), _row("b", rating=5)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/jobs")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["name"] == "talker"
        assert items[0]["total_rows"] == 2
        assert items[0]["rated_rows"] == 1


def test_jobs_api_empty_dir(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/jobs")
        assert r.status_code == 200
        assert r.json() == []


def test_job_rows_api_returns_rows(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a"), _row("b", rating=3)])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/jobs/talker/rows")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 2
        assert body["rated"] == 1
        assert any(row["predicted"]["text"] == "hello" for row in body["rows"])


def test_spa_index_returns_html(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_spa_catch_all_serves_studio_routes(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a")])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/jobs/talker")
        assert r.status_code == 200
        assert "operad" in r.text.lower()


def test_api_manifest(tmp_path: Path) -> None:
    app = create_app(data_dir=tmp_path, dashboard_port=7860)
    with TestClient(app) as client:
        r = client.get("/api/manifest")
        assert r.status_code == 200
        body = r.json()
        assert body["mode"] == "studio"
        assert body["dashboardPort"] == 7860


def test_rate_row_persists(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a")])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.post(
            "/jobs/talker/rows/a",
            data={"rating": "4", "rationale": "ok"},
        )
        assert r.status_code == 200
    persisted = json.loads((tmp_path / "talker.jsonl").read_text().strip())
    assert persisted["rating"] == 4
    assert persisted["rationale"] == "ok"


def test_rate_row_rejects_out_of_range(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a")])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        assert client.post("/jobs/talker/rows/a", data={"rating": "0"}).status_code == 400
        assert client.post("/jobs/talker/rows/a", data={"rating": "6"}).status_code == 400


def test_download_returns_ndjson(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a")])
    app = create_app(data_dir=tmp_path)
    with TestClient(app) as client:
        r = client.get("/jobs/talker/download")
        assert r.status_code == 200
        assert "a" in r.text


def test_train_without_agent_bundle_returns_400(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a", rating=5)])
    app = create_app(data_dir=tmp_path, agent_bundle=None)
    with TestClient(app) as client:
        r = client.post("/jobs/talker/train", data={"epochs": 1, "lr": 1.0})
        assert r.status_code == 400


async def _fake_runner(**kwargs):
    on_event = kwargs["on_event"]
    on_event({"kind": "fit_start", "entries": 1, "epochs": 1})
    await asyncio.sleep(0)
    on_event({"kind": "saved", "bundle_out": "/tmp/fake.json"})
    return Path("/tmp/fake.json")


def test_train_launches_runner_and_streams_events(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a", rating=4)])
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")

    app = create_app(
        data_dir=tmp_path, agent_bundle=bundle, runner=_fake_runner
    )
    with TestClient(app) as client:
        r = client.post("/jobs/talker/train", data={"epochs": 1, "lr": 1.0})
        assert r.status_code == 202

        # Drain the SSE — our fake_runner emits two events and finishes.
        with client.stream("GET", "/jobs/talker/train/stream") as resp:
            assert resp.status_code == 200
            seen: list[dict] = []
            for line in resp.iter_lines():
                if line.startswith("data:"):
                    env = json.loads(line[5:].strip())
                    if "kind" in env:
                        seen.append(env)
                    if env.get("kind") == "finished":
                        break
            kinds = [ev["kind"] for ev in seen]
            assert "started" in kinds
            assert "finished" in kinds


def test_train_same_job_twice_returns_conflict(tmp_path: Path) -> None:
    _seed_job(tmp_path, "talker", [_row("a", rating=4)])
    bundle = tmp_path / "bundle.json"
    bundle.write_text("{}", encoding="utf-8")

    async def _slow_runner(**kwargs):
        await asyncio.sleep(5)
        return None

    launcher = TrainingLauncher()
    app = create_app(
        data_dir=tmp_path,
        agent_bundle=bundle,
        launcher=launcher,
        runner=_slow_runner,
    )
    with TestClient(app) as client:
        assert client.post("/jobs/talker/train", data={"epochs": 1, "lr": 1.0}).status_code == 202
        assert client.post("/jobs/talker/train", data={"epochs": 1, "lr": 1.0}).status_code == 409
