# CURRENT NOTE — v2.0 FREE STACK
FREE_DATA_POLICY.md is the current authority for free/open acquisition, temporal recorder semantics and legal access. The inherited rules below remain applicable unless superseded.

# SOURCE POLICY v1.5

## Source truth hierarchy

Official competition/club -> licensed/reliable event provider -> validated market reference feed -> execution books -> reliable media/context.

A source's authority is task-specific: an official current fixture page is not automatically a historical training feed; a historical event dataset is not automatically a market reference.

## No silent identity merge

Different provider IDs are never fused from approximate names alone. External fixture data require an explicit verified `fixture_source_links` row. Player aliases are source-specific.

## Credentials and secrets

API credentials are never bundled in project source files, database provenance rows, request fingerprints or exported reports. Runtime adapters read credentials from environment variables only.

## Advanced data

xG, event, lineup, availability, transfer and player metrics must retain source provenance and observation/availability semantics.

Post-match xG can be used as history only for later fixtures through shifted/as-of features. The current fixture's own post-match xG can never enter its pre-match snapshot.

Historical actual XI with unknown publication timestamp may be useful for post-match/player-history research, but cannot be represented as if it were known pre-match.

## StatsBomb Open Data

Research adapter only. Coverage is partial by competition/season and must not be presented as a complete current Big-5/UEFA production feed. Capabilities are registered `RESEARCH_ONLY`.

## Commercial providers

The engine includes adapters for Sportmonks and The Odds API, but adapter availability is not proof that the user's subscription covers the target competition/season/market. Coverage must be verified from real fetch activity and ingested provenance.

## Market sources

Bookmaker name does not imply sharp truth. Sharp/reference/execution role is explicit and separately validated.

`observed_at` is the provider/bookmaker observation time when known; `ingested_at` is only local ingestion time. A T-5m snapshot is explicitly labelled `CLOSING_PROXY`, not exact bookmaker close.

Exact CLV, stale-price and line-movement claims require adequate timestamp semantics and same-line/same-market matching.


## Research-rights firewall (v1.6)

An external dataset with no verified redistribution/production rights is `RESEARCH_ONLY`. It may be normalized to an external staging artifact but must not populate canonical production xG or authorize a model-registry change. Raw research data are not bundled. A rights-cleared source must repeat the frozen validation protocol before deployment.


## Player / secondary source rules (v1.7)

- Historical actual XI/injury truth is not retroactively pre-match evidence without an archived observation timestamp.
- API-Football current odds are not a deep historical validation archive; recent odds must be captured prospectively if used.
- The Odds API additional-market availability is verified per sport/date/bookmaker/market; adapter capability is not coverage.
- One-sided player prices never receive invented NO prices.
- CZ historical secondary-market source remains unresolved until a rights-cleared source is actually integrated.
- Betfair Historical Data is a candidate source, not canonical data until a parser + explicit mapping pipeline is implemented.

## v2.1 Open UEFA result contract
OpenFootball UCL/UEL/UECL sources are CC0 result-history inputs. Administrative awards/cancellations are not football-performance observations and are excluded. For AET matches, canonical goals represent the 90-minute result; AET and shootout results are retained only as knockout/source evidence.

## v2.1 Wyscout research contract
Wyscout Open is a CC BY 4.0 research source. Full Big-5 2017/18 ingest requires strict 1,826-match coverage validation. Historical actual lineups are post-match truth, never automatically pre-match knowledge. Ingestion alone cannot change a player model from NO MODEL/PROVISIONAL to ACTIVE.
