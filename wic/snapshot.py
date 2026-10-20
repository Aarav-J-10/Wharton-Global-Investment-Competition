"""Immutable, hash-manifested input snapshots.

`acquire()` is the ONLY network step. Everything downstream (screen, backtest,
validator) reads a snapshot offline, so any third party can re-run the model
from the committed snapshot and must obtain byte-identical outputs.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from .util import sha256_file, utc_now, write_csv, write_json

log = logging.getLogger("wic.snapshot")

FILES = ("universe.csv", "membership_history.csv", "sector_history.csv", "prices*.parquet",
         "sec_facts*.parquet", "sec_sources.csv", "sec_ticker_map.csv")
MAX_FILE_BYTES = 90_000_000  # stay under GitHub's 100 MB per-file limit
BENCHMARKS = ("SPY", "RSP", "^IRX")


def last_completed_session(now_utc: pd.Timestamp | None = None) -> pd.Timestamp:
    """Most recent weekday whose 16:00 New York close has passed (+1h buffer)."""
    now = (now_utc or pd.Timestamp.now(tz="UTC")).tz_convert("America/New_York")
    d = now.normalize()
    if now.hour < 17:
        d -= pd.Timedelta(days=1)
    while d.weekday() >= 5:
        d -= pd.Timedelta(days=1)
    return d.tz_localize(None)


def _parquet(df: pd.DataFrame, path: Path) -> None:
    """Write one parquet file, or numbered parts if it would exceed MAX_FILE_BYTES."""
    df.to_parquet(path, index=False, compression="zstd")
    size = path.stat().st_size
    if size <= MAX_FILE_BYTES:
        return
    path.unlink()
    parts = int(size // MAX_FILE_BYTES) + 1
    step = -(-len(df) // parts)
    for i in range(parts):
        df.iloc[i * step:(i + 1) * step].to_parquet(path.with_name(f"{path.stem}-{i:03d}.parquet"), index=False,
                                                    compression="zstd")


def _read_parquet(snap: Path, stem: str) -> pd.DataFrame:
    files = sorted(snap.glob(f"{stem}.parquet")) or sorted(snap.glob(f"{stem}-[0-9][0-9][0-9].parquet"))
    if not files:
        raise FileNotFoundError(f"{stem}.parquet missing from snapshot")
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def acquire(cutoff: pd.Timestamp, root: Path, *, history_start: str = "2009-01-01",
            sector_history_start: str = "2011-01-01", cache_dir: Path | None = None) -> Path:
    from .sources import prices as P
    from .sources import sec as S
    from .sources import universe as U
    from .sources.http import SourceUnavailable

    snap = root / f"sp500_{cutoff.date().isoformat()}"
    snap.mkdir(parents=True, exist_ok=True)
    sources: dict = {"cutoff": cutoff.date().isoformat(), "acquired_utc": utc_now()}

    # 1. Current universe (revision pinned at cutoff), fallback to GitHub mirror.
    wiki = U.WikipediaUniverse()
    try:
        uni, meta = wiki.snapshot(cutoff, snap)
    except (SourceUnavailable, ValueError, KeyError) as exc:
        log.warning("Wikipedia unavailable (%s); using fallback list", exc)
        uni, meta = U.fetch_fja_current()
        meta["primary_failure"] = str(exc)[:300]
    sources["universe"] = meta
    uni = uni.rename(columns={"gics_sector": "sector"})

    # 2. Point-in-time membership + sector/CIK label history for the backtest.
    hist, hmeta = U.fetch_membership_history()
    sources["membership_history"] = hmeta
    try:
        sect, smeta = wiki.sector_history(sector_history_start, cutoff, snap)
        sources["sector_history"] = {"source": "Wikipedia semiannual revisions", "revisions": smeta}
    except SourceUnavailable as exc:
        sect = uni.assign(label_date=cutoff)[["label_date", "ticker", "yahoo_ticker", "security", "sector", "cik"]]
        sources["sector_history"] = {"source": "current universe only (historical revisions unavailable)",
                                     "error": str(exc)[:300]}
    sect = sect.rename(columns={"gics_sector": "sector"})

    # 3. SEC ticker map fills missing CIKs.
    http = S.sec_session()
    tmap, tmeta = S.fetch_ticker_map(http)
    sources["sec_ticker_map"] = tmeta
    cik_by_ticker = dict(zip(tmap.ticker.str.replace("-", "."), tmap.cik))
    for df in (uni, sect):
        miss = df["cik"].isna()
        df.loc[miss, "cik"] = df.loc[miss, "ticker"].map(cik_by_ticker)
        df["cik"] = pd.to_numeric(df["cik"], errors="coerce").astype("Int64")

    # 4. Prices: current members + every member since backtest window + benchmarks.
    since = hist.loc[hist["date"] >= pd.Timestamp(history_start)]
    hist_tickers = set().union(*[set(t.split(",")) for t in since["tickers"]])
    tickers = set(uni["yahoo_ticker"]) | {U.yahoo_symbol(t) for t in hist_tickers} | set(BENCHMARKS)
    prices, pmeta = P.download_prices(sorted(tickers), history_start, cutoff)
    problems = P.validate_prices(prices)
    if problems:
        raise SourceUnavailable("Price validation failed: " + "; ".join(problems))
    pmeta["validation"] = "PASSED"
    sources["prices"] = pmeta
    cur_missing = sorted(set(uni["yahoo_ticker"]) - set(prices["ticker"]))
    sources["prices"]["current_members_without_data"] = cur_missing

    # 5. SEC companyfacts for every CIK we might score.
    ciks = sorted(set(uni["cik"].dropna().astype(int)) | set(sect["cik"].dropna().astype(int)))
    facts, fmeta = S.fetch_all_facts(ciks, cache_dir=cache_dir)
    sources["sec_companyfacts"] = {"issuers_requested": len(ciks),
                                   "issuers_with_facts": int(facts["cik"].nunique()),
                                   "fact_rows": int(len(facts)),
                                   "endpoint": "https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json"}

    write_csv(snap / "universe.csv", uni.sort_values("ticker"))
    write_csv(snap / "membership_history.csv", hist.assign(date=hist["date"].dt.date))
    write_csv(snap / "sector_history.csv", sect.sort_values(["label_date", "ticker"]).assign(
        label_date=pd.to_datetime(sect["label_date"]).dt.date))
    _parquet(prices, snap / "prices.parquet")
    _parquet(facts, snap / "sec_facts.parquet")
    write_csv(snap / "sec_sources.csv", fmeta.sort_values("cik"))
    write_csv(snap / "sec_ticker_map.csv", tmap.sort_values("ticker"))
    write_json(snap / "SOURCES.json", sources)
    seal(snap)
    return snap


def seal(snap: Path) -> dict:
    files = sorted(p for p in snap.rglob("*") if p.is_file() and p.name != "MANIFEST.json")
    manifest = {"snapshot_id": snap.name, "sealed_utc": utc_now(),
                "files": {str(p.relative_to(snap)): {"sha256": sha256_file(p), "bytes": p.stat().st_size}
                          for p in files}}
    write_json(snap / "MANIFEST.json", manifest)
    return manifest


def verify(snap: Path) -> list[str]:
    """Return a list of integrity problems (empty == snapshot intact)."""
    man = json.loads((snap / "MANIFEST.json").read_text())
    problems = []
    for rel, info in man["files"].items():
        p = snap / rel
        if not p.exists():
            problems.append(f"missing {rel}")
        elif sha256_file(p) != info["sha256"]:
            problems.append(f"hash mismatch {rel}")
    import fnmatch
    for f in FILES:
        if not fnmatch.filter(man["files"], f):
            problems.append(f"manifest lacks required file {f}")
    return problems


class Snapshot:
    def __init__(self, path: str | Path, verify_hashes: bool = True):
        self.path = Path(path)
        if verify_hashes:
            problems = verify(self.path)
            if problems:
                raise RuntimeError("Snapshot integrity failure: " + "; ".join(problems[:10]))
        self.manifest = json.loads((self.path / "MANIFEST.json").read_text())
        self.sources = json.loads((self.path / "SOURCES.json").read_text())
        self.cutoff = pd.Timestamp(self.sources["cutoff"])

    def universe(self) -> pd.DataFrame:
        u = pd.read_csv(self.path / "universe.csv", dtype={"ticker": str})
        u["cik"] = pd.to_numeric(u["cik"], errors="coerce").astype("Int64")
        return u

    def membership_history(self) -> pd.DataFrame:
        h = pd.read_csv(self.path / "membership_history.csv")
        h["date"] = pd.to_datetime(h["date"])
        return h

    def sector_history(self) -> pd.DataFrame:
        s = pd.read_csv(self.path / "sector_history.csv", dtype={"ticker": str})
        s["label_date"] = pd.to_datetime(s["label_date"])
        s["cik"] = pd.to_numeric(s["cik"], errors="coerce").astype("Int64")
        return s

    def prices(self) -> pd.DataFrame:
        p = _read_parquet(self.path, "prices")
        p["date"] = pd.to_datetime(p["date"])
        return p

    def facts(self) -> pd.DataFrame:
        f = _read_parquet(self.path, "sec_facts")
        for c in ("start", "end", "filed"):
            f[c] = pd.to_datetime(f[c])
        return f
