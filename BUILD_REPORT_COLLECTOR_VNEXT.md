# MASTER Football Collector vNext — Build Report

**Build date:** 2026-08-15  
**Status:** IMPLEMENTED + LOCALLY TESTED / NOT DEPLOYED

## Implemented

- centralized `master_data/collector_scope.py`,
- 13 domestic + 3 UEFA acquisition scope,
- expanded API-Football default fixture catalog bootstrap,
- current The Odds API `/sports` capability discovery,
- exact configured sport-key resolution with no fuzzy substitution,
- UCL regular + qualification sport-key support where provider exposes it,
- Czech odds-provider gap explicitly represented instead of guessed,
- quota-paced current odds planner based on upcoming canonical fixtures,
- month-preserving daily credit envelope,
- broad default `h2h` odds history with optional deeper featured markets,
- unified `scripts/run_collector_vnext.py`,
- GitHub Actions workflow template with hourly collection + daily fixture bootstrap,
- persistent collector DB/raw-state cache template.

## Verification

- new Collector vNext tests: **3/3 PASS**,
- original Data Engine tests + new tests: **41/41 PASS**,
- Python compile: PASS,
- no live user API secrets used,
- no external collector deployment performed.

## Authority

This patch changes **data acquisition coverage only**.
It does not change the canonical model registry or betting authority.
Current source-pack authority remains **8 PROVISIONAL / 12 NO MODEL / 0 ACTIVE** unless a newer runtime registry proves otherwise.

## Remaining deployment blocker

A real persistent runtime needs:
1. a GitHub repository (or another host),
2. an initial canonical DB seed,
3. `API_FOOTBALL_KEY`,
4. `THE_ODDS_API_KEY`,
5. first real workflow run and resulting runtime audit.

Only after that can the collector be called DEPLOYED/RUNNING.
