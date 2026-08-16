from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from master_data import api_football_guard as guard
from master_data.collector_runtime import open_db


def test_paced_request_rejects_provider_errors(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(
        guard,
        "_original_api_request",
        lambda *a, **k: ({"errors": {"rateLimit": "Too many requests"}, "results": 0, "response": []}, "2026-08-15T00:00:00Z"),
    )
    with pytest.raises(guard.ApiFootballProviderError, match="API_FOOTBALL_PROVIDER_ERROR"):
        guard.paced_api_request(object(), "fixtures", {"league": 39, "season": 2026}, Path("."))


def test_provider_empty_is_not_error(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setattr(
        guard,
        "_original_api_request",
        lambda *a, **k: ({"errors": [], "results": 0, "paging": {"current": 1, "total": 1}, "response": []}, "2026-08-15T00:00:00Z"),
    )
    doc, _ = guard.paced_api_request(object(), "fixtures", {"league": 39, "season": 2026}, Path("."))
    assert doc["results"] == 0


def test_safe_bootstrap_marks_zero_results_empty(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", "0")
    target = {
        "domain": "ENG_PREMIER_LEAGUE",
        "league_id": 39,
        "season": 2026,
        "provider_name": "Premier League",
        "country": "England",
    }
    monkeypatch.setattr(guard, "exact_api_target_matches", lambda rows: ([target], []))
    monkeypatch.setattr(guard.rt, "quota_state", lambda *a, **k: {"spendable": 85})
    monkeypatch.setattr(guard.rt, "_upsert_fixture", lambda *a, **k: None)
    responses = iter([
        ({"errors": [], "results": 1, "response": [{"league": {"id": 39}}]}, "x"),
        ({"errors": [], "results": 0, "paging": {"current": 1, "total": 1}, "response": []}, "y"),
    ])
    monkeypatch.setattr(guard, "paced_api_request", lambda *a, **k: next(responses))
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        out = guard.safe_bootstrap_api_fixtures(con, Path(td))
    assert out["status"] == "EMPTY"
    assert out["catalogs"][0]["status"] == "EMPTY"
    assert out["catalogs"][0]["provider_results"] == 0


def test_plan_error_short_circuits_remaining_competitions(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("API_FOOTBALL_PLAN_BLOCK_DAYS", "7")
    targets = [
        {"domain": "ENG_PREMIER_LEAGUE", "league_id": 39, "season": 2026, "provider_name": "Premier League", "country": "England"},
        {"domain": "ESP_LA_LIGA", "league_id": 140, "season": 2026, "provider_name": "La Liga", "country": "Spain"},
        {"domain": "ITA_SERIE_A", "league_id": 135, "season": 2026, "provider_name": "Serie A", "country": "Italy"},
    ]
    monkeypatch.setattr(guard, "exact_api_target_matches", lambda rows: (targets, []))
    monkeypatch.setattr(guard.rt, "quota_state", lambda *a, **k: {"spendable": 85})
    calls = {"n": 0}

    def fake_request(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"errors": [], "response": [{}]}, "x"
        raise guard.ApiFootballProviderError(
            'API_FOOTBALL_PROVIDER_ERROR endpoint=fixtures; errors={"plan":"Free plans do not have access to this season, try from 2022 to 2024."}'
        )

    monkeypatch.setattr(guard, "paced_api_request", fake_request)
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        out = guard.safe_bootstrap_api_fixtures(con, Path(td))
        block = guard.current_plan_block(con)
    assert calls["n"] == 2  # leagues + first fixture probe only
    assert out["status"] == "PLAN_BLOCKED"
    assert out["catalogs"][0]["status"] == "PLAN_BLOCKED"
    assert out["catalogs"][1]["status"] == "SKIPPED_PLAN_BLOCKED"
    assert out["catalogs"][2]["status"] == "SKIPPED_PLAN_BLOCKED"
    assert block and block["season"] == 2026


def test_seed_plan_block_from_historical_run_uses_no_api(monkeypatch):
    monkeypatch.setenv("API_FOOTBALL_PLAN_BLOCK_DAYS", "7")
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        details = {
            "fixture_bootstrap": {
                "status": "FAILED",
                "catalogs": [
                    {
                        "season": 2026,
                        "error": 'ApiFootballProviderError: API_FOOTBALL_PROVIDER_ERROR endpoint=fixtures; errors={"plan": "Free plans do not have access to this season, try from 2022 to 2024."}',
                    }
                ],
            }
        }
        con.execute(
            "INSERT INTO collector_runs(run_id,started_at,finished_at,status,bootstrap,details_json) VALUES(?,?,?,?,?,?)",
            ("r", "2026-08-16T00:00:00Z", "2026-08-16T00:01:00Z", "DEGRADED", 1, json.dumps(details)),
        )
        con.commit()
        block = guard.seed_plan_block_from_history(con)
    assert block and block["status"] == "PLAN_BLOCKED"
    assert block["season"] == 2026


def test_429_retries_once(monkeypatch):
    import urllib.error

    monkeypatch.setenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", "0")
    monkeypatch.setenv("API_FOOTBALL_429_RETRY_SECONDS", "0")
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise urllib.error.HTTPError("https://example.invalid", 429, "Too Many Requests", {}, None)
        return ({"errors": [], "results": 1, "response": [{}]}, "x")

    monkeypatch.setattr(guard, "_original_api_request", fake)
    doc, _ = guard.paced_api_request(object(), "fixtures", {}, Path("."))
    assert calls["n"] == 2
    assert doc["results"] == 1
