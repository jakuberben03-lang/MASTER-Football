from __future__ import annotations

import json
import tempfile
from pathlib import Path

from master_data.collector_runtime import open_db, quota_state, should_bootstrap_today, stable_id
from master_data.collector_scope import exact_api_target_matches, exact_odds_sport_matches


def test_exact_api_scope_no_fuzzy():
    rows = [{
        "league": {"id": 39, "name": "Premier League"},
        "country": {"name": "England"},
        "seasons": [{"year": 2026, "current": True}],
    }, {
        "league": {"id": 999, "name": "Premier League 2"},
        "country": {"name": "England"},
        "seasons": [{"year": 2026, "current": True}],
    }]
    selected, _ = exact_api_target_matches(rows)
    assert any(x["domain"] == "ENG_PREMIER_LEAGUE" and x["league_id"] == 39 for x in selected)
    assert all(x["league_id"] != 999 for x in selected)


def test_odds_scope_exact_title_only():
    sports = [
        {"key": "soccer_epl", "title": "EPL"},
        {"key": "soccer_fake", "title": "EPL Juniors"},
    ]
    resolved, _ = exact_odds_sport_matches(sports)
    assert resolved["ENG_PREMIER_LEAGUE"]["key"] == "soccer_epl"


def test_db_and_quota_defaults():
    with tempfile.TemporaryDirectory() as td:
        con = open_db(Path(td) / "collector.db")
        assert quota_state(con, "API_FOOTBALL")["spendable"] == 85
        assert quota_state(con, "THE_ODDS_API")["spendable"] == 450
        assert should_bootstrap_today(con)
        con.execute("INSERT INTO collector_meta(key,value,updated_at) VALUES('last_bootstrap_date',date('now'),'x')")
        con.commit()
        assert not should_bootstrap_today(con)
        assert len(stable_id("a", "b")) == 40
