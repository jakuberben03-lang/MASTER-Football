# MASTER Football Data/Market Engine v2.3 — PLAYER OPEN-DATA DELIVERY

Canonical free/open data layer for MASTER Football.

## What changed from v2.0

- UEFA open result history expanded from UCL-only to UCL + UEL + UECL.
- Bundled seasons: 2021/22–2024/25 for UCL/UEL/UECL, plus 2024/25 qualification files where available.
- Fixture-level routing remains split into `UEFA_LEAGUE_PHASE`, `UEFA_KNOCKOUT`, and `UEFA_QUALIFYING`.
- Administrative awards/cancelled rows are source-audited but excluded from football-performance history.
- Matches decided after extra time now store the **90-minute score** in canonical team stats; AET/shootout truth remains in source/knockout evidence.
- Half-time scores are parsed where OpenFootball supplies them.
- Wyscout Open research adapter now has strict full-dataset validation before an all-Big-5 ingest.
- Wyscout expected match counts: England 380, France 380, Germany 306, Italy 380, Spain 380 = 1,826.
- Player research stores minutes/start, shots, SOT proxy definition, goals, fouls committed, cards, dribbles and crosses. `fouls_drawn` remains unavailable in the current adapter rather than inferred.
- schema/config feature version bumped to v2.1.

## Canonical DB snapshot

Run:

```bash
PYTHONPATH=. python -m master_data.cli audit
```

Packaged snapshot currently contains 15,768 fixtures. Open UEFA history contains 2,173 played fixtures. Wyscout raw files are **not bundled** and canonical research-player rows remain zero in this build because the build runtime could not resolve the public Figshare download host.

## Wyscout Open — safe workflow

```bash
PYTHONPATH=. python scripts/download_wyscout_open.py --out data/raw/wyscout_open
PYTHONPATH=. python -m master_data.cli wyscout-validate --root data/raw/wyscout_open
PYTHONPATH=. python -m master_data.cli wyscout-ingest-all --root data/raw/wyscout_open
```

The full ingest refuses incomplete Big-5 coverage by default. Historical actual lineups are POST-MATCH truth only and must never be treated as archived pre-match XI.

## UEFA reseed

```bash
PYTHONPATH=. python -m master_data.cli seed-uefa-openfootball
PYTHONPATH=. python -m master_data.cli features-historical
PYTHONPATH=. python -m master_data.cli free-coverage
PYTHONPATH=. python -m master_data.cli audit
```

## Hard safety

Data presence never activates a betting model. UEL/UECL/UCL domains remain EXPERIMENTAL until domain-specific model + market validation exists. Wyscout research data cannot make player props BET-capable by ingestion alone.

## v2.2 — Betfair FREE historical secondary market path

See `BETFAIR_FREE_HISTORICAL_GUIDE_CZ.md`.

New CLI:
- `betfair-scan`
- `betfair-stage-links`
- `betfair-approve-date-links --acknowledge-canonical-time-unknown`
- `betfair-ingest --tier BASIC|ADVANCED|PRO`
- `betfair-readiness`

Current supported canonical ingestion: half-point total corners and total cards. Cards are archived but current yellow-card model is settlement-mismatched and cannot be validated against Betfair Total Cards. Fouls remain unsupported until an explicit compatible historical market and counting contract exists.


## v2.3 — Player open-data delivery

- Wyscout Open downloader now supports `--source auto|figshare|github`.
- `auto` tries the original Figshare publication, then the public GitHub raw-data mirror.
- Strict full-Big5 2017/18 gate remains mandatory before research ingest (1,826 matches expected).
- Rights remain attributed to the original CC BY 4.0 dataset; the GitHub mirror is transport only.
- This packaged canonical DB still contains 0 Wyscout research-player rows: the build runtime could not fetch the large raw archive, and no synthetic rows were created.

## v2.4 — MASTER Stats Monitor v1.0

Current-season automatic statistics collection is now implemented.

Key commands:

```bash
# First current fixture catalog bootstrap (requires API_FOOTBALL_KEY)
PYTHONPATH=. python -m master_data.cli stats-monitor-bootstrap-defaults

# See what would be collected next
PYTHONPATH=. python -m master_data.cli stats-monitor-targets

# Run one quota-safe collection cycle
PYTHONPATH=. python -m master_data.cli stats-monitor-cycle

# Status
PYTHONPATH=. python -m master_data.cli stats-monitor-status
```

For automatic operation use `scripts/run_stats_monitor.py` or the bundled Windows Task Scheduler helper. Live collection is opt-in; default operation prioritizes one pre-match context capture and one post-match final capture so the free request budget is spent on building training history rather than noisy repeated live polling.

See `STATS_MONITOR_README_CZ.md`.
