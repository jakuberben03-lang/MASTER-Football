# CURRENT NOTE — v2.0 FREE STACK
This file contains the inherited v1.7 architecture below. v2.0 adds the free-source/recorder layer documented in README.md and FREE_DATA_POLICY.md; newer rules supersede older acquisition assumptions.

# MASTER Data + Market Engine v1.7 — architecture

## Canonical flow

`SOURCE -> provider_fetch_log/raw provenance -> canonical entities -> explicit cross-source links -> time-versioned observations -> PRE_FIXTURE features -> model -> market audit -> prediction lock -> outcome -> validation`

## Hard boundaries

1. **Raw != normalized != feature != model.**
2. **Cross-source identity is explicit.** `fixture_source_links` accepts only EXPLICIT_ID / MANUAL_VERIFIED / OFFICIAL_MAPPING. No fuzzy fixture merge.
3. **Observation time matters.** Lineups, injuries and market prices are time-versioned. Context builder filters by `observed_at <= asof_utc`.
4. **Post-match research data cannot leak.** If source publication timing is unavailable, availability is guarded rather than invented.
5. **Provider coverage is a vector, not a promise.** Capability registry distinguishes PRODUCTION / PARTIAL / RESEARCH_ONLY / UNKNOWN; real fetch activity is required to prove coverage.
6. **Feature admission is external to ingestion.** Data being present does not allow a model to use it. Validation Engine must approve the feature group.
7. **LLM cannot convert context to hand-written probability adjustments.** Material context requires model recompute; otherwise WATCH/PASS/qualitative flag.
8. **Market observations are exact groups.** Never normalize across different source, line or requested timestamp.
9. **Schema upgrades are migrations.** Existing databases are upgraded idempotently; production evolution must not require recreating history.

## v1.6 provider/time-series tables

- `provider_fetch_log`
- `data_provider_capabilities`
- `fixture_source_links`
- `fixture_metric_provenance`
- `odds_snapshots` with provider/request/bookmaker timestamp semantics
- `lineup_snapshots`
- `lineup_snapshot_members`
- `player_availability_snapshots`
- `squad_memberships`
- `transfer_events`
- `player_feature_snapshots`

Legacy `lineups` remains for backwards compatibility, but new workflows should use time-versioned snapshots.


## v1.7 player / secondary market isolation

Player and participant markets use explicit participant identity. Cross-provider fixture candidates are staged before approval. Historical actual lineups/availability with unknown publication time remain post-kickoff guarded. Secondary odds are grouped by source/bookmaker/market/line/participant/snapshot/requested time.
