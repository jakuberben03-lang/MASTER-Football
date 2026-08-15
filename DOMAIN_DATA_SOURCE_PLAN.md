# CURRENT NOTE — v2.0 FREE STACK
The free/open domain plan is now implemented in part: bundled CZ result history plus OpenFootball CC0 UEFA seed. See README.md and reports/STATUS_v2_0.md for actual current coverage.

# MASTER Domain Data Source Plan v1.7

## Global rule

`PROVIDER CAPABILITY REGISTERED != SUBSCRIPTION COVERAGE != DATA INGESTED != PREMATCH-KNOWN != FEATURE VALIDATED != MODEL ACTIVE`.

## BIG5_DOMESTIC

Canonical history: 12,459 fixtures / 7 seasons. Player-match/lineup/injury history is not yet bundled. Secondary-market exact history is not yet bundled.

Acquisition path:
- API-Football or another rights-cleared provider for player-match history, lineups and injuries after league-season coverage verification.
- The Odds API historical event odds for corners/cards and, in its currently documented scope, selected Big-5 player markets. Do not infer UEFA/CZ player-prop coverage.
- Betfair Historical Data as a possible second exchange reference after a canonical parser/mapping path is implemented.
- frozen family-specific player/corners/cards/fouls validation before deployment.

## CZ_FIRST_LEAGUE

Integrated now:
- 1,136 result-history fixtures from 4 partial public seasons.

Still missing:
- player-match/minutes history,
- archived pre-match lineups/availability history,
- exact historical secondary-market prices,
- continuous advanced/event data.

API-Football is the current player/lineup/injury acquisition candidate, but coverage must be probed by Czech Liga season. Deep historical market source remains unresolved; API-Football's current odds endpoint is not a deep archive and The Odds API Czech sport-key coverage is not assumed.

Status: **EXPERIMENTAL**.

## UEFA

Fixture domains stay separate:
- `UEFA_LEAGUE_PHASE`
- `UEFA_KNOCKOUT`
- `UEFA_QUALIFYING`

API-Football can be probed for UCL/UEL/UECL player/lineup/injury history by season. The Odds API has verified sport keys for UCL, UCL qualification, UEL and UECL and historical market snapshots are therefore a concrete market-acquisition path for those competitions where the requested market/bookmaker actually exists.

Knockout/qualification additionally requires stage, leg, aggregate-before, extra-time/penalty rules, away-goals rule state and cross-league-strength treatment.

Current canonical UEFA fixture/player/market history: 0. All UEFA domains remain **EXPERIMENTAL / NOT READY**.
