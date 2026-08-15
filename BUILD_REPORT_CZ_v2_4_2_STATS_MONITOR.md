# MASTER Football v2.4.2 — STATS MONITOR BUILD REPORT

## Implementováno

Data + Market Engine byl povýšen z v2.3 na **v2.4** a dostal `MASTER Stats Monitor v1.0`.

Nové hlavní části:
- `master_data/stats_monitor.py`,
- API-Football current fixture catalog ingestion,
- `fixture_stat_snapshots`,
- `player_stat_snapshots`,
- `stats_monitor_state`,
- `stats_monitor_watchlist`,
- CLI `stats-monitor-*`,
- `scripts/run_stats_monitor.py`,
- Windows `.bat` launchery,
- PowerShell Task Scheduler installer.

## Provozní logika

`CURRENT LEAGUE DISCOVERY -> FIXTURE CATALOG -> PREMATCH SNAPSHOT -> OPTIONAL LIVE SNAPSHOTS -> POSTMATCH FINAL SNAPSHOT -> CANONICAL TEAM/PLAYER STATS`

Scheduler je phase-aware a quota-aware. Default live collection je vypnutá. Hlavním cílem v1.0 je kvalitní current-season training history, ne plýtvání free requesty na live refresh každých pár minut.

## Reálný DB dry-run

Forward migration na kopii packaged canonical DB:
- fixtures 15 768 zachováno,
- team stats 15 768 zachováno,
- odds 19 656 zachováno,
- feature snapshots 59 435 zachováno,
- database audit `ok=true`.

## Testy

Data + Market Engine v2.4: **38/38 PASS**.

Player/Model/Validation status se tímto patchem nemění:
- 8 PROVISIONAL,
- 12 NO MODEL,
- 0 ACTIVE.

Stats history je datová infrastruktura. Sama o sobě nepovoluje žádný BET ani model promotion.
