"""SEC EDGAR XBRL companyfacts acquisition -> compact point-in-time fact table.

Every fact keeps its accession number, form, fiscal labels and SEC `filed`
date. The `filed` date (not the period end) controls when a fact may be used.
Raw companyfacts payload hashes are recorded per issuer in the snapshot.
"""
from __future__ import annotations

import gzip
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from ..accounting.concepts import ALL_CONCEPTS, ALLOWED_FORMS
from ..util import sha256_bytes, utc_now
from .http import PoliteSession, SourceUnavailable, sec_user_agent

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
UNITS = {"USD", "USD/shares", "shares"}
COLUMNS = ["cik", "concept", "unit", "start", "end", "val", "accn", "fy", "fp", "form", "filed"]


def sec_session() -> PoliteSession:
    # SEC fair-access limit is 10 requests/second; stay well below it.
    return PoliteSession(sec_user_agent(), min_interval=0.125)


def fetch_ticker_map(http: PoliteSession) -> tuple[pd.DataFrame, dict]:
    r = http.get(TICKERS_URL)
    if r.status_code != 200:
        raise SourceUnavailable(f"SEC company_tickers HTTP {r.status_code}")
    rows = pd.DataFrame(list(r.json().values()))
    rows = rows.rename(columns={"cik_str": "cik", "title": "sec_name"})
    rows["ticker"] = rows["ticker"].str.upper()
    return rows, {"url": TICKERS_URL, "sha256": sha256_bytes(r.content), "retrieved_utc": utc_now(),
                  "rows": int(len(rows))}


def extract_facts(payload: dict, cik: int) -> pd.DataFrame:
    wanted = set(ALL_CONCEPTS)
    out = []
    for taxonomy, concepts in payload.get("facts", {}).items():
        for concept, body in concepts.items():
            key = concept if taxonomy == "us-gaap" else f"{taxonomy}:{concept}"
            if key not in wanted:
                continue
            for unit, facts in body.get("units", {}).items():
                if unit not in UNITS:
                    continue
                for f in facts:
                    if f.get("form") not in ALLOWED_FORMS:
                        continue
                    out.append((cik, key, unit, f.get("start"), f["end"], f["val"], f["accn"],
                                f.get("fy"), f.get("fp"), f["form"], f["filed"]))
    df = pd.DataFrame(out, columns=COLUMNS)
    if df.empty:
        return df
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    df["val"] = pd.to_numeric(df["val"], errors="coerce")
    df = df.dropna(subset=["val"])
    # Identical fact repeated across filings: keep the first public version and
    # every later version whose value changed (restatements stay point-in-time).
    df = df.sort_values(["concept", "unit", "start", "end", "filed", "accn"], na_position="first")
    key = ["concept", "unit", "start", "end"]
    changed = df.groupby(key, dropna=False)["val"].transform(lambda s: s.ne(s.shift()))
    return df.loc[changed].reset_index(drop=True)


def fetch_company_facts(http: PoliteSession, cik: int, cache_dir: Path | None) -> tuple[pd.DataFrame, dict]:
    url = FACTS_URL.format(cik=int(cik))
    cache = cache_dir / f"CIK{int(cik):010d}.json.gz" if cache_dir else None
    if cache and cache.exists():
        raw = gzip.decompress(cache.read_bytes())
        status = "CACHE"
    else:
        r = http.get(url)
        if r.status_code == 404:
            return pd.DataFrame(columns=COLUMNS), {"cik": int(cik), "url": url, "status": "NOT_FOUND"}
        if r.status_code != 200:
            raise SourceUnavailable(f"SEC companyfacts {cik} HTTP {r.status_code}")
        raw = r.content
        status = "FETCHED"
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(gzip.compress(raw, mtime=0))
    payload = json.loads(raw)
    facts = extract_facts(payload, int(cik))
    return facts, {"cik": int(cik), "url": url, "status": status, "raw_sha256": sha256_bytes(raw),
                   "raw_bytes": len(raw), "entity_name": payload.get("entityName"), "facts_kept": int(len(facts)),
                   "retrieved_utc": utc_now()}


def fetch_all_facts(ciks: list[int], cache_dir: Path | None = None, workers: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    http = sec_session()
    ciks = sorted({int(c) for c in ciks})
    with ThreadPoolExecutor(max_workers=workers) as ex:
        results = list(ex.map(lambda c: fetch_company_facts(http, c, cache_dir), ciks))
    facts = pd.concat([r[0] for r in results if not r[0].empty], ignore_index=True)
    meta = pd.DataFrame([r[1] for r in results])
    return facts.sort_values(["cik", "concept", "end", "filed"]).reset_index(drop=True), meta
