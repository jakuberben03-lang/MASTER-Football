#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from master_data.collector_runtime import (
    bootstrap_api_fixtures,
    collect_football_data,
    collect_the_odds_api,
    monitor_api_fixtures,
    open_db,
    should_bootstrap_today,
    status_report,
    utcnow,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="MASTER Football Collector vNext operational runner")
    ap.add_argument("--db", default=str(ROOT / "runtime" / "collector_runtime.db"))
    ap.add_argument("--raw-dir", default=str(ROOT / "runtime" / "raw"))
    ap.add_argument("--bootstrap-fixtures", action="store_true")
    ap.add_argument("--auto-bootstrap", action="store_true", help="Bootstrap API-Football fixture catalogs once per UTC day")
    ap.add_argument("--skip-football-data", action="store_true")
    ap.add_argument("--current-odds", action="store_true")
    ap.add_argument("--odds-markets", default="h2h", choices=("h2h", "h2h,totals"))
    ap.add_argument("--max-odds-sports", type=int, default=None)
    ap.add_argument("--max-monitor-fixtures", type=int, default=12)
    args = ap.parse_args()

    con = open_db(args.db)
    started = utcnow()
    run_id = started.replace(":", "")
    con.execute("INSERT OR REPLACE INTO collector_runs(run_id,started_at,status,bootstrap,details_json) VALUES(?,?,?,?,'{}')", (run_id, started, "RUNNING", int(args.bootstrap_fixtures or args.auto_bootstrap)))
    con.commit()
    out: dict = {"started_at": started, "db": args.db, "raw_dir": args.raw_dir}
    try:
        if args.bootstrap_fixtures or (args.auto_bootstrap and should_bootstrap_today(con)):
            try:
                out["fixture_bootstrap"] = bootstrap_api_fixtures(con, args.raw_dir)
            except Exception as exc:
                out["fixture_bootstrap"] = {"status": "SKIPPED_OR_FAILED", "error": f"{type(exc).__name__}: {exc}"}
        else:
            out["fixture_bootstrap"] = {"status": "NOT_DUE"}

        out["stats_monitor"] = monitor_api_fixtures(con, args.raw_dir, max_fixtures=args.max_monitor_fixtures)
        if not args.skip_football_data:
            out["football_data"] = collect_football_data(con, args.raw_dir)
        if args.current_odds:
            out["the_odds_api"] = collect_the_odds_api(con, args.raw_dir, markets=args.odds_markets, max_sports=args.max_odds_sports)
        out["status_report"] = status_report(con)
        out["finished_at"] = utcnow()
        out["status"] = "SUCCESS"
        con.execute("UPDATE collector_runs SET finished_at=?,status='SUCCESS',details_json=? WHERE run_id=?", (out["finished_at"], json.dumps(out, ensure_ascii=False, default=str), run_id))
        con.commit()
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    except Exception as exc:
        out["finished_at"] = utcnow()
        out["status"] = "FAILED"
        out["error"] = f"{type(exc).__name__}: {exc}"
        con.execute("UPDATE collector_runs SET finished_at=?,status='FAILED',details_json=? WHERE run_id=?", (out["finished_at"], json.dumps(out, ensure_ascii=False, default=str), run_id))
        con.commit()
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
