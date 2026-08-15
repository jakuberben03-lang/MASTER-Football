# MASTER Data + Market Engine v1.6 — Data Dictionary

- `fixtures`: canonical match identity.
- `team_match_stats`: FT/basic counts plus nullable advanced post-match metrics (`xg`, blocked shots, crosses, box touches, possession).
- `odds_snapshots`: immutable market observations; `observed_at` != `ingested_at`. v1.6 also tracks provider event ID, requested snapshot time, snapshot basis and bookmaker last update where available.
- `provider_fetch_log`: audit trail for provider requests/responses without persisting API secrets; stores request fingerprint, requested/provider time, response hash/raw path and result status.
- `feature_snapshots`: versioned LATEST/PRE_FIXTURE/MANUAL team features.
- `data_provider_capabilities`: registered provider capability/timing/license class. Registration alone is not data coverage.
- `fixture_source_links`: explicit external fixture ID -> canonical fixture mapping.
- `fixture_metric_provenance`: advanced metric observation with source, time/availability semantics and evidence.
- `lineup_snapshots`: time-versioned expected/predicted/confirmed/corrected XI snapshot.
- `lineup_snapshot_members`: players/roles inside one lineup snapshot.
- `player_availability_snapshots`: time-versioned AVAILABLE/DOUBTFUL/INJURED/SUSPENDED/ILL/RESTED status.
- `squad_memberships`: player-team membership intervals.
- `transfer_events`: effective + observed transfer/squad change events.
- `player_feature_snapshots`: versioned as-of player features; model status explicitly RESEARCH/PROVISIONAL/ACTIVE.
- `prediction_locks`: immutable pre-match truth; MODEL PROBABILITY requires REAL computation provenance.
- `prediction_outcomes`: closing/result/CLV/calibration/post-match thesis audit.

## Odds grouping contract

No-vig normalization is performed only inside an exact group keyed by canonical fixture, source, bookmaker, market, line, snapshot type and requested snapshot time. Duplicate selections inside one exact group are an error rather than silently deduplicated.
