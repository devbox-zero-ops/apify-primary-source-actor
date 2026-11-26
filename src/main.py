"""Primary-Source Macro, Regulatory & Market Data Extractor (Apify Actor + Standalone CLI).

Zero third-party API keys required. Runs natively on Apify Cloud (Pay-per-Event / Dataset push)
or standalone via `python -m src.main --source fred --query ICSA --limit 5`.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any

UA = {"User-Agent": "DevBoxZeroOps-PrimarySourceActor/1.0 (+https://github.com/devbox-zero-ops)"}


def _fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "ignore")


def _fetch_json(url: str, timeout: int = 20) -> Any:
    return json.loads(_fetch_text(url, timeout=timeout))


def fetch_source(source: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    source = source.strip().lower()
    query = query.strip()
    limit = max(1, min(100, int(limit)))

    if source == "fred":
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={urllib.parse.quote(query)}&cosd=2024-01-01"
        lines = [ln for ln in _fetch_text(url).strip().splitlines() if ln and not ln.startswith("observation_date")]
        rows = []
        for ln in lines[-limit:]:
            parts = ln.split(",")
            if len(parts) >= 2 and parts[1] != ".":
                rows.append({
                    "source": "fred",
                    "series": query,
                    "date": parts[0],
                    "value": float(parts[1]),
                    "sourceUrl": url,
                    "fetchedAt": now,
                })
        return rows

    if source == "defillama":
        url = f"https://api.llama.fi/protocol/{urllib.parse.quote(query.lower())}"
        d = _fetch_json(url)
        tvl_list = d.get("tvl") or []
        latest_tvl = tvl_list[-1]["totalLiquidityUSD"] if tvl_list else None
        return [{
            "source": "defillama",
            "protocol": d.get("name", query),
            "symbol": d.get("symbol"),
            "category": d.get("category"),
            "chains": d.get("chains", [])[:10],
            "latestTvlUsd": round(float(latest_tvl), 2) if latest_tvl is not None else None,
            "sourceUrl": url,
            "fetchedAt": now,
        }]

    if source == "github_releases":
        url = f"https://api.github.com/repos/{query}/releases?per_page={limit}"
        rels = _fetch_json(url)
        return [
            {
                "source": "github_releases",
                "repo": query,
                "tag": r.get("tag_name"),
                "name": r.get("name"),
                "prerelease": r.get("prerelease"),
                "publishedAt": r.get("published_at"),
                "htmlUrl": r.get("html_url"),
                "fetchedAt": now,
            }
            for r in rels[:limit]
        ]

    if source == "wikipedia_stats":
        lang = query or "en"
        url = f"https://{urllib.parse.quote(lang)}.wikipedia.org/w/api.php?action=query&meta=siteinfo&siprop=statistics&format=json"
        stats = _fetch_json(url)["query"]["statistics"]
        return [{
            "source": "wikipedia_stats",
            "lang": lang,
            "articles": stats.get("articles"),
            "pages": stats.get("pages"),
            "edits": stats.get("edits"),
            "activeUsers": stats.get("activeusers"),
            "sourceUrl": url,
            "fetchedAt": now,
        }]

    if source == "arxiv":
        q = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{q}&start=0&max_results={limit}&sortBy=submittedDate&sortOrder=descending"
        root = ET.fromstring(_fetch_text(url))
        ns = {"a": "http://www.w3.org/2005/Atom"}
        out = []
        for entry in root.findall("a:entry", ns)[:limit]:
            out.append({
                "source": "arxiv",
                "id": (entry.findtext("a:id", "", ns) or "").strip(),
                "title": " ".join((entry.findtext("a:title", "", ns) or "").split()),
                "published": entry.findtext("a:published", "", ns),
                "sourceUrl": (entry.findtext("a:id", "", ns) or "").strip(),
                "fetchedAt": now,
            })
        return out

    if source == "usgs_quake":
        min_mag = query or "5.0"
        url = f"https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&minmagnitude={urllib.parse.quote(min_mag)}&limit={limit}"
        feats = _fetch_json(url).get("features", [])
        return [
            {
                "source": "usgs_quake",
                "id": f.get("id"),
                "magnitude": (f.get("properties") or {}).get("mag"),
                "place": (f.get("properties") or {}).get("place"),
                "timeMs": (f.get("properties") or {}).get("time"),
                "sourceUrl": (f.get("properties") or {}).get("url"),
                "fetchedAt": now,
            }
            for f in feats[:limit]
        ]

    if source == "openfda":
        q = urllib.parse.quote(query)
        url = f"https://api.fda.gov/drug/event.json?search={q}&limit={limit}"
        res = _fetch_json(url).get("results", [])
        return [
            {
                "source": "openfda",
                "safetyReportId": r.get("safetyreportid"),
                "receiveDate": r.get("receivedate"),
                "serious": r.get("serious"),
                "sourceUrl": url,
                "fetchedAt": now,
            }
            for r in res[:limit]
        ]

    if source == "clinicaltrials":
        q = urllib.parse.quote(query)
        url = f"https://clinicaltrials.gov/api/v2/studies?query.term={q}&pageSize={limit}"
        studies = _fetch_json(url).get("studies", [])
        out = []
        for s in studies[:limit]:
            ps = s.get("protocolSection", {})
            ident = ps.get("identificationModule", {})
            status_mod = ps.get("statusModule", {})
            nct = ident.get("nctId", "")
            out.append({
                "source": "clinicaltrials",
                "nctId": nct,
                "title": ident.get("briefTitle"),
                "status": status_mod.get("overallStatus"),
                "sourceUrl": f"https://clinicaltrials.gov/study/{nct}" if nct else url,
                "fetchedAt": now,
            })
        return out

    raise ValueError(f"Unsupported source: {source}")


async def run_apify() -> None:
    from apify import Actor  # type: ignore

    async with Actor:
        inp = await Actor.get_input() or {}
        source = inp.get("source", "fred")
        query = inp.get("query", "ICSA")
        limit = int(inp.get("limit", 10))
        items = fetch_source(source, query, limit)
        for item in items:
            await Actor.push_data(item)


def main() -> None:
    parser = argparse.ArgumentParser(description="Primary-Source Macro & Market Data Extractor")
    parser.add_argument("--source", default=None)
    parser.add_argument("--query", default=None)
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.source is not None:
        items = fetch_source(args.source, args.query or "", args.limit)
        print(json.dumps({"count": len(items), "items": items}, ensure_ascii=False, indent=2))
        return

    asyncio.run(run_apify())


if __name__ == "__main__":
    main()
