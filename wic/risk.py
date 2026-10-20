"""Ex-ante risk profile of a candidate book (evidence for the IC, not sizing)."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .factors import PriceSeries

WINDOW = 252


def _returns(series: dict[str, PriceSeries], tickers: list[str], asof: pd.Timestamp) -> pd.DataFrame:
    cols = {}
    for t in tickers:
        ps = series.get(t)
        if ps is None:
            continue
        i = ps.index_at(asof)
        if i < WINDOW:
            continue
        adj = ps.adj[i - WINDOW: i + 1]
        cols[t] = pd.Series(adj[1:] / adj[:-1] - 1, index=pd.DatetimeIndex(ps.dates[i - WINDOW + 1: i + 1]))
    return pd.DataFrame(cols).dropna()


def book_risk(series: dict[str, PriceSeries], book: pd.DataFrame, asof: pd.Timestamp, bench: str = "SPY") -> dict:
    tickers = list(book["yahoo_ticker"])
    rets = _returns(series, tickers + [bench], asof)
    if bench not in rets or len(rets) < 120:
        return {"status": "INSUFFICIENT_PRICE_HISTORY"}
    names = [t for t in tickers if t in rets]
    w = np.full(len(names), 1.0 / len(names))
    cov = rets[names].cov().to_numpy() * 252
    port = rets[names].to_numpy() @ w
    b = rets[bench].to_numpy()
    beta = float(np.cov(port, b, ddof=1)[0, 1] / np.var(b, ddof=1))
    corr = rets[names].corr().to_numpy()
    off = corr[~np.eye(len(names), dtype=bool)]
    per = []
    for t in names:
        r = rets[t].to_numpy()
        per.append({"ticker": t, "vol_252": float(r.std(ddof=1) * math.sqrt(252)),
                    "beta_252": float(np.cov(r, b, ddof=1)[0, 1] / np.var(b, ddof=1)),
                    "corr_to_spy": float(np.corrcoef(r, b)[0, 1])})
    mcr = (cov @ w) * w / float(w @ cov @ w)
    for row, c in zip(per, mcr):
        row["risk_contribution"] = float(c)
    sectors = book.groupby("sector").size() / len(book)
    return {"status": "OK", "asof": asof.date().isoformat(), "weighting": "EQUAL (illustrative; not a sizing rule)",
            "names": len(names), "ex_ante_vol_252": float(math.sqrt(w @ cov @ w)),
            "spy_vol_252": float(b.std(ddof=1) * math.sqrt(252)), "beta_vs_spy": beta,
            "avg_pairwise_correlation": float(off.mean()) if len(off) else None,
            "max_pairwise_correlation": float(off.max()) if len(off) else None,
            "diversification_ratio": float((w @ np.sqrt(np.diag(cov))) / math.sqrt(w @ cov @ w)),
            "sector_weights": {k: float(v) for k, v in sectors.items()}, "per_name": per}
