"""`/benchmarks/*` API tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from operad_dashboard.app import create_app


@pytest.fixture
def app_and_store():
    app = create_app(auto_register=False)
    return app, app.state.benchmark_store


def _report(
    *,
    score_a: float = 0.80,
    score_b: float = 0.70,
    mean_a: float = 0.80,
    mean_b: float = 0.70,
) -> dict:
    return {
        "cells": [
            {
                "task": "classification",
                "method": "tgd",
                "seed": 0,
                "metric": "accuracy",
                "score": score_a,
                "tokens": {"prompt": 100, "completion": 30},
                "latency_s": 1.2,
            },
            {
                "task": "classification",
                "method": "momentum",
                "seed": 0,
                "metric": "accuracy",
                "score": score_b,
                "tokens": {"prompt": 120, "completion": 40},
                "latency_s": 1.4,
            },
        ],
        "summary": [
            {
                "task": "classification",
                "method": "tgd",
                "mean": mean_a,
                "std": 0.01,
                "tokens_mean": 130,
                "latency_mean": 1.2,
                "n": 1,
            },
            {
                "task": "classification",
                "method": "momentum",
                "mean": mean_b,
                "std": 0.02,
                "tokens_mean": 160,
                "latency_mean": 1.4,
                "n": 1,
            },
        ],
        "headline_findings": {
            "classification": "Best method: tgd (mean=0.800).",
        },
    }


def test_benchmark_ingest_list_detail_delete(app_and_store) -> None:
    app, _ = app_and_store
    with TestClient(app) as client:
        r_ingest = client.post("/benchmarks/_ingest", json=_report())
        assert r_ingest.status_code == 200
        bench_id = r_ingest.json()["id"]

        r_list = client.get("/benchmarks")
        assert r_list.status_code == 200
        rows = r_list.json()
        assert len(rows) == 1
        assert rows[0]["id"] == bench_id
        assert rows[0]["n_tasks"] == 1
        assert rows[0]["n_methods"] == 2

        r_detail = client.get(f"/benchmarks/{bench_id}")
        assert r_detail.status_code == 200
        detail = r_detail.json()
        assert detail["id"] == bench_id
        assert detail["report"]["summary"][0]["task"] == "classification"
        assert detail["baseline"] is None
        assert detail["delta"] == []

        r_delete = client.delete(f"/benchmarks/{bench_id}")
        assert r_delete.status_code == 200
        assert r_delete.json() == {"ok": True}

        r_list2 = client.get("/benchmarks")
        assert r_list2.status_code == 200
        assert r_list2.json() == []


def test_benchmark_ingest_invalid_schema_422(app_and_store) -> None:
    app, _ = app_and_store
    with TestClient(app) as client:
        r = client.post("/benchmarks/_ingest", json={"summary": [], "headline_findings": {}})
        assert r.status_code == 422


def test_benchmark_tag_idempotent_and_latest_baseline(app_and_store) -> None:
    app, _ = app_and_store
    with TestClient(app) as client:
        base1 = client.post("/benchmarks/_ingest", json=_report(mean_a=0.50, mean_b=0.45)).json()["id"]
        base2 = client.post("/benchmarks/_ingest", json=_report(mean_a=0.70, mean_b=0.60)).json()["id"]
        curr = client.post("/benchmarks/_ingest", json=_report(mean_a=0.90, mean_b=0.80)).json()["id"]

        r_tag1 = client.post(f"/benchmarks/{base1}/tag", json={"tag": "baseline-v1"})
        assert r_tag1.status_code == 200

        first_detail = client.get(f"/benchmarks/{base1}").json()
        tagged_at_1 = first_detail["tagged_at"]

        r_tag1_repeat = client.post(f"/benchmarks/{base1}/tag", json={"tag": "baseline-v1"})
        assert r_tag1_repeat.status_code == 200
        second_detail = client.get(f"/benchmarks/{base1}").json()
        assert second_detail["tagged_at"] == tagged_at_1

        r_tag2 = client.post(f"/benchmarks/{base2}/tag", json={"tag": "baseline-v2"})
        assert r_tag2.status_code == 200

        current_detail = client.get(f"/benchmarks/{curr}").json()
        assert current_detail["baseline"]["id"] == base2
        deltas = {(d["task"], d["method"]): d["delta"] for d in current_detail["delta"]}
        assert deltas[("classification", "tgd")] == pytest.approx(0.2)
        assert deltas[("classification", "momentum")] == pytest.approx(0.2)


def test_benchmark_startup_scan_ingests_valid_files(tmp_path: Path) -> None:
    bench_dir = tmp_path / "bench"
    bench_dir.mkdir(parents=True)

    (bench_dir / "valid.json").write_text(json.dumps(_report()), encoding="utf-8")
    (bench_dir / "invalid.json").write_text("{\"oops\": 1}", encoding="utf-8")

    app = create_app(auto_register=False, benchmark_dir=str(bench_dir))
    with TestClient(app) as client:
        rows = client.get("/benchmarks").json()
        assert len(rows) == 1
        assert rows[0]["n_tasks"] == 1
        assert rows[0]["n_methods"] == 2
