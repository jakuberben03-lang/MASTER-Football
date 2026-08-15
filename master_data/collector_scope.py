from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompetitionTarget:
    domain: str
    api_name: str
    country: str | None
    aliases: tuple[str, ...] = ()
    odds_titles: tuple[str, ...] = ()
    enabled: bool = True


TARGETS: tuple[CompetitionTarget, ...] = (
    CompetitionTarget("ENG_PREMIER_LEAGUE", "Premier League", "England", odds_titles=("Premier League", "EPL", "English Premier League")),
    CompetitionTarget("ENG_CHAMPIONSHIP", "Championship", "England", aliases=("EFL Championship",), odds_titles=("EFL Championship", "Championship")),
    CompetitionTarget("ESP_LA_LIGA", "La Liga", "Spain", odds_titles=("La Liga", "La Liga - Spain")),
    CompetitionTarget("GER_BUNDESLIGA", "Bundesliga", "Germany", odds_titles=("Bundesliga", "Bundesliga - Germany")),
    CompetitionTarget("ITA_SERIE_A", "Serie A", "Italy", odds_titles=("Serie A", "Serie A - Italy")),
    CompetitionTarget("FRA_LIGUE_1", "Ligue 1", "France", odds_titles=("Ligue 1", "Ligue 1 - France")),
    CompetitionTarget("CZ_FIRST_LEAGUE", "Czech Liga", "Czech Republic", aliases=("Chance Liga", "1. Liga"), odds_titles=("Czech First League", "Czech Liga", "Chance Liga")),
    CompetitionTarget("NED_EREDIVISIE", "Eredivisie", "Netherlands", odds_titles=("Eredivisie", "Eredivisie - Netherlands")),
    CompetitionTarget("BEL_PRO_LEAGUE", "Jupiler Pro League", "Belgium", aliases=("Pro League",), odds_titles=("Belgian First Division A", "Belgian Pro League", "Jupiler Pro League")),
    CompetitionTarget("POR_PRIMEIRA_LIGA", "Primeira Liga", "Portugal", odds_titles=("Primeira Liga", "Primeira Liga - Portugal")),
    CompetitionTarget("DEN_SUPERLIGA", "Superliga", "Denmark", aliases=("Danish Superliga",), odds_titles=("Denmark Superliga", "Danish Superliga", "Superliga - Denmark")),
    CompetitionTarget("NOR_ELITESERIEN", "Eliteserien", "Norway", odds_titles=("Eliteserien", "Eliteserien - Norway")),
    CompetitionTarget("SWE_ALLSVENSKAN", "Allsvenskan", "Sweden", odds_titles=("Allsvenskan", "Allsvenskan - Sweden")),
    CompetitionTarget("UEFA_CHAMPIONS_LEAGUE", "UEFA Champions League", None, odds_titles=("UEFA Champions League", "Champions League")),
    CompetitionTarget("UEFA_EUROPA_LEAGUE", "UEFA Europa League", None, odds_titles=("UEFA Europa League", "Europa League")),
    CompetitionTarget("UEFA_CONFERENCE_LEAGUE", "UEFA Conference League", None, aliases=("UEFA Europa Conference League",), odds_titles=("UEFA Conference League", "Europa Conference League", "Conference League")),
)


def normalize(value: str | None) -> str:
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in (value or "")).split())


def exact_api_target_matches(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Resolve provider league rows only by exact normalized declared name/country aliases."""
    selected: list[dict] = []
    missing: list[dict] = []
    for target in TARGETS:
        names = {normalize(target.api_name), *(normalize(a) for a in target.aliases)}
        candidates = []
        for row in rows:
            league = row.get("league") or {}
            country = (row.get("country") or {}).get("name")
            if normalize(league.get("name")) not in names:
                continue
            if target.country and normalize(country) != normalize(target.country):
                continue
            current = [s for s in (row.get("seasons") or []) if s.get("current")]
            if len(current) == 1 and league.get("id") is not None and current[0].get("year") is not None:
                candidates.append((league, current[0], country))
        if len(candidates) == 1:
            league, season, country = candidates[0]
            selected.append({
                "domain": target.domain,
                "league_id": int(league["id"]),
                "season": int(season["year"]),
                "provider_name": league.get("name"),
                "country": country,
            })
        else:
            missing.append({"domain": target.domain, "target": target.api_name, "matches": len(candidates)})
    return selected, missing


def exact_odds_sport_matches(sports: list[dict]) -> tuple[dict[str, dict], list[dict]]:
    """Resolve The Odds API sports by exact declared titles; never guess a sport key."""
    by_title: dict[str, list[dict]] = {}
    for sport in sports:
        by_title.setdefault(normalize(sport.get("title")), []).append(sport)
    resolved: dict[str, dict] = {}
    missing: list[dict] = []
    for target in TARGETS:
        hits: list[dict] = []
        for title in target.odds_titles:
            hits.extend(by_title.get(normalize(title), []))
        uniq = {str(x.get("key")): x for x in hits if x.get("key")}
        if len(uniq) == 1:
            resolved[target.domain] = next(iter(uniq.values()))
        else:
            missing.append({"domain": target.domain, "matches": len(uniq), "declared_titles": list(target.odds_titles)})
    return resolved, missing
