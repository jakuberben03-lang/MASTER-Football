# MASTER — Betfair FREE Historical Market Guide v2.2

## Účel
Zero-cost historická market-reference cesta pro secondary markets. MASTER raw Betfair data NEBUNDUJE ani nepřerozděluje. Operátor smí ingestovat pouze soubory, které získal přes vlastní oprávněný Betfair Historical Data účet/licenci.

## Co MASTER umí
- skenovat oficiální Betfair stream JSON v TAR/BZ2/GZ/JSON,
- objevit marketType coverage před ingestem,
- normalizovat half-point TOTAL CORNERS (`OVER_UNDER_*_CORNR`),
- archivovat half-point TOTAL CARDS (`OVER_UNDER_*_CARDS`) pro budoucí settlement-aligned model,
- stageovat fixture links bez fuzzy auto-merge,
- explicitně schválit unikátní date+exact-team link tam, kde canonical Football-Data zná datum, ale ne kickoff čas,
- vytvářet ENTRY (T-1h) a CLOSING (last LTP <= kickoff) snapshots,
- vyžadovat současně OVER + UNDER,
- počítat no-vig reference,
- ukládat price age, runner pair skew, market ID, runner ID a tier,
- odmítnout whole-number push lines pro současné binary >=k OOS targety,
- odmítnout stale/asynchronous runner pair podle ingest guardrailů.

## Free acquisition
Oficiální Betfair Historical Data BASIC tier je zero-cost, ale vyžaduje Betfair účet a formální £0 purchase/download flow. BASIC = 1-minute sampled last traded price, bez volume. Raw files zůstávají mimo MASTER source pack.

Doporučený download pro současný MASTER OOS window:
- Football
- 2022/23 až 2025/26
- BASIC
- File Type: Market (M)
- market types obsahující corner O/U; cards lze stáhnout také pro budoucí target, ale current yellow-card model s nimi NESMÍ být validován.
- stahovat raději po měsících.

Historický bonus: květen 2015 až duben 2016 je podle Betfair dostupný za £0 i pro ADVANCED/PRO. Je vhodný pro parser/liquidity research, ale není to současné OOS období MASTERu.

## Workflow po stažení
```bash
python -m master_data.cli --db data/master_football.db betfair-scan PATH_TO_TAR_OR_FILES
python -m master_data.cli --db data/master_football.db betfair-stage-links PATH_TO_TAR_OR_FILES
python -m master_data.cli --db data/master_football.db betfair-approve-date-links --acknowledge-canonical-time-unknown
python -m master_data.cli --db data/master_football.db betfair-ingest PATH_TO_TAR_OR_FILES --tier BASIC --snapshots ENTRY,CLOSING
python -m master_data.cli --db data/master_football.db betfair-readiness
```

Potom Validation Engine:
```bash
python run_secondary_market_validation.py \
  --model-root PATH_TO_MASTER_Model_Engine_v2_0_1 \
  --db PATH_TO_master_football.db \
  --oos-predictions reports/MULTI_FAMILY_OOS_PREDICTIONS_v2_2.csv \
  --out reports/SECONDARY_MARKET_VALIDATION_v2_3.json
```

## Market-specific safety
### Corners
Current total-corners OOS targets jsou kompatibilní s half-point total corner lines na 90 minut. Lze validovat po skutečném ingestu.

### Cards
Current MASTER cards target = Football-Data yellow cards (`HY+AY`). Betfair Total Cards má jiné settlement counting rules včetně red-card handling. Proto:
`CURRENT CARDS MODEL vs BETFAIR TOTAL CARDS = BLOCKED_SETTLEMENT_TARGET_MISMATCH`.
Archivovat data lze; validovat současný model ne.

### Fouls
MASTER nemá ověřenou kompatibilní Betfair historical Exchange foul market mapping. Cards nejsou foul-price proxy.
`FOULS = BLOCKED_NO_COMPATIBLE_HISTORICAL_EXCHANGE_MARKET`.

## Reference confidence
BASIC LTP nemá volume ani full ladder. MASTER ho proto drží maximálně jako market reference confidence B. Nesmí se vydávat za jistý liquid sharp executable close.

## Absolute rules
- NO RAW FILE = NO MARKET VALIDATION.
- NO EXPLICIT FIXTURE LINK = NO INGEST.
- NO TWO-SIDED PAIR = NO NO-VIG.
- WHOLE NUMBER PUSH LINE != BINARY >=k TARGET.
- CARDS SETTLEMENT MISMATCH = NO CURRENT CARDS MARKET VALIDATION.
- FOULS MARKET UNKNOWN = NO FOULS MARKET VALIDATION.
- MARKET EVIDENCE != AUTOMATIC ACTIVE.
