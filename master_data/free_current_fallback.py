from __future__ import annotations

import json
import os
import urllib.parse
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from . import collector_runtime as rt
from .collector_scope import normalize

FOOTBALL_DATA_ORG_BASE = "https://api.football-data.org/v4"

# football-data.org free-tier competitions verified from provider coverage/docs.
FD_ORG_FREE_COMPETITIONS: dict[str, str] = {
    "ENG_PREMIER_LEAGUE": "PL",
    "ENG_CHAMPIONSHIP": "ELC",
    "ESP_LA_LIGA": "PD",
    "GER_BUNDESLIGA": "BL1",
    "ITA_SERIE_A": "SA",
    "FRA_LIGUE_1": "FL1",
    "NED_EREDIVISIE": "DED",
    "POR_PRIMEIRA_LIGA": "PPL",
    "UEFA_CHAMPIONS_LEAGUE": "CL",
}
FD_ORG_CODE_TO_DOMAIN = {v: k for k, v in FD_ORG_FREE_COMPETITIONS.items()}

# Football-Data.co.uk public current fixture scanner: exact declared mappings only.
FD_PUBLIC_MAIN_DIV_TO_DOMAIN: dict[str, str] = {
    "E0": "ENG_PREMIER_LEAGUE",
    "E1": "ENG_CHAMPIONSHIP",
    "SP1": "ESP_LA_LIGA",
    "D1": "GER_BUNDESLIGA",
    "I1": "ITA_SERIE_A",
    "F1": "FRA_LIGUE_1",
    "N1": "NED_EREDIVISIE",
    "B1": "BEL_PRO_LEAGUE",
    "P1": "POR_PRIMEIRA_LIGA",
}
FD_PUBLIC_EXTRA_TO_DOMAIN: dict[tuple[str, str], str] = {
    (normalize("Denmark"), normalize("Superliga")): "DEN_SUPERLIGA",
    (normalize("Denmark"), normalize("Danish Superliga")): "DEN_SUPERLIGA",
    (normalize("Denmark"), normalize("Superligaen")): "DEN_SUPERLIGA",
    (normalize("Norway"), normalize("Eliteserien")): "NOR_ELITESERIEN",
    (normalize("Sweden"), normalize("Allsvenskan")): "SWE_ALLSVENSKAN",
}


def ensure_free_current_schema(con) -> None:
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS free_current_fixture_candidates(
          candidate_id TEXT PRIMARY KEY,
          source TEXT NOT NULL,
          source_fixture_key TEXT NOT NULL,
          domain TEXT NOT NULL,
          home_team TEXT NOT NULL,
          away_team TEXT NOT NULL,
          source_kickoff TEXT,
          kickoff_utc TEXT,
          source_status TEXT,
          observed_at TEXT NOT NULL,
          timing_quality TEXT NOT NULL,
          identity_quality TEXT NOT NULL,
          usage_scope TEXT NOT NULL,
          raw_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_free_current_domain_kickoff
          ON free_current_fixture_candidates(domain, kickoff_utc);
        CREATE INDEX IF NOT EXISTS idx_free_current_source_observed
          ON free_current_fixture_candidates(source, observed_at);
        """
    )
    con.commit()


def _raw_write(raw_dir: str | Path, provider: str, observed_at: str, raw: bytes) -> str:
    d = Path(raw_dir) / provider.lower()
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"current_matches_{observed_at.replace(':', '')}.json"
    p.write_bytes(raw)
    return str(p)


def collect_football_data_org(con, raw_dir: str | Path, *, horizon_days: int = 21) -> dict[str, Any]:
    """Collect a free current schedule snapshot from football-data.org if a free token is configured.

    This source is discovery/schedule data only. It does not authorize lineups, injuries,
    player stats, model activation or canonical API-Football fixture identity.
    """
    token = os.getenv("FOOTBALL_DATA_ORG_KEY")
    if not token:
        return {
            "status": "SKIPPED",
            "reason": "FOOTBALL_DATA_ORG_KEY_NOT_SET",
            "free_domains": sorted(FD_ORG_FREE_COMPETITIONS),
        }

    now = datetime.now(rt.UTC)
    date_from = (now.date() - timedelta(days=1)).isoformat()
    date_to = (now.date() + timedelta(days=max(1, int(horizon_days)))).isoformat()
    params = {
        "competitions": ",".join(FD_ORG_FREE_COMPETITIONS.values()),
        "dateFrom": date_from,
        "dateTo": date_to,
    }
    url = f"{FOOTBALL_DATA_ORG_BASE}/matches?{urllib.parse.urlencode(params)}"
    endpoint = "matches_current_free"

    try:
        doc, _, observed = rt._http_json(
            con,
            "FOOTBALL_DATA_ORG_FREE",
            url,
            endpoint,
            {
                "X-Auth-Token": token,
                "User-Agent": "MASTER-Football-Collector-vNext/1.1",
            },
            raw_dir,
        )
    except Exception as exc:
        return {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}

    if not isinstance(doc, dict):
        return {"status": "FAILED", "error": f"INVALID_RESPONSE_TYPE:{type(doc).__name__}"}

    if doc.get("error"):
        return {"status": "FAILED", "error": f"PROVIDER_ERROR:{doc.get('error')}"}

    matches = doc.get("matches") or []
    staged = 0
    skipped_unknown_competition = 0
    domains = Counter()
    for match in matches:
        comp = match.get("competition") or {}
        code = str(comp.get("code") or "")
        domain = FD_ORG_CODE_TO_DOMAIN.get(code)
        if not domain:
            skipped_unknown_competition += 1
            continue
        pid = match.get("id")
        home = ((match.get("homeTeam") or {}).get("name") or "").strip()
        away = ((match.get("awayTeam") or {}).get("name") or "").strip()
        kickoff = match.get("utcDate")
        if pid is None or not home or not away or not kickoff:
            continue
        source_key = str(pid)
        raw_json = json.dumps(match, ensure_ascii=False, sort_keys=True)
        oid = rt.stable_id("fd-org-fixture", source_key, observed)
        con.execute(
            "INSERT OR IGNORE INTO external_fixture_observations VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                oid,
                "FOOTBALL_DATA_ORG_FREE",
                source_key,
                domain,
                home,
                away,
                str(kickoff),
                observed,
                "EXACT_SOURCE_EVENT_TIME",
                raw_json,
            ),
        )
        changed = int(con.execute("SELECT changes()").fetchone()[0])
        staged += changed
        domains[domain] += changed
    con.commit()

    return {
        "status": "SUCCESS" if staged else "EMPTY",
        "request_count": 1,
        "date_from": date_from,
        "date_to": date_to,
        "fixture_observations": staged,
        "domains": dict(sorted(domains.items())),
        "unknown_competition_rows": skipped_unknown_competition,
        "usage_scope": "DISCOVERY_ONLY__NO_STATS_AUTHORITY",
    }


def _domain_from_fd_public_hint(hint: str) -> str | None:
    if hint in FD_PUBLIC_MAIN_DIV_TO_DOMAIN:
        return FD_PUBLIC_MAIN_DIV_TO_DOMAIN[hint]
    if "::" not in hint:
        return None
    country, league = hint.split("::", 1)
    return FD_PUBLIC_EXTRA_TO_DOMAIN.get((normalize(country), normalize(league)))


def _domain_from_odds_sport_key(con, sport_key: str) -> str | None:
    rows = con.execute(
        "SELECT domain FROM competition_links WHERE odds_sport_key=?",
        (sport_key,),
    ).fetchall()
    return str(rows[0][0]) if len(rows) == 1 else None


def _parse_source_date(value: str | None) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    try:
        return rt.parse_utc(raw)
    except Exception:
        pass
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(raw, fmt)
            return d.replace(tzinfo=rt.UTC)
        except Exception:
            continue
    return None


def _candidate_fields(con, row) -> dict[str, Any] | None:
    source = str(row["source"])
    hint = str(row["competition_hint"] or "")
    source_date = str(row["source_date"] or "")
    raw_json = str(row["raw_json"] or "{}")
    try:
        payload = json.loads(raw_json)
    except Exception:
        payload = {}

    domain: str | None = None
    kickoff_utc: str | None = None
    source_kickoff = source_date or None
    source_status: str | None = None
    timing_quality = "SOURCE_DATE_ONLY__TIMEZONE_UNVERIFIED"

    if source == "FOOTBALL_DATA_PUBLIC":
        domain = _domain_from_fd_public_hint(hint)
        source_time = str(payload.get("Time") or "").strip()
        if source_time:
            source_kickoff = f"{source_date} {source_time}".strip()
            timing_quality = "SOURCE_DATE_TIME__TIMEZONE_UNVERIFIED"
    elif source == "THE_ODDS_API":
        domain = _domain_from_odds_sport_key(con, hint)
        dt = _parse_source_date(source_date)
        if dt is not None:
            kickoff_utc = dt.isoformat().replace("+00:00", "Z")
            timing_quality = "EXACT_SOURCE_EVENT_TIME"
    elif source == "FOOTBALL_DATA_ORG_FREE":
        domain = hint if hint in FD_ORG_FREE_COMPETITIONS else None
        dt = _parse_source_date(source_date)
        if dt is not None:
            kickoff_utc = dt.isoformat().replace("+00:00", "Z")
            timing_quality = "EXACT_SOURCE_EVENT_TIME"
        source_status = str(payload.get("status") or "") or None
    else:
        return None

    if not domain:
        return None

    return {
        "domain": domain,
        "source_kickoff": source_kickoff,
        "kickoff_utc": kickoff_utc,
        "source_status": source_status,
        "timing_quality": timing_quality,
    }


def materialize_free_current_candidates(con, *, observed_since: str | None = None) -> dict[str, Any]:
    """Classify free/current external observations without pretending they are canonical fixtures."""
    ensure_free_current_schema(con)

    sql = """SELECT observation_id,source,source_fixture_key,competition_hint,home_team,away_team,
                    source_date,observed_at,timing_quality,raw_json
             FROM external_fixture_observations
             WHERE source IN ('FOOTBALL_DATA_PUBLIC','THE_ODDS_API','FOOTBALL_DATA_ORG_FREE')"""
    params: tuple[Any, ...] = ()
    if observed_since:
        sql += " AND observed_at>=?"
        params = (observed_since,)
    rows = con.execute(sql, params).fetchall()

    mapped = 0
    future_or_today = 0
    source_counts = Counter()
    domain_counts = Counter()
    unmapped_hints = Counter()
    today = datetime.now(rt.UTC).date()

    for row in rows:
        fields = _candidate_fields(con, row)
        if fields is None:
            unmapped_hints[f"{row['source']}::{row['competition_hint'] or ''}"] += 1
            continue

        source_date_dt = _parse_source_date(str(row["source_date"] or ""))
        if source_date_dt is not None and source_date_dt.date() >= today:
            future_or_today += 1

        cid = rt.stable_id(
            "free-current-candidate",
            row["source"],
            row["source_fixture_key"],
            row["observed_at"],
        )
        con.execute(
            """INSERT OR IGNORE INTO free_current_fixture_candidates(
                 candidate_id,source,source_fixture_key,domain,home_team,away_team,source_kickoff,kickoff_utc,
                 source_status,observed_at,timing_quality,identity_quality,usage_scope,raw_json
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                cid,
                row["source"],
                row["source_fixture_key"],
                fields["domain"],
                row["home_team"],
                row["away_team"],
                fields["source_kickoff"],
                fields["kickoff_utc"],
                fields["source_status"],
                row["observed_at"],
                fields["timing_quality"],
                "EXACT_DECLARED_COMPETITION_MAP__TEAM_NAMES_UNLINKED",
                "DISCOVERY_ONLY__NO_CANONICAL_FIXTURE_LINK__NO_STATS_AUTHORITY",
                row["raw_json"],
            ),
        )
        changed = int(con.execute("SELECT changes()").fetchone()[0])
        mapped += changed
        source_counts[str(row["source"])] += changed
        domain_counts[fields["domain"]] += changed

    con.commit()

    return {
        "status": "SUCCESS" if mapped else ("IDLE" if not rows else "PARTIAL"),
        "input_observations": len(rows),
        "mapped_observations": mapped,
        "future_or_today_observations": future_or_today,
        "source_counts": dict(sorted(source_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "covered_domains": sorted(domain_counts),
        "unmapped_hints": [
            {"hint": hint, "count": count}
            for hint, count in unmapped_hints.most_common(30)
        ],
        "identity_quality": "EXACT_COMPETITION_ONLY__TEAM_LINK_PENDING",
        "usage_scope": "DISCOVERY_ONLY__NO_STATS_AUTHORITY",
    }
