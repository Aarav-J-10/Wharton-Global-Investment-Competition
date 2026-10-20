"""Daily market data via yfinance (Yahoo Finance).

Stored fields per (date, ticker):
  close      split-adjusted close (yfinance convention)
  adj_close  split + dividend adjusted close = total-return index proxy
  volume     split-adjusted share volume
  dividends, splits  corporate actions on that date (split ratio, 0 if none)

The raw (unadjusted) close on any date is reconstructed as
close * product(split ratios with ex-date after that date), see raw_close().
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

from ..util import utc_now
from .http import SourceUnavailable

FIELDS = ["close", "adj_close", "volume", "dividends", "splits"]


def _download_batch(tickers: list[str], start: str, end: pd.Timestamp) -> pd.DataFrame:
    import yfinance as yf

    data = yf.download(tickers, start=start, end=(end + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                       auto_adjust=False, actions=True, progress=False, group_by="ticker",
                       threads=True, timeout=60)
    if data is None or data.empty:
        return pd.DataFrame(columns=["date", "ticker", *FIELDS])
    frames = []
    for t in tickers:
        if isinstance(data.columns, pd.MultiIndex):
            if t not in data.columns.get_level_values(0):
                continue
            d = data[t]
        else:
            d = data
        d = d.rename(columns={"Close": "close", "Adj Close": "adj_close", "Volume": "volume",
                              "Dividends": "dividends", "Stock Splits": "splits"})
        if "close" not in d or d["close"].notna().sum() == 0:
            continue
        for col in FIELDS:
            if col not in d:
                d[col] = 0.0
        d = d[FIELDS].dropna(subset=["close", "adj_close"])
        d.index = pd.to_datetime(d.index).tz_localize(None).normalize()
        d = d.reset_index().rename(columns={d.index.name or "index": "date", "Date": "date"})
        d["ticker"] = t
        frames.append(d[["date", "ticker", *FIELDS]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "ticker", *FIELDS])


def download_prices(tickers: list[str], start: str, end: pd.Timestamp, batch: int = 50,
                    pause: float = 1.0, retries: int = 3) -> tuple[pd.DataFrame, dict]:
    tickers = sorted(set(tickers))
    frames, failed = [], []
    for i in range(0, len(tickers), batch):
        chunk = tickers[i:i + batch]
        got = pd.DataFrame()
        for attempt in range(retries):
            try:
                got = _download_batch(chunk, start, end)
                break
            except Exception as exc:  # yfinance raises assorted rate-limit errors
                time.sleep(5 * (attempt + 1))
                last = exc
        else:
            raise SourceUnavailable(f"yfinance failed for batch starting {chunk[0]}: {last}")
        missing = sorted(set(chunk) - set(got.ticker.unique()))
        # Retry stragglers one by one (Yahoo occasionally drops names in batch calls).
        for t in missing:
            try:
                one = _download_batch([t], start, end)
            except Exception:
                one = pd.DataFrame()
            if one.empty:
                failed.append(t)
            else:
                got = pd.concat([got, one], ignore_index=True)
        frames.append(got)
        time.sleep(pause)
    prices = pd.concat(frames, ignore_index=True)
    prices = prices.loc[prices.date <= end]
    prices = prices.sort_values(["ticker", "date"]).drop_duplicates(["ticker", "date"], keep="last")
    prices["volume"] = prices["volume"].fillna(0.0)
    prices["dividends"] = prices["dividends"].fillna(0.0)
    prices["splits"] = prices["splits"].fillna(0.0)
    meta = {"provider": "Yahoo Finance via yfinance", "retrieved_utc": utc_now(), "start": start,
            "end": end.date().isoformat(), "requested": len(tickers),
            "returned": int(prices.ticker.nunique()), "no_data": failed,
            "convention": "close=split-adjusted; adj_close=split+dividend adjusted (total-return proxy)"}
    return prices.reset_index(drop=True), meta


def validate_prices(prices: pd.DataFrame) -> list[str]:
    problems = []
    if prices.duplicated(["ticker", "date"]).any():
        problems.append("duplicate (ticker, date) rows")
    for col in ("close", "adj_close"):
        bad = prices[col].le(0) | ~np.isfinite(prices[col])
        if bad.any():
            problems.append(f"{int(bad.sum())} nonpositive/nonfinite {col} values")
    if prices.volume.lt(0).any():
        problems.append("negative volume")
    return problems


def split_factor_after(splits: pd.DataFrame, ticker: str, date: pd.Timestamp) -> float:
    """Product of split ratios with ex-date strictly after `date` (to today's basis)."""
    s = splits.loc[(splits.ticker == ticker) & (splits.date > date) & (splits.splits > 0), "splits"]
    return float(np.prod(s.to_numpy())) if len(s) else 1.0


def split_events(prices: pd.DataFrame) -> pd.DataFrame:
    return prices.loc[prices.splits.gt(0) & prices.splits.ne(1.0), ["ticker", "date", "splits"]].reset_index(drop=True)
