# Wyscout Open ingest status — v2.1

## Contract

- Dataset role: OPEN RESEARCH player/minutes/event history.
- License class: CC BY 4.0 with attribution.
- Target domestic sample: Big-5 2017/18.
- Expected matches: 1,826.
- Historical actual XI/substitutions: POST-MATCH truth only; not archived pre-match information.

## Strict admission checks

`wyscout-validate` checks:

- players.json and teams.json exist;
- England = 380 matches;
- France = 380;
- Germany = 306;
- Italy = 380;
- Spain = 380;
- total = 1,826;
- event match IDs do not point outside the corresponding match file.

If strict coverage fails, the all-Big-5 ingest fails instead of pretending the research dataset is complete.

## Features available from current adapter

- starter/substitute reconstruction;
- approximate minutes from substitutions/red-card timing;
- position/role prior;
- shots;
- SOT research proxy with explicit definition;
- goals;
- fouls committed;
- yellow/red cards;
- attacking dribbles / successful dribbles;
- crosses.

`fouls_drawn` is intentionally NULL because the current adapter cannot safely identify the fouled player from the public event representation.

## Packaged build status

The build runtime failed public Figshare downloads with a DNS resolution error. No fake replacement or partial research sample was inserted. Canonical `research_player_match_stats` rows therefore remain 0 in the packaged DB.

Use `scripts/download_wyscout_open.py`, then `wyscout-validate`, then `wyscout-ingest-all` in an environment with normal network access.
