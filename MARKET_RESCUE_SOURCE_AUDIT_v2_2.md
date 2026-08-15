# FREE Secondary Odds Source Audit — v2.2

## Accepted acquisition path
**Betfair Historical Data BASIC**
- zero-cost tier after account login/purchase flow,
- sampled 1-minute last-traded price,
- no volume,
- near-complete Exchange history since 2016 according to Betfair Data Scientists guide,
- supports market-type filtering and market files,
- historical football market types include corner O/U and total-card examples,
- MASTER raw redistribution prohibited by project source policy; operator-owned/account-licensed files only.

## Useful research bonus
**Betfair May 2015–Apr 2016 ADVANCED/PRO** — official £0 acquisition period. Useful for parser/liquidity research but outside current v2 OOS test window.

## Rejected / insufficient paths
- Football-Data.co.uk: excellent match stats/main odds, but no verified historical two-sided secondary corner/card/foul price archive suitable for this gate.
- The Odds API free current tier: useful for own future recorder; historical additional-market backfill is not a zero-cost solution.
- public GitHub/Kaggle search: no source found that simultaneously provides verified long-run two-sided secondary closing prices, timestamps, settlement semantics and clear redistributable rights.
- scraped OddsPortal/other bookmaker-history approaches: not adopted as canonical free path due rights/ToS/provenance concerns.

## Current canonical truth
Parser + link + no-vig + validator are implemented. Bundled DB contains zero Betfair historical rows, because authenticated operator download is not bundled or bypassed.
