from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .collector_scope import TARGETS, exact_api_target_matches, exact_odds_sport_matches

UTC = timezone.utc
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
ODDS_BASE = "https://api.the-odds-api.com/v4"
FOOTBALL_DATA_URLS = (
    "https://www.football-data.co.uk/fixtures.csv",
    "https://www.football-data.co.uk/new_league_fixtures.csv",
)
API_DAILY_LIMIT = 100
API_DAILY_RESERVE = 15
ODDS_MONTHLY_LIMIT = 500
ODDS_MONTHLY_RESERVE = 50


def utcnow() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return (dt if dt.tzinfo else dt.replace(tzinfo=UTC)).astimezone(UTC)


def stable_id(*parts: Any) -> str:
    raw = "\x1f".join(str(x) for x in parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:40]


def open_db(path: str | Path) -> sqlite3.Connection:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.row_factory = sqlite3.Row
    con.executescript(
        """
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS collector_runs(
          run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
          bootstrap INTEGER NOT NULL DEFAULT 0, details_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS provider_fetches(
          fetch_id TEXT PRIMARY KEY, provider TEXT NOT NULL, endpoint TEXT NOT NULL, requested_at TEXT NOT NULL,
          http_status INTEGER, response_bytes INTEGER, success INTEGER NOT NULL, notes TEXT, raw_path TEXT
        );
        CREATE TABLE IF NOT EXISTS quota_ledger(
          ledger_id TEXT PRIMARY KEY, provider TEXT NOT NULL, period_key TEXT NOT NULL, observed_at TEXT NOT NULL,
          cost INTEGER NOT NULL, provider_remaining INTEGER, source TEXT NOT NULL, notes TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_quota_provider_period ON quota_ledger(provider, period_key);
        CREATE TABLE IF NOT EXISTS competition_links(
          domain TEXT PRIMARY KEY, api_league_id INTEGER, api_season INTEGER, api_name TEXT, country TEXT,
          odds_sport_key TEXT, odds_title TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS fixtures(
          fixture_id TEXT PRIMARY KEY, provider_fixture_id TEXT UNIQUE NOT NULL, domain TEXT NOT NULL,
          kickoff_utc TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL, status TEXT,
          round TEXT, venue TEXT, referee TEXT, observed_at TEXT NOT NULL, raw_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures(kickoff_utc);
        CREATE TABLE IF NOT EXISTS lineup_snapshots(
          snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, observed_at TEXT NOT NULL,
          provider_fixture_id TEXT NOT NULL, raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS injury_snapshots(
          snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, observed_at TEXT NOT NULL,
          provider_fixture_id TEXT NOT NULL, raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS team_stat_snapshots(
          snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, observed_at TEXT NOT NULL,
          provider_fixture_id TEXT NOT NULL, phase TEXT NOT NULL, provider_status TEXT,
          raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS player_stat_snapshots(
          snapshot_id TEXT PRIMARY KEY, fixture_id TEXT NOT NULL, observed_at TEXT NOT NULL,
          provider_fixture_id TEXT NOT NULL, phase TEXT NOT NULL, provider_status TEXT,
          raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS monitor_state(
          fixture_id TEXT PRIMARY KEY, prematch_observed_at TEXT, lineup_captured INTEGER NOT NULL DEFAULT 0,
          final_observed_at TEXT, final_status TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS external_fixture_observations(
          observation_id TEXT PRIMARY KEY, source TEXT NOT NULL, source_fixture_key TEXT NOT NULL,
          competition_hint TEXT, home_team TEXT, away_team TEXT, source_date TEXT,
          observed_at TEXT NOT NULL, timing_quality TEXT NOT NULL, raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS external_odds_observations(
          observation_id TEXT PRIMARY KEY, source TEXT NOT NULL, source_fixture_key TEXT NOT NULL,
          competition_hint TEXT, bookmaker TEXT, market_key TEXT NOT NULL, selection_key TEXT NOT NULL,
          line REAL, decimal_odds REAL NOT NULL, observed_at TEXT NOT NULL, timing_quality TEXT NOT NULL,
          raw_json TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS collector_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
        """
    )
    con.commit()
    return con


def _period(provider: str, when: datetime | None = None) -> str:
    d = when or datetime.now(UTC)
    return d.strftime("%Y-%m-%d") if provider == "API_FOOTBALL" else d.strftime("%Y-%m")


def quota_state(con: sqlite3.Connection, provider: str) -> dict:
    if provider == "API_FOOTBALL":
        limit, reserve = API_DAILY_LIMIT, API_DAILY_RESERVE
    elif provider == "THE_ODDS_API":
        limit, reserve = ODDS_MONTHLY_LIMIT, ODDS_MONTHLY_RESERVE
    else:
        raise KeyError(provider)
    period = _period(provider)
    row = con.execute("SELECT COALESCE(SUM(cost),0) FROM quota_ledger WHERE provider=? AND period_key=?", (provider, period)).fetchone()
    used = int(row[0] or 0)
    remaining = max(0, limit - used)
    return {"provider": provider, "period": period, "limit": limit, "reserve": reserve, "used": used, "remaining": remaining, "spendable": max(0, remaining - reserve)}


def record_cost(con: sqlite3.Connection, provider: str, cost: int, *, remaining: int | None = None, source: str = "LOCAL_ESTIMATE", notes: str = "") -> None:
    observed = utcnow()
    lid = stable_id("quota", provider, _period(provider), observed, cost, source, notes)
    con.execute("INSERT OR IGNORE INTO quota_ledger VALUES(?,?,?,?,?,?,?,?)", (lid, provider, _period(provider), observed, int(cost), remaining, source, notes))
    con.commit()


def _raw_write(raw_dir: str | Path, provider: str, endpoint: str, observed_at: str, raw: bytes) -> str:
    d = Path(raw_dir) / provider.lower()
    d.mkdir(parents=True, exist_ok=True)
    safe = endpoint.strip("/").replace("/", "_").replace("?", "_").replace("&", "_").replace("=", "-") or "root"
    path = d / f"{safe}_{observed_at.replace(':','')}.json"
    path.write_bytes(raw)
    return str(path)


def _http_json(con: sqlite3.Connection, provider: str, url: str, endpoint: str, headers: dict[str, str], raw_dir: str | Path, timeout: int = 45) -> tuple[Any, dict[str, str], str]:
    requested = utcnow()
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            status = int(getattr(resp, "status", 200))
            response_headers = {str(k).lower(): str(v) for k, v in resp.headers.items()}
        raw_path = _raw_write(raw_dir, provider, endpoint, requested, raw)
        fid = stable_id("fetch", provider, endpoint, requested)
        con.execute("INSERT INTO provider_fetches VALUES(?,?,?,?,?,?,?,?,?)", (fid, provider, endpoint, requested, status, len(raw), 1, None, raw_path))
        con.commit()
        return json.loads(raw.decode("utf-8")), response_headers, requested
    except Exception as exc:
        fid = stable_id("fetch", provider, endpoint, requested)
        con.execute("INSERT OR REPLACE INTO provider_fetches VALUES(?,?,?,?,?,?,?,?,?)", (fid, provider, endpoint, requested, None, None, 0, f"{type(exc).__name__}: {exc}", None))
        con.commit()
        raise


def _api_request(con: sqlite3.Connection, endpoint: str, params: dict[str, Any], raw_dir: str | Path) -> tuple[dict, str]:
    key = os.getenv("API_FOOTBALL_KEY")
    if not key:
        raise RuntimeError("API_FOOTBALL_KEY_NOT_SET")
    if quota_state(con, "API_FOOTBALL")["spendable"] < 1:
        raise RuntimeError("API_FOOTBALL_QUOTA_RESERVE")
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"{API_FOOTBALL_BASE}/{endpoint.lstrip('/')}" + (f"?{query}" if query else "")
    doc, headers, observed = _http_json(con, "API_FOOTBALL", url, endpoint, {"x-apisports-key": key, "User-Agent": "MASTER-Football-Collector-vNext/1.0"}, raw_dir)
    remaining = None
    try:
        remaining = int(headers.get("x-ratelimit-requests-remaining") or headers.get("x-ratelimit-remaining"))
    except Exception:
        pass
    record_cost(con, "API_FOOTBALL", 1, remaining=remaining, source="REQUEST", notes=endpoint)
    return doc, observed


def _upsert_fixture(con: sqlite3.Connection, domain: str, item: dict, observed_at: str) -> None:
    fixture = item.get("fixture") or {}
    teams = item.get("teams") or {}
    league = item.get("league") or {}
    pid = fixture.get("id")
    kickoff = fixture.get("date")
    home = (teams.get("home") or {}).get("name")
    away = (teams.get("away") or {}).get("name")
    if pid is None or not kickoff or not home or not away:
        return
    fid = stable_id("api-football-fixture", pid)
    con.execute(
        """INSERT INTO fixtures(fixture_id,provider_fixture_id,domain,kickoff_utc,home_team,away_team,status,round,venue,referee,observed_at,raw_json)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(provider_fixture_id) DO UPDATE SET domain=excluded.domain,kickoff_utc=excluded.kickoff_utc,
             home_team=excluded.home_team,away_team=excluded.away_team,status=excluded.status,round=excluded.round,
             venue=excluded.venue,referee=excluded.referee,observed_at=excluded.observed_at,raw_json=excluded.raw_json""",
        (fid, str(pid), domain, kickoff, home, away, (fixture.get("status") or {}).get("short"), league.get("round"), (fixture.get("venue") or {}).get("name"), fixture.get("referee"), observed_at, json.dumps(item, ensure_ascii=False, sort_keys=True)),
    )
    con.execute("INSERT OR IGNORE INTO monitor_state(fixture_id,updated_at) VALUES(?,?)", (fid, observed_at))


def bootstrap_api_fixtures(con: sqlite3.Connection, raw_dir: str | Path) -> dict:
    doc, observed = _api_request(con, "leagues", {"current": "true"}, raw_dir)
    selected, missing = exact_api_target_matches(doc.get("response") or [])
    results = []
    for item in selected:
        if quota_state(con, "API_FOOTBALL")["spendable"] < 1:
            results.append({**item, "status": "QUOTA_RESERVE"})
            break
        fixtures_doc, fetched = _api_request(con, "fixtures", {"league": item["league_id"], "season": item["season"]}, raw_dir)
        count = 0
        for fx in fixtures_doc.get("response") or []:
            _upsert_fixture(con, item["domain"], fx, fetched)
            count += 1
        con.execute(
            """INSERT INTO competition_links(domain,api_league_id,api_season,api_name,country,updated_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET api_league_id=excluded.api_league_id,
               api_season=excluded.api_season,api_name=excluded.api_name,country=excluded.country,updated_at=excluded.updated_at""",
            (item["domain"], item["league_id"], item["season"], item["provider_name"], item.get("country"), fetched),
        )
        con.commit()
        results.append({**item, "status": "OK", "fixtures_seen": count})
    con.execute("INSERT OR REPLACE INTO collector_meta(key,value,updated_at) VALUES('last_bootstrap_date',?,?)", (datetime.now(UTC).date().isoformat(), utcnow()))
    con.commit()
    return {"status": "SUCCESS", "selected": selected, "missing_or_ambiguous": missing, "catalogs": results}


def _fixture_status(con: sqlite3.Connection, fixture_id: str) -> sqlite3.Row:
    return con.execute("SELECT f.*,m.prematch_observed_at,m.lineup_captured,m.final_observed_at,m.final_status FROM fixtures f JOIN monitor_state m USING(fixture_id) WHERE fixture_id=?", (fixture_id,)).fetchone()


def monitor_api_fixtures(con: sqlite3.Connection, raw_dir: str | Path, *, max_fixtures: int = 12, prematch_minutes: int = 180, post_delay_minutes: int = 105, post_lookback_hours: int = 18) -> dict:
    if not os.getenv("API_FOOTBALL_KEY"):
        return {"status": "SKIPPED", "reason": "API_FOOTBALL_KEY_NOT_SET", "quota": quota_state(con, "API_FOOTBALL")}
    now = datetime.now(UTC)
    rows = con.execute("SELECT fixture_id FROM fixtures ORDER BY kickoff_utc").fetchall()
    targets = []
    for row in rows:
        fx = _fixture_status(con, row["fixture_id"])
        ko = parse_utc(fx["kickoff_utc"])
        mins = (ko - now).total_seconds() / 60
        if 0 <= mins <= prematch_minutes and not int(fx["lineup_captured"] or 0):
            targets.append((0, fx, "PRE_MATCH"))
        elif -(post_lookback_hours * 60) <= mins <= -post_delay_minutes and not fx["final_observed_at"]:
            targets.append((1, fx, "POST_MATCH"))
    targets.sort(key=lambda x: (x[0], x[1]["kickoff_utc"]))
    out = []
    for _, fx, phase in targets[:max_fixtures]:
        pid = fx["provider_fixture_id"]
        try:
            if phase == "PRE_MATCH":
                if quota_state(con, "API_FOOTBALL")["spendable"] < 2:
                    out.append({"fixture_id": fx["fixture_id"], "phase": phase, "status": "QUOTA_RESERVE"})
                    break
                lineup, obs1 = _api_request(con, "fixtures/lineups", {"fixture": pid}, raw_dir)
                injuries, obs2 = _api_request(con, "injuries", {"fixture": pid}, raw_dir)
                con.execute("INSERT OR IGNORE INTO lineup_snapshots VALUES(?,?,?,?,?)", (stable_id("lineup", fx["fixture_id"], obs1), fx["fixture_id"], obs1, pid, json.dumps(lineup, ensure_ascii=False)))
                con.execute("INSERT OR IGNORE INTO injury_snapshots VALUES(?,?,?,?,?)", (stable_id("injury", fx["fixture_id"], obs2), fx["fixture_id"], obs2, pid, json.dumps(injuries, ensure_ascii=False)))
                captured = 1 if (lineup.get("response") or []) else 0
                con.execute("UPDATE monitor_state SET prematch_observed_at=?,lineup_captured=?,updated_at=? WHERE fixture_id=?", (obs1, captured, utcnow(), fx["fixture_id"]))
                con.commit()
                out.append({"fixture_id": fx["fixture_id"], "phase": phase, "status": "OK", "lineup_captured": bool(captured)})
            else:
                if quota_state(con, "API_FOOTBALL")["spendable"] < 3:
                    out.append({"fixture_id": fx["fixture_id"], "phase": phase, "status": "QUOTA_RESERVE"})
                    break
                fixture_doc, obs = _api_request(con, "fixtures", {"id": pid}, raw_dir)
                stats_doc, obs_stats = _api_request(con, "fixtures/statistics", {"fixture": pid}, raw_dir)
                players_doc, obs_players = _api_request(con, "fixtures/players", {"fixture": pid}, raw_dir)
                rows_status = fixture_doc.get("response") or []
                status = (((rows_status[0] if rows_status else {}).get("fixture") or {}).get("status") or {}).get("short")
                con.execute("INSERT OR IGNORE INTO team_stat_snapshots VALUES(?,?,?,?,?,?,?)", (stable_id("teamstats", fx["fixture_id"], obs_stats), fx["fixture_id"], obs_stats, pid, phase, status, json.dumps(stats_doc, ensure_ascii=False)))
                con.execute("INSERT OR IGNORE INTO player_stat_snapshots VALUES(?,?,?,?,?,?,?)", (stable_id("playerstats", fx["fixture_id"], obs_players), fx["fixture_id"], obs_players, pid, phase, status, json.dumps(players_doc, ensure_ascii=False)))
                if status in {"FT", "AET", "PEN"}:
                    con.execute("UPDATE monitor_state SET final_observed_at=?,final_status=?,updated_at=? WHERE fixture_id=?", (obs, status, utcnow(), fx["fixture_id"]))
                con.commit()
                out.append({"fixture_id": fx["fixture_id"], "phase": phase, "status": "OK", "provider_status": status})
        except Exception as exc:
            out.append({"fixture_id": fx["fixture_id"], "phase": phase, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
    return {"status": "SUCCESS" if any(x.get("status") == "OK" for x in out) else ("IDLE" if not out else "PARTIAL"), "targets": out, "quota": quota_state(con, "API_FOOTBALL")}


def _http_bytes(url: str, timeout: int = 45) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "MASTER-Football-Collector-vNext/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def collect_football_data(con: sqlite3.Connection, raw_dir: str | Path) -> dict:
    observed = utcnow()
    totals = {"files": 0, "fixture_observations": 0, "odds_observations": 0, "errors": []}
    for url in FOOTBALL_DATA_URLS:
        try:
            raw = _http_bytes(url)
            d = Path(raw_dir) / "football_data"
            d.mkdir(parents=True, exist_ok=True)
            name = url.rsplit("/", 1)[-1]
            path = d / f"{name.rsplit('.',1)[0]}_{observed.replace(':','')}.csv"
            path.write_bytes(raw)
            text = raw.decode("utf-8-sig", errors="replace")
            reader = csv.DictReader(io.StringIO(text))
            extra = "new_league" in name
            for row in reader:
                home = row.get("Home") if extra else row.get("HomeTeam")
                away = row.get("Away") if extra else row.get("AwayTeam")
                if not home or not away:
                    continue
                comp = f"{row.get('Country','')}::{row.get('League','')}" if extra else str(row.get("Div") or "")
                date = str(row.get("Date") or "")
                source_key = stable_id("football-data", comp, date, home, away)
                raw_json = json.dumps(row, ensure_ascii=False, sort_keys=True)
                oid = stable_id("fd-fixture", source_key, observed)
                con.execute("INSERT OR IGNORE INTO external_fixture_observations VALUES(?,?,?,?,?,?,?,?,?,?)", (oid, "FOOTBALL_DATA_PUBLIC", source_key, comp, home, away, date, observed, "FETCH_TIME_ONLY", raw_json))
                totals["fixture_observations"] += int(con.execute("SELECT changes()").fetchone()[0])
                for prefix in ("B365", "PS", "Max", "Avg", "BFE"):
                    for suffix, sel in (("H", "HOME"), ("D", "DRAW"), ("A", "AWAY")):
                        value = row.get(prefix + suffix)
                        try:
                            price = float(value)
                        except Exception:
                            continue
                        if price <= 1:
                            continue
                        ooid = stable_id("fd-odds", source_key, prefix, "1X2", sel, observed)
                        con.execute("INSERT OR IGNORE INTO external_odds_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (ooid, "FOOTBALL_DATA_PUBLIC", source_key, comp, prefix, "1X2", sel, None, price, observed, "FETCH_TIME_ONLY", raw_json))
                        totals["odds_observations"] += int(con.execute("SELECT changes()").fetchone()[0])
                if not extra:
                    for prefix in ("B365", "Max", "Avg", "BFE"):
                        for suffix, sel in ((">2.5", "OVER"), ("<2.5", "UNDER")):
                            try:
                                price = float(row.get(prefix + suffix))
                            except Exception:
                                continue
                            if price <= 1:
                                continue
                            ooid = stable_id("fd-odds", source_key, prefix, "GOALS_TOTAL", sel, "2.5", observed)
                            con.execute("INSERT OR IGNORE INTO external_odds_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (ooid, "FOOTBALL_DATA_PUBLIC", source_key, comp, prefix, "GOALS_TOTAL", sel, 2.5, price, observed, "FETCH_TIME_ONLY", raw_json))
                            totals["odds_observations"] += int(con.execute("SELECT changes()").fetchone()[0])
            con.commit()
            totals["files"] += 1
        except Exception as exc:
            totals["errors"].append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
    totals["status"] = "SUCCESS" if totals["files"] else "FAILED"
    return totals


def _odds_request(con: sqlite3.Connection, endpoint: str, params: dict[str, Any], raw_dir: str | Path, *, charge_estimate: int = 0) -> tuple[Any, dict[str, str], str]:
    key = os.getenv("THE_ODDS_API_KEY")
    if not key:
        raise RuntimeError("THE_ODDS_API_KEY_NOT_SET")
    query = urllib.parse.urlencode({**params, "apiKey": key})
    url = f"{ODDS_BASE}/{endpoint.lstrip('/')}?{query}"
    doc, headers, observed = _http_json(con, "THE_ODDS_API", url, endpoint, {"User-Agent": "MASTER-Football-Collector-vNext/1.0"}, raw_dir)
    last = None
    remaining = None
    try:
        last = int(headers.get("x-requests-last"))
    except Exception:
        pass
    try:
        remaining = int(headers.get("x-requests-remaining"))
    except Exception:
        pass
    cost = last if last is not None else int(charge_estimate)
    if cost > 0:
        record_cost(con, "THE_ODDS_API", cost, remaining=remaining, source="PROVIDER_HEADER" if last is not None else "LOCAL_ESTIMATE", notes=endpoint)
    return doc, headers, observed


def _odds_daily_envelope(con: sqlite3.Connection) -> int:
    state = quota_state(con, "THE_ODDS_API")
    now = datetime.now(UTC)
    next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
    days_left = max(1, (next_month.date() - now.date()).days)
    return max(1, state["spendable"] // days_left) if state["spendable"] else 0


def _stage_odds_event(con: sqlite3.Connection, sport_key: str, event: dict, observed_at: str) -> tuple[int, int]:
    source_key = str(event.get("id") or "")
    home = str(event.get("home_team") or "")
    away = str(event.get("away_team") or "")
    if not source_key or not home or not away:
        return 0, 0
    raw_json = json.dumps(event, ensure_ascii=False, sort_keys=True)
    oid = stable_id("odds-fixture", source_key, observed_at)
    con.execute("INSERT OR IGNORE INTO external_fixture_observations VALUES(?,?,?,?,?,?,?,?,?,?)", (oid, "THE_ODDS_API", source_key, sport_key, home, away, event.get("commence_time"), observed_at, "FETCH_TIME_ONLY", raw_json))
    fc = int(con.execute("SELECT changes()").fetchone()[0])
    oc = 0
    for book in event.get("bookmakers") or []:
        bookmaker = str(book.get("key") or book.get("title") or "")
        book_obs = str(book.get("last_update") or observed_at)
        timing = "EXACT_SOURCE" if book.get("last_update") else "FETCH_TIME_ONLY"
        for market in book.get("markets") or []:
            mkey = str(market.get("key") or "")
            if mkey not in {"h2h", "totals"}:
                continue
            for outcome in market.get("outcomes") or []:
                name = str(outcome.get("name") or "")
                if mkey == "h2h":
                    sel = "HOME" if name == home else ("AWAY" if name == away else ("DRAW" if name.lower() == "draw" else None))
                    market_key = "1X2"
                    line = None
                else:
                    sel = "OVER" if name.lower() == "over" else ("UNDER" if name.lower() == "under" else None)
                    market_key = "GOALS_TOTAL"
                    try:
                        line = float(outcome.get("point"))
                    except Exception:
                        line = None
                try:
                    price = float(outcome.get("price"))
                except Exception:
                    continue
                if not sel or price <= 1:
                    continue
                ooid = stable_id("odds", source_key, bookmaker, market_key, sel, line, book_obs)
                con.execute("INSERT OR IGNORE INTO external_odds_observations VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (ooid, "THE_ODDS_API", source_key, sport_key, bookmaker, market_key, sel, line, price, book_obs, timing, raw_json))
                oc += int(con.execute("SELECT changes()").fetchone()[0])
    con.commit()
    return fc, oc


def collect_the_odds_api(con: sqlite3.Connection, raw_dir: str | Path, *, markets: str = "h2h", max_sports: int | None = None) -> dict:
    if not os.getenv("THE_ODDS_API_KEY"):
        return {"status": "SKIPPED", "reason": "THE_ODDS_API_KEY_NOT_SET", "quota": quota_state(con, "THE_ODDS_API")}
    sports, _, observed = _odds_request(con, "sports", {"all": "false"}, raw_dir, charge_estimate=0)
    resolved, missing = exact_odds_sport_matches(sports if isinstance(sports, list) else [])
    for domain, sport in resolved.items():
        con.execute("""INSERT INTO competition_links(domain,odds_sport_key,odds_title,updated_at) VALUES(?,?,?,?)
                       ON CONFLICT(domain) DO UPDATE SET odds_sport_key=excluded.odds_sport_key,odds_title=excluded.odds_title,updated_at=excluded.updated_at""",
                    (domain, sport.get("key"), sport.get("title"), observed))
    con.commit()

    envelope = _odds_daily_envelope(con)
    if envelope <= 0:
        return {"status": "QUOTA_RESERVE", "resolved": list(resolved), "missing_or_ambiguous": missing, "quota": quota_state(con, "THE_ODDS_API")}

    upcoming = con.execute("SELECT domain,MIN(kickoff_utc) next_kickoff FROM fixtures WHERE kickoff_utc>? GROUP BY domain ORDER BY next_kickoff", (utcnow(),)).fetchall()
    domains = [r["domain"] for r in upcoming if r["domain"] in resolved]
    for domain in resolved:
        if domain not in domains:
            domains.append(domain)
    estimated_cost = 1 if markets == "h2h" else max(1, len([m for m in markets.split(",") if m]))
    cap = envelope // estimated_cost
    if max_sports is not None:
        cap = min(cap, int(max_sports))
    results = []
    total_fc = total_oc = 0
    for domain in domains[:cap]:
        if quota_state(con, "THE_ODDS_API")["spendable"] < estimated_cost:
            break
        sport = resolved[domain]
        try:
            doc, _, fetched = _odds_request(con, f"sports/{sport['key']}/odds", {"regions": "eu", "markets": markets, "oddsFormat": "decimal", "dateFormat": "iso"}, raw_dir, charge_estimate=estimated_cost)
            fc = oc = 0
            for event in doc if isinstance(doc, list) else []:
                a, b = _stage_odds_event(con, str(sport["key"]), event, fetched)
                fc += a; oc += b
            total_fc += fc; total_oc += oc
            results.append({"domain": domain, "sport_key": sport["key"], "status": "OK", "fixture_observations": fc, "odds_observations": oc})
        except Exception as exc:
            results.append({"domain": domain, "sport_key": sport.get("key"), "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
    return {"status": "SUCCESS" if any(x.get("status") == "OK" for x in results) else ("IDLE" if not results else "PARTIAL"), "resolved": list(resolved), "missing_or_ambiguous": missing, "daily_envelope": envelope, "results": results, "fixture_observations": total_fc, "odds_observations": total_oc, "quota": quota_state(con, "THE_ODDS_API")}


def should_bootstrap_today(con: sqlite3.Connection) -> bool:
    row = con.execute("SELECT value FROM collector_meta WHERE key='last_bootstrap_date'").fetchone()
    return not row or row[0] != datetime.now(UTC).date().isoformat()


def status_report(con: sqlite3.Connection) -> dict:
    scalar = lambda sql, args=(): int(con.execute(sql, args).fetchone()[0] or 0)
    return {
        "scope_domains": len(TARGETS),
        "fixtures": scalar("SELECT COUNT(*) FROM fixtures"),
        "future_fixtures": scalar("SELECT COUNT(*) FROM fixtures WHERE kickoff_utc>?", (utcnow(),)),
        "lineup_snapshots": scalar("SELECT COUNT(*) FROM lineup_snapshots"),
        "injury_snapshots": scalar("SELECT COUNT(*) FROM injury_snapshots"),
        "team_stat_snapshots": scalar("SELECT COUNT(*) FROM team_stat_snapshots"),
        "player_stat_snapshots": scalar("SELECT COUNT(*) FROM player_stat_snapshots"),
        "external_fixture_observations": scalar("SELECT COUNT(*) FROM external_fixture_observations"),
        "external_odds_observations": scalar("SELECT COUNT(*) FROM external_odds_observations"),
        "api_football_quota": quota_state(con, "API_FOOTBALL"),
        "the_odds_api_quota": quota_state(con, "THE_ODDS_API"),
        "betting_authority": "UNCHANGED__COLLECTION_ONLY",
    }
