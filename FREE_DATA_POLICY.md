# MASTER Football — FREE DATA POLICY v2.0

## Cíl
MASTER Free Data Engine má fungovat bez povinného placeného datového providera. Free-only neznamená obcházení paywallů, loginů, rate-limitů nebo licencí. Používají se pouze veřejné/open zdroje a legitimní free API tarify.

## Povolené vrstvy
- Football-Data.co.uk Public: historické match/stat/main-odds jádro + veřejný current fixture scanner. Current CSV ceny jsou MASTER fetch observations, ne automaticky exact opening/closing.
- OpenFootball Europe / Champions League: CC0 result history; CZ a UEFA jsou EXPERIMENTAL domains a vyžadují vlastní validaci.
- Wyscout/Pappalardo Open: CC BY 4.0 player/event research 2017/18 Big-5; attribution required. Actual XI je post-match truth, ne archived prematch lineup.
- StatsBomb Open: selective research-only event/xG/lineup data; ne souvislý production feed.
- API-Football Free Tier a The Odds API Free Tier: volitelné quota-aware current collectors. API secrets pouze z environment variables.

## Vlastní archiv
Od okamžiku sběru MASTER ukládá každou pozorovanou cenu/context snapshot s `observed_at`. Historii nelze zpětně "dopočítat".

### Temporal firewall
Veřejný fixture CSV bez exact event-time contractu používá konzervativní `event_temporal_relation`:
- PRE_EVENT_DATE = event date je až po datu našeho fetchu;
- POST_EVENT_DATE = event date už byla před fetchem;
- SAME_DATE_UNKNOWN = stejný den, bez bezpečné časové relace;
- UNKNOWN = nelze určit.

Pro prematch market-history readiness se počítá pouze bezpečně pre-event historie; post-event a same-day-unknown se nesmí vydávat za prematch market evidence.

## Modelový firewall
FREE DATA AVAILABLE != FEATURE VALIDATED != MODEL ACTIVE.
Žádná nová open/free data vrstva nesmí automaticky měnit model registry. Každá feature/market family musí projít frozen walk-forward/OOS, calibration, market comparison a příslušný promotion gate.
