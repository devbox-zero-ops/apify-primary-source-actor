# Primary-Source Macro, Regulatory & Market Data Extractor (Apify Actor)

Extract clean, timestamped, structured JSON records from **8 zero-key official primary-source APIs** without managing API keys or fragile HTML scrapers:

- `fred` — Federal Reserve Economic Data (`ICSA`, `CCSA`, `PAYEMS`, `CPIAUCSL`, `DGS10`, etc.)
- `defillama` — DeFi Protocol TVL & multi-chain metadata
- `github_releases` — Official GitHub release tags & publication timestamps
- `wikipedia_stats` — Live MediaWiki `siteinfo` article & edit counts
- `arxiv` — Latest scientific preprints ordered by submission date
- `usgs_quake` — Real-time USGS earthquake GeoJSON feed
- `openfda` — FDA drug adverse event reports
- `clinicaltrials` — ClinicalTrials.gov v2 study status records

## Standalone Local Usage

```bash
python -m src.main --source wikipedia_stats --query en --limit 1
python -m src.main --source github_releases --query oven-sh/bun --limit 3
python -m src.main --source defillama --query aave --limit 1
```

## Apify Store Deployment

Push this directory directly with `apify push` and enable **Pay-per-Event** pricing (`dataset_item`) to monetize automated agent & research workflows.
