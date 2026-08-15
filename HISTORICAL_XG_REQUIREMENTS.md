# Historical xG acquisition requirements — MASTER v1.6

A source suitable for production feature admission should provide, at minimum:

- rights-cleared commercial/internal use,
- Big-5 multi-season history sufficient for development + untouched confirmation folds,
- stable fixture/team identifiers or a verifiable mapping export,
- team xG for both sides of each match,
- metric definition/model-version metadata where available,
- reproducible download/export/API mechanism,
- post-match availability semantics,
- enough market overlap for same-row closing comparison.

Preferred target window for the first licensed repeat: **2015/16 through 2024/25 or deeper**, with at least two untouched recent confirmation seasons.

Current provider notes:
- Sportmonks adapter exists, but its current documented xG coverage is too recent for the frozen historical confirmation protocol on its own.
- MASTER therefore supports a provider-neutral licensed CSV path so a deeper archive from Opta/Stats Perform, StatsBomb commercial, Sportradar or another rights-cleared provider can be ingested without redesigning the model layer.

No provider is approved as "market truth" or "model truth" merely by brand name. Coverage and rights must be audited on the purchased package.
