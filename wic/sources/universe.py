"""S&P 500 universe acquisition.

Primary source: the Wikipedia "List of S&P 500 companies" page, pinned to the
latest revision at or before the cutoff (revision id + timestamp + raw payload
preserved). This is a reproducible public research source, NOT licensed S&P
Dow Jones Indices data. Historical revisions also provide point-in-time GICS
sector / CIK labels for former constituents in the backtest.

Point-in-time membership for the backtest comes from the community-maintained
fja05680/sp500 dataset (1996-present, derived from Clenow + Wikipedia changes).
"""
from __future__ import annotations

import io
import json
import re
from pathlib import Path

import pandas as pd

from ..util import sha256_bytes, utc_now
from .http import PoliteSession, SourceUnavailable

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_TITLE = "List of S&P 500 companies"
WIKI_UA = "WIC-S003-research-engine/1.2 (educational research; github.com/Aarav-J-10)"
FJA_BASE = "https://raw.githubusercontent.com/fja05680/sp500/master/"
FJA_HISTORY = "S&P 500 Historical Components & Changes (Updated).csv"
FJA_CURRENT = "sp500.csv"


def yahoo_symbol(ticker: str) -> str:
    return ticker.strip().upper().replace(".", "-")


def _norm_col(c: str) -> str:
    c = re.sub(r"\[.*?\]", "", str(c)).strip().lower()
    if c in ("symbol", "ticker symbol", "ticker"):
        return "ticker"
    if c in ("security", "company"):
        return "security"
    if c == "gics sector":
        return "gics_sector"
    if c in ("gics sub-industry", "gics sub industry"):
        return "gics_sub_industry"
    if c.startswith("cik"):
        return "cik"
    if c.startswith("date added") or c.startswith("date first added"):
        return "date_added"
    return c


def parse_constituents_html(html: str) -> pd.DataFrame:
    tables = pd.read_html(io.StringIO(html))
    for t in tables:
        t = t.rename(columns=_norm_col)
        if {"ticker", "gics_sector"}.issubset(t.columns) and len(t) > 300:
            break
    else:
        raise ValueError("No S&P 500 constituents table found in revision HTML")
    out = pd.DataFrame({
        "ticker": t["ticker"].astype(str).str.strip().str.upper(),
        "security": t.get("security", pd.Series([None] * len(t))).astype(str).str.strip(),
        "gics_sector": t["gics_sector"].astype(str).str.strip(),
        "gics_sub_industry": t.get("gics_sub_industry", pd.Series([None] * len(t))),
        "cik": pd.to_numeric(t["cik"], errors="coerce").astype("Int64") if "cik" in t else pd.Series(
            [pd.NA] * len(t), dtype="Int64"),
        "date_added": t.get("date_added", pd.Series([None] * len(t))),
    })
    # GICS renamed "Telecommunication Services" -> "Communication Services" (2018)
    # and "Information Technology" has been stable; keep labels as published.
    out["yahoo_ticker"] = out["ticker"].map(yahoo_symbol)
    return out.drop_duplicates("ticker").reset_index(drop=True)


class WikipediaUniverse:
    def __init__(self, session: PoliteSession | None = None, min_interval: float = 1.0,
                 cache_dir: Path | None = None):
        self.http = session or PoliteSession(WIKI_UA, min_interval=min_interval)
        self.cache_dir = cache_dir

    def revision_at(self, cutoff_utc: str) -> dict:
        cache = self.cache_dir / f"revision_at_{cutoff_utc.replace(':', '')}.json" if self.cache_dir else None
        if cache and cache.exists():
            return json.loads(cache.read_text())
        rev = self._revision_at(cutoff_utc)
        if cache:
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps(rev))
        return rev

    def _revision_at(self, cutoff_utc: str) -> dict:
        params = {"action": "query", "prop": "revisions", "titles": WIKI_TITLE, "rvlimit": 1,
                  "rvstart": cutoff_utc, "rvdir": "older", "rvprop": "ids|timestamp|sha1",
                  "format": "json", "formatversion": 2}
        r = self.http.get(WIKI_API, params=params)
        if r.status_code != 200:
            raise SourceUnavailable(f"Wikipedia revision lookup HTTP {r.status_code}")
        page = r.json()["query"]["pages"][0]
        rev = page["revisions"][0]
        return {"revid": rev["revid"], "timestamp": rev["timestamp"], "sha1": rev.get("sha1")}

    def fetch_revision(self, revid: int) -> tuple[pd.DataFrame, bytes]:
        cache = self.cache_dir / f"rev{revid}.json" if self.cache_dir else None
        if cache and cache.exists():
            raw = cache.read_bytes()
        else:
            params = {"action": "parse", "oldid": revid, "prop": "text", "format": "json", "formatversion": 2}
            r = self.http.get(WIKI_API, params=params)
            if r.status_code != 200:
                raise SourceUnavailable(f"Wikipedia parse HTTP {r.status_code}")
            raw = r.content
            if cache:
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_bytes(raw)
        html = json.loads(raw)["parse"]["text"]
        return parse_constituents_html(html), raw

    def snapshot(self, cutoff: pd.Timestamp, out_dir: Path) -> tuple[pd.DataFrame, dict]:
        cutoff_utc = (cutoff + pd.Timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z")
        rev = self.revision_at(cutoff_utc)
        df, raw = self.fetch_revision(rev["revid"])
        raw_path = out_dir / "raw" / f"wikipedia_sp500_rev{rev['revid']}.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        meta = {"source": "Wikipedia: List of S&P 500 companies", "source_class":
                "AUTO_REPRODUCIBLE_PUBLIC_RESEARCH_SOURCE (not licensed S&P DJI data)",
                "revision_id": rev["revid"], "revision_timestamp": rev["timestamp"],
                "revision_sha1": rev["sha1"], "raw_sha256": sha256_bytes(raw),
                "raw_file": str(raw_path.relative_to(out_dir)), "retrieved_utc": utc_now(),
                "url": f"https://en.wikipedia.org/w/index.php?oldid={rev['revid']}",
                "rows": int(len(df))}
        return df, meta

    def sector_history(self, start: str, end: pd.Timestamp, out_dir: Path) -> tuple[pd.DataFrame, list]:
        """Semiannual revisions -> point-in-time ticker -> (GICS sector, CIK) labels."""
        frames, metas = [], []
        for d in pd.date_range(start, end, freq="6MS"):
            try:
                rev = self.revision_at(d.strftime("%Y-%m-%dT00:00:00Z"))
                df, raw = self.fetch_revision(rev["revid"])
            except (SourceUnavailable, ValueError, KeyError) as exc:
                metas.append({"as_of": d.date().isoformat(), "error": str(exc)[:200]})
                continue
            df["label_date"] = d.normalize()
            frames.append(df[["label_date", "ticker", "yahoo_ticker", "security", "gics_sector", "cik"]])
            metas.append({"as_of": d.date().isoformat(), "revision_id": rev["revid"],
                          "revision_timestamp": rev["timestamp"], "raw_sha256": sha256_bytes(raw),
                          "rows": int(len(df))})
        if not frames:
            raise SourceUnavailable("No historical Wikipedia revisions could be parsed")
        return pd.concat(frames, ignore_index=True), metas


def fetch_membership_history(session: PoliteSession | None = None) -> tuple[pd.DataFrame, dict]:
    """fja05680/sp500 point-in-time membership (date, comma-separated tickers)."""
    http = session or PoliteSession(WIKI_UA)
    url = FJA_BASE + FJA_HISTORY.replace("&", "%26").replace(" ", "%20")
    r = http.get(url)
    if r.status_code != 200:
        raise SourceUnavailable(f"Membership history HTTP {r.status_code}")
    df = pd.read_csv(io.BytesIO(r.content))
    df["date"] = pd.to_datetime(df["date"])
    meta = {"source": "github.com/fja05680/sp500 " + FJA_HISTORY, "url": url,
            "sha256": sha256_bytes(r.content), "retrieved_utc": utc_now(),
            "first_date": df.date.min().date().isoformat(), "last_date": df.date.max().date().isoformat(),
            "rows": int(len(df)),
            "limitations": "Community dataset; tickers are as-of each date; delisted names usually lack Yahoo prices"}
    return df, meta


def fetch_fja_current(session: PoliteSession | None = None) -> tuple[pd.DataFrame, dict]:
    """Fallback current list (Wikipedia-derived CSV hosted on GitHub)."""
    http = session or PoliteSession(WIKI_UA)
    r = http.get(FJA_BASE + FJA_CURRENT)
    if r.status_code != 200:
        raise SourceUnavailable(f"Fallback constituents HTTP {r.status_code}")
    t = pd.read_csv(io.BytesIO(r.content)).rename(columns=_norm_col)
    out = pd.DataFrame({"ticker": t["ticker"].str.upper(), "security": t["security"],
                        "gics_sector": t["gics_sector"], "gics_sub_industry": t.get("gics_sub_industry"),
                        "cik": pd.to_numeric(t["cik"], errors="coerce").astype("Int64"),
                        "date_added": t.get("date_added")})
    out["yahoo_ticker"] = out["ticker"].map(yahoo_symbol)
    meta = {"source": "github.com/fja05680/sp500 sp500.csv (Wikipedia-derived)", "url": FJA_BASE + FJA_CURRENT,
            "raw_sha256": sha256_bytes(r.content), "retrieved_utc": utc_now(), "rows": int(len(out)),
            "source_class": "FALLBACK_PUBLIC_RESEARCH_SOURCE (not licensed S&P DJI data; as-of date not pinned)"}
    return out, meta


def members_on(history: pd.DataFrame, date: pd.Timestamp) -> list[str]:
    rows = history.loc[history["date"] <= date]
    if rows.empty:
        return []
    return sorted(set(rows.iloc[-1]["tickers"].split(",")))
