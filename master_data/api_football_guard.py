from __future__ import annotations

import json
import os
import time
import urllib.error
from typing import Any

from . import collector_runtime as rt
from .collector_scope import exact_api_target_matches

_DEFAULT_MIN_INTERVAL_SECONDS = 6.2
_DEFAULT_429_RETRY_SECONDS = 65.0
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
    """Bootstrap current competitions with explicit EMPTY/ERROR diagnostics."""
    install_api_football_guard()
    doc, _ = paced_api_request(con, "leagues", {"current": "true"}, raw_dir)
    selected, missing = exact_api_target_matches(doc.get("response") or [])
    results: list[dict[str, Any]] = []

    for item in selected:
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
            results.append(
                {
                    **item,
                    "status": "ERROR",
                    "fixtures_seen": 0,
                    "error": f"{type(exc).__name__}: {exc}",
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

    if results and ok_count == len(results):
        status = "SUCCESS"
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
        "summary": {
            "ok": ok_count,
            "empty": empty_count,
            "errors": error_count,
            "quota_reserve": quota_count,
            "min_interval_seconds": _min_interval_seconds(),
            "provider_errors_fail_closed": True,
        },
    }
