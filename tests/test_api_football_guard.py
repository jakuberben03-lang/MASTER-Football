from __future__ import annotations

import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from master_data import api_football_guard as guard


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


class _FakeCon:
    def __init__(self):
        self.rows = []

    def execute(self, sql, params=()):
        self.rows.append((sql, params))
        return self

    def commit(self):
        return None


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
    monkeypatch.setattr(guard.rt, "utcnow", lambda: "2026-08-15T00:00:00Z")
    responses = iter([
        ({"errors": [], "results": 1, "response": [{"league": {"id": 39}}]}, "x"),
        ({"errors": [], "results": 0, "paging": {"current": 1, "total": 1}, "response": []}, "y"),
    ])
    monkeypatch.setattr(guard, "paced_api_request", lambda *a, **k: next(responses))
    con = _FakeCon()
    out = guard.safe_bootstrap_api_fixtures(con, Path("."))
    assert out["status"] == "EMPTY"
    assert out["catalogs"][0]["status"] == "EMPTY"
    assert out["catalogs"][0]["provider_results"] == 0


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
