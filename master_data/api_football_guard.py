from __future__ import annotations

import json
import os
import time
import urllib.error
from datetime import datetime, timedelta
from typing import Any

from . import collector_runtime as rt
from .collector_scope import exact_api_target_matches

_DEFAULT_MIN_INTERVAL_SECONDS = 6.2
_DEFAULT_429_RETRY_SECONDS = 65.0
_DEFAULT_PLAN_BLOCK_DAYS = 7
_last_request_monotonic = 0.0
_original_api_request = rt._api_request


class ApiFootballProviderError(RuntimeError):
    pass


def _min_interval_seconds() -> float:
    raw = os.getenv("API_FOOTBALL_MIN_INTERVAL_SECONDS", str(_DEFAULT_MIN_INTERVAL_SECONDS))
    try:
        return max(0.0, float(raw))
    except Exception:
        return _DEFAULT_MIN_INTERVAL_SECONDS


def _pace() -> None:
    global _last_request_monotonic
    interval = _min_interval_seconds()
    if interval <= 0:
        return
    now = time.monotonic()
    if _last_request_monotonic:
        wait = interval - (now - _last_request_monotonic)
        if wait > 0:
            time.sleep(wait)


def _provider_errors(doc: dict[str, Any]) -> Any:
    errors = doc.get("errors")
    return errors if errors not in (None, [], {}) else None


def _is_current_season_free_plan_error(value: Any) -> bool:
    text = str(value or "").lower()
    return (
        "free plans do not have access to this season" in text
        or ("free plan" in text and "season" in text and "access" in text)
    )


def _meta_get(con, key: str) -> str | None:
    row = con.execute("SELECT value FROM collector_meta WHERE key=?", (key,)).fetchone()
    return str(row[0]) if row else None


def _meta_set(con, key: str, value: str, observed_at: str | None = None) -> None:
    observed = observed_at or rt.utcnow()
    con.execute(
        "INSERT OR REPLACE INTO collector_meta(key,value,updated_at) VALUES(?,?,?)",
        (key, str(value), observed),
    )


def _clear_plan_block(con) -> None:
    con.execute(
        "DELETE FROM collector_meta WHERE key IN (?,?,?)",
        (
            "api_football_plan_blocked_until",
            "api_football_plan_blocked_reason",
            "api_football_plan_blocked_season",
        ),
    )
    con.commit()


def _set_plan_block(con, *, reason: str, season: int | None = None) -> dict[str, Any]:
    now = datetime.now(rt.UTC)
    days_raw = os.getenv("API_FOOTBALL_PLAN_BLOCK_DAYS", str(_DEFAULT_PLAN_BLOCK_DAYS))
    try:
        days = max(1, int(days_raw))
    except Exception:
        days = _DEFAULT_PLAN_BLOCK_DAYS
    until = now + timedelta(days=days)
    observed = rt.utcnow()
    _meta_set(con, "api_football_plan_blocked_until", until.isoformat().replace("+00:00", "Z"), observed)
    _meta_set(con, "api_football_plan_blocked_reason", reason, observed)
    if season is not None:
        _meta_set(con, "api_football_plan_blocked_season", str(int(season)), observed)
    _meta_set(con, "last_bootstrap_status", "PLAN_BLOCKED", observed)
    _meta_set(con, "last_bootstrap_date", now.date().isoformat(), observed)
    con.commit()
    return current_plan_block(con) or {"status": "PLAN_BLOCKED", "reason": reason}


def current_plan_block(con) -> dict[str, Any] | None:
    until_raw = _meta_get(con, "api_football_plan_blocked_until")
    if not until_raw:
        return None
    try:
        until = rt.parse_utc(until_raw)
    except Exception:
        return None
    if until <= datetime.now(rt.UTC):
        _clear_plan_block(con)
        return None
    season_raw = _meta_get(con, "api_football_plan_blocked_season")
    return {
        "status": "PLAN_BLOCKED",
        "blocked_until": until.isoformat().replace("+00:00", "Z"),
        "season": int(season_raw) if season_raw and season_raw.isdigit() else None,
        "reason": _meta_get(con, "api_football_plan_blocked_reason"),
        "request_policy": "NO_API_FOOTBALL_CURRENT_SEASON_PROBES_UNTIL_BLOCK_EXPIRY",
    }


def seed_plan_block_from_history(con) -> dict[str, Any] | None:
    """Migrate a previously observed free-plan season error into the quota guard without a new API call."""
    active = current_plan_block(con)
    if active:
        return active
    rows = con.execute(
        "SELECT details_json FROM collector_runs WHERE details_json IS NOT NULL AND details_json!='{}' ORDER BY started_at DESC LIMIT 12"
    ).fetchall()
    for row in rows:
        try:
            details = json.loads(row[0])
        except Exception:
            continue
        catalogs = ((details.get("fixture_bootstrap") or {}).get("catalogs") or [])
        for item in catalogs:
            err = item.get("error")
            if _is_current_season_free_plan_error(err):
                return _set_plan_block(
                    con,
                    reason=str(err),
                    season=item.get("season"),
                )
    return None


def paced_api_request(con, endpoint: str, params: dict[str, Any], raw_dir):
    """Rate-limit API-Football calls and fail closed on provider-level errors."""
    global _last_request_monotonic
    _pace()
    try:
        doc, observed = _original_api_request(con, endpoint, params, raw_dir)
    except urllib.error.HTTPError as exc:
        _last_request_monotonic = time.monotonic()
        if int(getattr(exc, "code", 0) or 0) != 429:
            raise
        raw_wait = os.getenv("API_FOOTBALL_429_RETRY_SECONDS", str(_DEFAULT_429_RETRY_SECONDS))
        try:
            retry_wait = max(0.0, float(raw_wait))
        except Exception:
            retry_wait = _DEFAULT_429_RETRY_SECONDS
        if retry_wait > 0:
            time.sleep(retry_wait)
        _pace()
        try:
            doc, observed = _original_api_request(con, endpoint, params, raw_dir)
        except urllib.error.HTTPError as retry_exc:
            _last_request_monotonic = time.monotonic()
            if int(getattr(retry_exc, "code", 0) or 0) == 429:
                raise ApiFootballProviderError(
                    f"API_FOOTBALL_HTTP_429 endpoint={endpoint}; retry exhausted"
                ) from retry_exc
            raise
    _last_request_monotonic = time.monotonic()

    if not isinstance(doc, dict):
        raise ApiFootballProviderError(
            f"API_FOOTBALL_INVALID_RESPONSE endpoint={endpoint}; type={type(doc).__name__}"
        )

    errors = _provider_errors(doc)
    if errors is not None:
        detail = json.dumps(errors, ensure_ascii=False, sort_keys=True, default=str)
        raise ApiFootballProviderError(
            f"API_FOOTBALL_PROVIDER_ERROR endpoint={endpoint}; errors={detail}"
        )
    return doc, observed


def install_api_football_guard() -> None:
    """Install pacing/error validation for all subsequent runtime API-Football calls."""
    if rt._api_request is not paced_api_request:
        rt._api_request = paced_api_request


def safe_bootstrap_api_fixtures(con, raw_dir) -> dict[str, Any]:
    """Bootstrap current competitions with explicit EMPTY/ERROR diagnostics and plan-block short circuit."""
    install_api_football_guard()
    doc, _ = paced_api_request(con, "leagues", {"current": "true"}, raw_dir)
    selected, missing = exact_api_target_matches(doc.get("response") or [])
    results: list[dict[str, Any]] = []
    plan_blocked = False
    plan_reason = None
    plan_season = None

    for idx, item in enumerate(selected):
        if rt.quota_state(con, "API_FOOTBALL")["spendable"] < 1:
            results.append({**item, "status": "QUOTA_RESERVE"})
            break

        try:
            fixtures_doc, fetched = paced_api_request(
                con,
                "fixtures",
                {"league": item["league_id"], "season": item["season"]},
                raw_dir,
            )
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            if _is_current_season_free_plan_error(error_text):
                plan_blocked = True
                plan_reason = error_text
                plan_season = item.get("season")
                results.append(
                    {
                        **item,
                        "status": "PLAN_BLOCKED",
                        "fixtures_seen": 0,
                        "error": error_text,
                    }
                )
                for rest in selected[idx + 1 :]:
                    results.append(
                        {
                            **rest,
                            "status": "SKIPPED_PLAN_BLOCKED",
                            "fixtures_seen": 0,
                        }
                    )
                break
            results.append(
                {
                    **item,
                    "status": "ERROR",
                    "fixtures_seen": 0,
                    "error": error_text,
                }
            )
            continue

        response = fixtures_doc.get("response") or []
        for fx in response:
            rt._upsert_fixture(con, item["domain"], fx, fetched)

        count = len(response)
        con.execute(
            """INSERT INTO competition_links(domain,api_league_id,api_season,api_name,country,updated_at)
               VALUES(?,?,?,?,?,?) ON CONFLICT(domain) DO UPDATE SET api_league_id=excluded.api_league_id,
               api_season=excluded.api_season,api_name=excluded.api_name,country=excluded.country,updated_at=excluded.updated_at""",
            (
                item["domain"],
                item["league_id"],
                item["season"],
                item["provider_name"],
                item.get("country"),
                fetched,
            ),
        )
        con.commit()
        results.append(
            {
                **item,
                "status": "OK" if count else "EMPTY",
                "fixtures_seen": count,
                "provider_results": fixtures_doc.get("results"),
                "provider_paging": fixtures_doc.get("paging"),
            }
        )

    ok_count = sum(1 for x in results if x.get("status") == "OK")
    error_count = sum(1 for x in results if x.get("status") == "ERROR")
    empty_count = sum(1 for x in results if x.get("status") == "EMPTY")
    quota_count = sum(1 for x in results if x.get("status") == "QUOTA_RESERVE")
    skipped_plan_count = sum(1 for x in results if x.get("status") == "SKIPPED_PLAN_BLOCKED")

    if plan_blocked:
        status = "PLAN_BLOCKED"
        block = _set_plan_block(con, reason=str(plan_reason), season=plan_season)
    else:
        block = None
        if results and ok_count == len(results):
            status = "SUCCESS"
            _clear_plan_block(con)
        elif ok_count:
            status = "PARTIAL"
        elif error_count:
            status = "FAILED"
        elif quota_count:
            status = "QUOTA_RESERVE"
        else:
            status = "EMPTY"

        now = rt.utcnow()
        con.execute(
            "INSERT OR REPLACE INTO collector_meta(key,value,updated_at) VALUES('last_bootstrap_date',?,?)",
            (time.strftime("%Y-%m-%d", time.gmtime()), now),
        )
        con.execute(
            "INSERT OR REPLACE INTO collector_meta(key,value,updated_at) VALUES('last_bootstrap_status',?,?)",
            (status, now),
        )
        con.commit()

    return {
        "status": status,
        "selected": selected,
        "missing_or_ambiguous": missing,
        "catalogs": results,
        "plan_block": block,
        "summary": {
            "ok": ok_count,
            "empty": empty_count,
            "errors": error_count,
            "quota_reserve": quota_count,
            "skipped_plan_blocked": skipped_plan_count,
            "min_interval_seconds": _min_interval_seconds(),
            "provider_errors_fail_closed": True,
            "plan_block_short_circuit": True,
        },
    }
