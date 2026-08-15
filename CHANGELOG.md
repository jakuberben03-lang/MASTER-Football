# Changelog

## v2.0.0 — Free Data Stack
- Legal free/open acquisition strategy.
- Football-Data public odds recorder with temporal relation firewall.
- OpenFootball CC0 UCL/qualification result-history seed and fixture-level UEFA domains.
- Wyscout Open player/event research pipeline and synthetic regression tests.
- Quota-aware optional current APIs.
- Own history coverage/readiness accounting.
- Legacy source-ID conflict fix in `ensure_source`.
- 27 Data Engine tests.

# CHANGELOG

## v1.7.0 — 2026-08-12

- Added API-Football league-season coverage discovery and fixture-centred player/lineup/injury backfill adapter.
- Historical actual lineup/injury backfills are post-kickoff guarded unless genuine archived pre-match timing is proved.
- Added `fixture_link_proposals` staging; exact cross-provider links require explicit approval before canonical linking.
- Added player-match ingest for minutes, starting status, position, shots/SOT, goals/assists, fouls committed/drawn, cards and dribbles where available.
- Added research-only Understat-derived player shot staging; research output explicitly reports missing minutes/lineups and cannot activate a player model.
- Extended The Odds API adapter to historical event-level secondary/player markets after its documented additional-market history boundary.
- Added participant-aware odds identity and no-vig isolation to prevent cross-player/cross-team market contamination.
- Added canonical acquisition plan for player data, secondary-market history, CZ and UEFA.
- Fixed API-Football backfill quota estimator to count fixture-detail calls in the current bundle contract.
- Schema metadata advanced to 1.7.0; migrations remain idempotent.
- **19/19 unit/regression tests PASS.**

## v1.6.0

- Added research-only xG staging and provider-neutral licensed xG ingest with data-rights gates.

## v1.5.0

- Added Sportmonks/The Odds API provider foundations, provider provenance, schema migrations and strict market group isolation.

## v2.1 — 2026-08-13
- Added UEL + UECL open result history and 2024/25 qualification seeds.
- Added source-declared match reconciliation; cancelled/awarded fixtures do not enter performance history.
- Fixed AET semantics: canonical team goals are 90-minute goals; AET/shootout truth stored separately in evidence.
- Added HT parsing for normal and AET notation.
- Added strict Wyscout full-Big5 2017/18 validation and one-command all-competition ingest.
- Added explicit unsupported `fouls_drawn` contract rather than inference.
- Rebuilt leakage-safe PRE_FIXTURE feature set `master_team_features_v2.1`.

## v2.2 — 2026-08-13
- Added official Betfair Historical Data stream parser for TAR/BZ2/GZ/JSON.
- Added marketType discovery and half-point total corners/cards normalization.
- Added Exchange market/runner/tier/price-age/pair-skew provenance columns.
- Added explicit date+exact-team/manual approval path for historical canonical fixtures with unknown kickoff time.
- Added ENTRY/CLOSING LTP targets, two-sided no-vig and stale/asynchronous pair guardrails.
- Whole-number push lines are intentionally not mapped to binary >=k targets.
- Raw Betfair files are never bundled.
- Current cards validation is blocked by settlement-target mismatch; fouls historical Exchange mapping remains unavailable.

## v2.3 — 2026-08-13
- Added Figshare -> GitHub raw-data mirror fallback for Wyscout Open.
- Preserved strict completeness/license gates before player research ingest.
- No canonical player rows were fabricated; packaged DB remains at zero Wyscout rows.

## v2.4 — 2026-08-13 — MASTER Stats Monitor v1.0
- Added API-Football current fixture catalog ingestion with explicit provider fixture IDs.
- Added one-call current league discovery + current fixture catalog bootstrap for Big-5, Czech top flight and optional UEFA club competitions.
- Added time-versioned team-stat snapshots: shots, SOT, blocked shots, fouls, corners, cards, xG, possession, offsides, saves and passes where provider supplies them.
- Added time-versioned player-stat snapshots: minutes, start flag, position, shots/SOT, goals/assists, fouls committed/drawn, cards and dribbles where supplied.
- Added phase-aware scheduler: PRE_MATCH once/retry-until-lineup, optional LIVE, POST_MATCH finalization.
- Final stats are materialized into canonical `team_match_stats` / `player_match_stats` only after provider final status.
- AET/PEN result goals are not silently treated as 90-minute goals.
- Added `stats_monitor_state` and `stats_monitor_watchlist` for idempotent finalization and opt-in live collection.
- Added quota-aware runner and Windows Task Scheduler helper. Default live monitoring is OFF to protect the free 100-request/day budget.
- Missing `API_FOOTBALL_KEY` = SKIPPED, never fabricated data or fatal canonical corruption.
- Schema version advanced to 2.4.0.
- Test suite: **38/38 PASS**.
