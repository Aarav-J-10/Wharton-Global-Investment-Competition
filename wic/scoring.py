"""Sector-relative normalization, composite score and ranking (spec section 12).

For each (sector, metric):
  1. valid finite values only (ECONOMICALLY_UNFAVORABLE sentinels excluded)
  2. need >= min_peers of them, else SCORING_UNAVAILABLE for the whole sector
  3. winsorize at the [lo, hi] quantiles (linear interpolation)
  4. ascending midranks; p = 100*(rank-0.5)/n; lower-is-better -> 100-p
  5. sentinels get the specified unfavorable score (0)
A composite exists only when all eleven outcomes are scored. No missing-weight
redistribution. Sort: composite desc, Quality desc, liquidity desc, id asc.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .config import DIRECTIONS, FACTOR_NAMES, FACTORS, FAMILIES, UNFAVORABLE, VALID, WEIGHTS


def _percentiles(values: np.ndarray, lo: float, hi: float, direction: int) -> np.ndarray:
    ql, qh = np.quantile(values, [lo, hi])
    w = np.clip(values, ql, qh)
    ranks = pd.Series(w).rank(method="average").to_numpy()
    p = 100.0 * (ranks - 0.5) / len(w)
    return p if direction > 0 else 100.0 - p


def score_universe(frame: pd.DataFrame, *, weights: dict | None = None, min_peers: int = 20,
                   winsor: tuple[float, float] = (0.05, 0.95), sentinel_score: float = 0.0,
                   sector_col: str = "sector") -> pd.DataFrame:
    """frame: one row per eligible security with `<f>` values and `<f>_status`.

    Returns a copy with `<f>_score`, `<f>_score_status`, `<f>_peers`, family
    scores, `composite`, `complete_factors` and `rank`.
    """
    weights = weights or WEIGHTS
    lo, hi = winsor
    out = frame.copy()
    for name in FACTOR_NAMES:
        out[f"{name}_score"] = np.nan
        out[f"{name}_score_status"] = "SCORING_UNAVAILABLE"
        out[f"{name}_peers"] = 0
    for sector, idx in out.groupby(sector_col, sort=True).groups.items():
        g = out.loc[idx]
        for name in FACTOR_NAMES:
            vals = pd.to_numeric(g[name], errors="coerce")
            st = g[f"{name}_status"]
            valid = st.eq(VALID) & np.isfinite(vals)
            n = int(valid.sum())
            out.loc[idx, f"{name}_peers"] = n
            if n < min_peers:
                out.loc[idx, f"{name}_score_status"] = "PEER_SET_INSUFFICIENT"
                continue
            vidx = g.index[valid.to_numpy()]
            out.loc[vidx, f"{name}_score"] = _percentiles(vals[valid].to_numpy(float), lo, hi, DIRECTIONS[name])
            out.loc[vidx, f"{name}_score_status"] = VALID
            uidx = g.index[st.eq(UNFAVORABLE).to_numpy()]
            out.loc[uidx, f"{name}_score"] = sentinel_score
            out.loc[uidx, f"{name}_score_status"] = UNFAVORABLE
            rest = g.index[~(valid | st.eq(UNFAVORABLE)).to_numpy()]
            out.loc[rest, f"{name}_score_status"] = st.loc[rest].where(st.loc[rest].ne(VALID), "NONFINITE_VALUE")
    return composite(out, weights)


def composite(out: pd.DataFrame, weights: dict) -> pd.DataFrame:
    scores = out[[f"{n}_score" for n in FACTOR_NAMES]].to_numpy(float)
    complete = np.isfinite(scores).all(axis=1)
    w = np.array([weights[n] for n in FACTOR_NAMES])
    out["complete_factors"] = np.isfinite(scores).sum(axis=1)
    comp = np.full(len(out), np.nan)
    for i in np.where(complete)[0]:
        comp[i] = math.fsum(scores[i] * w)
    out["composite"] = comp
    for fam in FAMILIES:
        cols = [j for j, f in enumerate(FACTORS) if f.family == fam]
        fw = w[cols].sum()
        vals = np.full(len(out), np.nan)
        ok = np.isfinite(scores[:, cols]).all(axis=1)
        for i in np.where(ok)[0]:
            vals[i] = math.fsum(scores[i, cols] * w[cols]) / fw
        out[fam.lower()] = vals
    return rank(out)


def rank(out: pd.DataFrame) -> pd.DataFrame:
    liq = out["liquidity_63"] if "liquidity_63" in out else pd.Series(np.nan, index=out.index)
    out = out.assign(_liq=liq.fillna(-np.inf), _c=out["composite"].fillna(-np.inf),
                     _q=out["quality"].fillna(-np.inf))
    out = out.sort_values(["_c", "_q", "_liq", "security_id"], ascending=[False, False, False, True],
                          kind="stable").drop(columns=["_liq", "_c", "_q"]).reset_index(drop=True)
    good = out["composite"].notna().to_numpy()
    r = np.full(len(out), np.nan)
    r[good] = np.arange(1, good.sum() + 1)
    out["rank"] = pd.array(r, dtype="Int64") if good.any() else pd.array([pd.NA] * len(out), dtype="Int64")
    return out


def diversified_view(ranked: pd.DataFrame, n: int = 10, max_per_sector: int = 3,
                     sector_col: str = "sector") -> pd.DataFrame:
    """Sector-capped research view; raw rank preserved, cap exceptions flagged."""
    ordered = ranked.loc[ranked["rank"].notna()].sort_values("rank")
    chosen, skipped, counts = [], [], {}
    for _, row in ordered.iterrows():
        if len(chosen) >= n:
            break
        s = row[sector_col]
        if counts.get(s, 0) >= max_per_sector:
            skipped.append(row)
            continue
        chosen.append((row, False))
        counts[s] = counts.get(s, 0) + 1
    for row in skipped:
        if len(chosen) >= min(n, len(ordered)):
            break
        chosen.append((row, True))
    rows = []
    for pos, (row, exc) in enumerate(sorted(chosen, key=lambda t: t[0]["rank"]), 1):
        d = row.to_dict()
        d.update(diversified_rank=pos, sector_cap_exception=exc)
        rows.append(d)
    return pd.DataFrame(rows)
