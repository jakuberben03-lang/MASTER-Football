# CURRENT NOTE — v2.0 FREE STACK
Paid-provider setup below is optional legacy capability. MASTER v2.0 must function without paid providers; use README.md / FREE_DATA_POLICY.md for current operation.

# PROVIDER SETUP — MASTER Data + Market Engine v1.7

No API credential is bundled or stored in the database.

## 1. API-Football — player / lineup / injury / CZ / UEFA candidate

Set only at runtime:

```bash
export API_FOOTBALL_KEY='...'
```

Before downloading history, inspect **league-season coverage**. Do not assume one season has the same fields as another:

```bash
python -m master_data.cli api-football-coverage --name "Czech Liga" --season 2025
python -m master_data.cli api-football-coverage --name "UEFA Champions League" --season 2025
```

The coverage response decides whether lineups, fixture stats, player stats and injuries should even be requested.

For bulk history:
1. fetch season fixtures,
2. stage exact canonical link proposals,
3. explicitly approve exact proposals,
4. fetch fixture bundles,
5. ingest them as `historical_backfill=True`.

Historical actual XI/injury records without archived publication time are deliberately timestamped **after kickoff**, so they may describe player history but cannot leak into a pre-match backtest.

The provider's current `/odds` endpoint is **not** a deep historical archive. MASTER therefore does not use API-Football as the main source for historical secondary-market validation.

## 2. The Odds API — historical market snapshots

Set:

```bash
export THE_ODDS_API_KEY='...'
```

Featured-market plan:

```bash
python -m master_data.cli odds-api-plan 2026-08-15T18:00:00Z
```

Secondary/player plan:

```bash
python -m master_data.cli odds-api-secondary-plan 2026-08-15T18:00:00Z
```

Historical secondary workflow:
1. query historical events for a sport/snapshot,
2. explicitly link provider event ID to canonical fixture,
3. fetch event-level historical odds at T-24h / T-6h / T-60m / T-5m,
4. ingest exact participant-aware odds,
5. run market normalization and readiness audit.

Mapped soccer families include corners, cards and selected player props. The provider currently documents soccer player props for Big-5 + MLS with selected US bookmakers; MASTER therefore must not assume UEFA/CZ player-prop coverage. All additional-market availability still depends on the actual sport/date/bookmaker/market response. The T-5m point remains a **CLOSING_PROXY**, not proof of the bookmaker's final tick.

Verified UEFA sport keys encoded in the acquisition plan:
- `soccer_uefa_champs_league`
- `soccer_uefa_champs_league_qualification`
- `soccer_uefa_europa_league`
- `soccer_uefa_europa_conference_league`

MASTER does not hard-code a Czech Liga sport key because it has not been verified in the provider catalogue.

## 3. Betfair Historical Data — secondary reference candidate

Betfair provides time-stamped Exchange historical price/market data. It is a useful candidate for a second historical reference, particularly where bookmaker additional-market coverage is thin.

**Current MASTER status:** source candidate documented, but no canonical Betfair stream parser is included in v1.7. Do not claim Betfair coverage until purchased files are actually parsed and mapped.

## 4. Understat-derived player research

Research staging only:

```bash
python -m master_data.cli understat-player-research /external/shots.csv --out /tmp/player_research.csv
```

The external research file used during development produced large shot-event coverage but no reliable historical minutes or pre-match lineup timing. It therefore cannot satisfy `NO MINUTES = NO PLAYER BET`.

## 5. Admission sequence

`COVERAGE PROBE -> FETCH/PROVENANCE -> EXPLICIT FIXTURE LINK -> TIMING AUDIT -> NORMALIZED DATA -> AS-OF FEATURES -> FROZEN A/B -> MARKET COMPARISON -> MODEL REVIEW`.

No provider adapter or paid subscription can skip this sequence.
