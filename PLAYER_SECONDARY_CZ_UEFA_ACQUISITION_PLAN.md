# CURRENT NOTE — v2.0 FREE STACK
This inherited v1.7 plan is historical design context. Current free acquisition/readiness truth is in README.md, FREE_DATA_POLICY.md and Validation Engine v2.0.

# PLAYER / SECONDARY / CZ / UEFA ACQUISITION PLAN v1.7

## Track A — Player / lineup / injury

### Required research inputs before any dedicated player model can even start
- player match event history,
- minutes history,
- start/substitution history,
- stable role/position history,
- opponent/team context,
- pre-match lineup history with genuine observation time,
- pre-match availability history with genuine observation time,
- historical market prices for the exact player family.

### Current candidate
API-Football fixture ID links fixtures, lineups, player performance and injury endpoints. MASTER therefore uses it as the first production-candidate backfill path, subject to league-season coverage flags and subscription rights.

### Historical timing firewall
Actual lineup or injury data recovered after the match are useful for player history, but cannot be treated as pre-match known. In v1.7 historical backfill defaults to `POST_KICKOFF_GUARD`.

### Research-only evidence
The external Understat-derived player shot research file used during development normalized to:
- 204,458 player-match rows,
- 15,301 matches,
- 6,602 players,
- 0 reliable minutes coverage,
- 0 pre-match lineup coverage.

Conclusion: useful proof that shot-event staging works; **not sufficient for a player model**.

## Track B — Corners / cards / fouls historical market prices

### The Odds API target
Historical event odds after 2023-05-03 are the primary coded path for:
- total/team/handicap corners,
- total/handicap cards,
- selected player shots/SOT/cards/goals/assists.

Current provider documentation limits soccer player-prop coverage to Big-5 + MLS and selected US bookmakers. UEFA/CZ player-prop coverage must not be inferred.

Every stored selection is isolated by:
`fixture + source + bookmaker + market + line + participant + snapshot + requested time`.

### Remaining hole: fouls
No historical fouls market is declared available merely because card/corner markets are. Team/player fouls remain without a verified coded historical-price source in v1.7.

### Betfair candidate
Time-stamped Exchange historical data are a strong second-reference candidate. v1.7 documents the source but does not yet include a canonical Betfair parser; therefore it provides zero current canonical rows.

## Track C — Czech league and UEFA

### Czech league
Already integrated: 1,136 fixtures / 4 partial seasons.
Next acquisition:
1. API-Football Czech Liga coverage probe by season,
2. player/lineup/injury backfill only for returned capabilities,
3. explicit fixture links,
4. identify a rights-cleared deep historical secondary-market source,
5. run CZ-specific time-split/domain validation.

### UEFA
Next acquisition:
1. API-Football UCL/UEL/UECL coverage probe by season,
2. ingest fixtures + player/lineup/injury history,
3. assign fixture-level UEFA domain,
4. The Odds API historical event/market fetch for verified UEFA sport keys,
5. preserve league-phase vs knockout vs qualification split,
6. build/validate cross-league strength before official UEFA qualifying bets.

## Stop conditions
- Missing minutes -> no player model.
- Missing genuine pre-match lineup/availability timestamps -> those fields are context only, not historical predictive features.
- Missing exact two-sided historical price -> no market validation for that family.
- Fewer than adequate time-split seasons -> research only.
- CZ/UEFA data availability -> does not inherit Big-5 model validation.
