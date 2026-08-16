from __future__ import annotations

import json
import tempfile
from pathlib import Path

from master_data.collector_runtime import open_db, stable_id
from master_data.free_current_fallback import (
    FD_ORG_FREE_COMPETITIONS,
    collect_football_data_org,
    materialize_free_current_candidates,
)


def _stage_external(con, *, source, source_key, hint, home, away, source_date, observed, raw):
    oid = stable_id("test", source, source_key, observed)
    con.execute(
        "INSERT INTO external_fixture_observations VALUES(?,?,?,?,?,?,?,?,?,?)",
        (oid, source, source_key, hint, home, away, source_date, observed, "TEST", json.dumps(raw)),
    )
    con.commit()


def test_materializes_exact_football_data_domains_without_canonical_link():
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        observed = "2099-08-16T08:00:00Z"
        _stage_external(
            con,
            source="FOOTBALL_DATA_PUBLIC",
            source_key="a",
            hint="E0",
            home="Arsenal",
            away="Chelsea",
            source_date="17/08/99",
            observed=observed,
            raw={"Div": "E0", "Date": "17/08/99", "Time": "16:30"},
        )
        _stage_external(
            con,
            source="FOOTBALL_DATA_PUBLIC",
            source_key="b",
            hint="Denmark::Superliga",
            home="A",
            away="B",
            source_date="17/08/2099",
            observed=observed,
            raw={"Country": "Denmark", "League": "Superliga", "Date": "17/08/2099"},
        )
        out = materialize_free_current_candidates(con, observed_since=observed)
        rows = con.execute("SELECT domain,usage_scope,identity_quality FROM free_current_fixture_candidates ORDER BY domain").fetchall()
    assert out["mapped_observations"] == 2
    assert {r["domain"] for r in rows} == {"ENG_PREMIER_LEAGUE", "DEN_SUPERLIGA"}
    assert all("NO_CANONICAL_FIXTURE_LINK" in r["usage_scope"] for r in rows)
    assert all("TEAM_NAMES_UNLINKED" in r["identity_quality"] for r in rows)


def test_unmapped_fixture_hint_is_not_guessed():
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        observed = "2026-08-16T08:00:00Z"
        _stage_external(
            con,
            source="FOOTBALL_DATA_PUBLIC",
            source_key="x",
            hint="Czechia::Some Similar Liga",
            home="X",
            away="Y",
            source_date="17/08/2026",
            observed=observed,
            raw={},
        )
        out = materialize_free_current_candidates(con, observed_since=observed)
        count = con.execute("SELECT COUNT(*) FROM free_current_fixture_candidates").fetchone()[0]
    assert count == 0
    assert out["mapped_observations"] == 0
    assert out["unmapped_hints"]


def test_football_data_org_skips_cleanly_without_key(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_ORG_KEY", raising=False)
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        out = collect_football_data_org(con, Path(td))
    assert out["status"] == "SKIPPED"
    assert out["reason"] == "FOOTBALL_DATA_ORG_KEY_NOT_SET"
    assert "ENG_PREMIER_LEAGUE" in out["free_domains"]


def test_football_data_org_stages_only_declared_free_competitions(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_ORG_KEY", "secret")
    sample = {
        "matches": [
            {
                "id": 1,
                "utcDate": "2026-08-17T19:00:00Z",
                "status": "SCHEDULED",
                "competition": {"code": "PL", "name": "Premier League"},
                "homeTeam": {"name": "Arsenal FC"},
                "awayTeam": {"name": "Chelsea FC"},
            },
            {
                "id": 2,
                "utcDate": "2026-08-17T19:00:00Z",
                "status": "SCHEDULED",
                "competition": {"code": "BJL", "name": "Jupiler Pro League"},
                "homeTeam": {"name": "A"},
                "awayTeam": {"name": "B"},
            },
        ]
    }
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "x.db")
        from master_data import free_current_fallback as ff
        monkeypatch.setattr(
            ff.rt,
            "_http_json",
            lambda *a, **k: (sample, {}, "2026-08-16T08:00:00Z"),
        )
        out = collect_football_data_org(con, Path(td))
        rows = con.execute("SELECT source,competition_hint,source_fixture_key FROM external_fixture_observations").fetchall()
    assert out["status"] == "SUCCESS"
    assert out["request_count"] == 1
    assert len(rows) == 1
    assert rows[0]["competition_hint"] == "ENG_PREMIER_LEAGUE"
    assert set(FD_ORG_FREE_COMPETITIONS.values()) >= {"PL", "ELC", "CL"}
