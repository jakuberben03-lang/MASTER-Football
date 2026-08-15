# MASTER Football Collector vNext — CZ README

## Stav

**IMPLEMENTED + LOCALLY TESTED / NOT DEPLOYED**

Tato vrstva pouze sbírá data. **Neaktivuje žádný model a nepovoluje BET.**

## Scope

13 domácích soutěží:
- Premier League
- EFL Championship
- La Liga
- Bundesliga
- Serie A
- Ligue 1
- Chance Liga / Czech top flight
- Eredivisie
- Belgian Pro League
- Primeira Liga
- Danish Superliga
- Eliteserien
- Allsvenskan

UEFA:
- Champions League
- Europa League
- Conference League

API-Football fixture catalog zachovává provider-native league/round metadata; analytická UEFA phase klasifikace musí dál respektovat canonical domain/knockout context pravidla.

## Co dělá runner

`scripts/run_collector_vnext.py` orchestrace:

1. volitelný current fixture-catalog bootstrap přes API-Football,
2. Stats Monitor PRE/POST sběr,
3. broad veřejné Football-Data odds observation,
4. quota-paced The Odds API current odds pro soutěže s nejbližšími fixtures.

The Odds API `/sports` se používá jako live availability registry. Statické sport keys jsou pouze kandidáti; runner neháda neexistující soutěž.

## Quota policy

The Odds API free limit v canonical configu je 500 credits/měsíc s rezervou 50.
Planner proto:
- počítá zbývající spendable quota,
- rozpočítá ji přes zbývající dny měsíce,
- prioritizuje soutěže podle nejbližšího kickoffu,
- defaultně sbírá pouze `h2h` jako nejlevnější broad history.

`h2h,totals` lze zapnout explicitně, ale spotřeba je vyšší.

## GitHub Actions

Soubor `.github/workflows/master-collector-vnext.yml`:
- hourly collector cycle,
- daily fixture-catalog bootstrap,
- persistent state přes official GitHub Actions cache,
- secrets pouze z GitHub Secrets.

Potřebné secrets:
- `API_FOOTBALL_KEY`
- `THE_ODDS_API_KEY`

## První lokální spuštění

```bash
export API_FOOTBALL_KEY='...'
export THE_ODDS_API_KEY='...'
PYTHONPATH=. python scripts/run_collector_vnext.py --bootstrap-fixtures --current-odds
```

## Safety

- NO SECRET IN DB/SOURCE.
- NO FUZZY COMPETITION MATCH.
- NO GUESSED ODDS SPORT KEY.
- COLLECTION != MODEL VALIDATION.
- COLLECTION != ACTIVE.
- PROVISIONAL remains max WATCH/SHADOW.
