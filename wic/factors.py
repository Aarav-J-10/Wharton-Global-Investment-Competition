"""Eleven raw factor outcomes (spec section 11) from fundamentals + prices.

Outcome states:
  VALID                      finite value that enters the sector percentile
  ECONOMICALLY_UNFAVORABLE   explicit sentinel (scored 0) where the spec allows
  anything else              missing with a reason; blocks the composite
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from .config import FACTOR_NAMES, UNFAVORABLE, VALID

SESSIONS_12M, SESSIONS_6M, SKIP_1M = 252, 126, 21


class PriceSeries:
    """Per-ticker arrays for fast as-of lookups."""

    def __init__(self, df: pd.DataFrame):
        df = df.sort_values("date")
        self.dates = df["date"].to_numpy(dtype="datetime64[ns]")
        self.close = df["close"].to_numpy(float)
        self.adj = df["adj_close"].to_numpy(float)
        self.volume = df["volume"].to_numpy(float)
        sp = df.loc[df["splits"].gt(0) & df["splits"].ne(1.0), ["date", "splits"]]
        self.splits = sp.reset_index(drop=True)

    def index_at(self, asof: pd.Timestamp) -> int:
        return int(np.searchsorted(self.dates, np.datetime64(asof), side="right")) - 1

    def split_factor_after(self, date) -> float:
        s = self.splits.loc[self.splits["date"] > pd.Timestamp(date), "splits"]
        return float(np.prod(s.to_numpy())) if len(s) else 1.0


def market_block(ps: PriceSeries | None, asof: pd.Timestamp, ref_session: pd.Timestamp,
                 liquidity_window: int = 63) -> dict:
    out = {"price_status": "NO_PRICE_DATA"}
    if ps is None or len(ps.dates) == 0:
        return out
    i = ps.index_at(asof)
    if i < 0:
        return out
    last = pd.Timestamp(ps.dates[i])
    out["last_price_date"] = last
    if last < ref_session:
        out["price_status"] = "STALE_PRICE"
        return out
    out["close"] = ps.close[i]
    out["raw_close"] = ps.close[i] * ps.split_factor_after(last)
    lo = max(0, i - liquidity_window + 1)
    out["liquidity_63"] = float(np.median(ps.close[lo:i + 1] * ps.volume[lo:i + 1]))
    first = pd.Timestamp(ps.dates[0])
    out["history_months"] = (last.year - first.year) * 12 + (last.month - first.month)
    if i < SESSIONS_12M:
        out["price_status"] = "INSUFFICIENT_PRICE_HISTORY"
        return out
    adj = ps.adj[: i + 1]
    window = adj[i - SESSIONS_12M: i + 1]          # 253 prices -> 252 returns
    if not np.all(np.isfinite(window)) or np.any(window <= 0):
        out["price_status"] = "INVALID_PRICE_DATA"
        return out
    rets = window[1:] / window[:-1] - 1.0
    out["momentum_12_1"] = adj[i - SKIP_1M] / adj[i - SESSIONS_12M] - 1.0
    out["momentum_6_1"] = adj[i - SKIP_1M] / adj[i - SESSIONS_6M] - 1.0
    out["volatility_252"] = float(np.std(rets, ddof=1) * math.sqrt(252))
    out["max_drawdown_252"] = float(np.max(1.0 - window / np.maximum.accumulate(window)))
    out["price_status"] = "OK"
    return out


def _r(value, status=VALID, detail=""):
    return {"value": value if status == VALID else None, "status": status, "detail": detail}


def compute_factors(fund: dict, mkt: dict, asof: pd.Timestamp, cfg: dict) -> tuple[dict, dict]:
    """Return ({factor: {value,status,detail}}, intermediates)."""
    f: dict[str, dict] = {}
    inter: dict = {}
    fcfg = cfg["fundamentals"]

    # ---- market factors
    ps = mkt.get("price_status")
    for name in ("momentum_12_1", "momentum_6_1", "volatility_252", "max_drawdown_252"):
        f[name] = _r(mkt[name]) if ps == "OK" else _r(None, ps or "NO_PRICE_DATA")

    # ---- fundamentals availability
    fund_status = fund.get("status")
    if fund_status != "OK":
        for name in FACTOR_NAMES[:7]:
            f[name] = _r(None, fund_status or "NO_FUNDAMENTALS")
        return f, inter
    q = fund["q"]
    E = fund["period_end"]
    stale_q = (asof - E).days > fcfg["max_latest_quarter_age_days"]
    inter["period_end"] = E
    inter["max_filed_used"] = fund.get("max_filed_used")

    def get(name):
        x = q[name]
        return x.value if x.ok else None

    def why(*names):
        for n in names:
            if not q[n].ok:
                return f"{n.upper()}:{q[n].status}"
        return ""

    rev, ebit, da, cfo, capex = (get(k) for k in ("revenue", "ebit", "da", "cfo", "capex"))
    debt, cash, eq, nci, pref = (get(k) for k in ("debt", "cash", "equity", "nci", "preferred"))
    fcf = cfo - capex if cfo is not None and capex is not None else None
    ebitda = ebit + da if ebit is not None and da is not None else None
    inter.update(revenue_ttm=rev, ebit_ttm=ebit, da_ttm=da, ebitda_ttm=ebitda, cfo_ttm=cfo, capex_ttm=capex,
                 fcf_ttm=fcf, debt=debt, cash=cash, equity=eq, nci=nci, preferred=pref,
                 interest_ttm=get("interest"), tax_rate=get("tax_rate"))
    flags = sorted({v.lineage.get("flag") for v in q.values() if isinstance(v.lineage, dict) and v.lineage.get("flag")})
    inter["accounting_flags"] = ";".join(flags)

    def stale_or(status_fn):
        return _r(None, "STALE_INPUT", f"latest period {E.date()} older than "
                  f"{fcfg['max_latest_quarter_age_days']}d") if stale_q else status_fn()

    # ROIC
    def roic():
        # Operating losses carry no tax shield: NOPAT = EBIT, so no tax rate is needed.
        need = ("ebit", "debt", "cash", "equity", "debt_prior", "cash_prior", "equity_prior")
        if ebit is None or ebit > 0:
            need = ("tax_rate",) + need
        w = why(*need)
        if w:
            return _r(None, w.split(":")[1], w)
        ic = debt + eq + pref + nci - cash
        icp = (q["debt_prior"].value + q["equity_prior"].value + q["preferred_prior"].value
               + q["nci_prior"].value - q["cash_prior"].value)
        avg = (ic + icp) / 2.0
        inter.update(invested_capital=ic, invested_capital_prior=icp, avg_invested_capital=avg)
        if avg <= 0:
            return _r(None, "OUTSIDE_METRIC_MODEL", "average invested capital <= 0")
        tax = q["tax_rate"].value if ebit > 0 else 0.0
        return _r(ebit * (1.0 - tax) / avg)
    f["roic"] = stale_or(roic)

    def fcf_margin():
        w = why("cfo", "capex", "revenue")
        if w:
            return _r(None, w.split(":")[1], w)
        if rev <= 0:
            return _r(None, "OUTSIDE_METRIC_MODEL", "revenue <= 0")
        return _r(fcf / rev)
    f["fcf_margin"] = stale_or(fcf_margin)

    def nd_ebitda():
        w = why("debt", "cash", "ebit", "da")
        if w:
            return _r(None, w.split(":")[1], w)
        if ebitda <= 0:
            return _r(None, UNFAVORABLE, "EBITDA <= 0")
        return _r((debt - cash) / ebitda)
    f["net_debt_ebitda"] = stale_or(nd_ebitda)

    # Market-value metrics
    mcap = None
    if q["shares"].ok and ps in ("OK", "INSUFFICIENT_PRICE_HISTORY") and mkt.get("close"):
        mcap = q["shares"].value * mkt["close"]
    inter["market_cap"] = mcap

    def fcf_yield():
        w = why("cfo", "capex", "shares")
        if w:
            return _r(None, w.split(":")[1], w)
        if mcap is None:
            return _r(None, ps or "NO_PRICE_DATA", "market cap unavailable")
        if mcap <= 0:
            return _r(None, "INVALID_MARKET_CAP")
        return _r(fcf / mcap)
    f["fcf_yield"] = stale_or(fcf_yield)

    def ev_ebit():
        w = why("ebit", "debt", "cash", "shares")
        if w:
            return _r(None, w.split(":")[1], w)
        if mcap is None:
            return _r(None, ps or "NO_PRICE_DATA", "market cap unavailable")
        ev = mcap + debt + pref + nci - cash
        inter["enterprise_value"] = ev
        if ev <= 0:
            return _r(None, "OUTSIDE_METRIC_MODEL", "EV <= 0 requires review")
        if ebit <= 0:
            return _r(None, UNFAVORABLE, "EBIT <= 0")
        return _r(ev / ebit)
    f["ev_ebit"] = stale_or(ev_ebit)

    # Growth
    def cagr(hist, status, name, sentinel_on_nonpositive):
        if status != VALID or len(hist) < 4:
            return _r(None, status if status != VALID else "INSUFFICIENT_ANNUAL_HISTORY")
        fy0_end = hist[0][0]
        if (asof - fy0_end).days > fcfg["max_latest_fy_age_days"]:
            return _r(None, "STALE_INPUT", f"latest FY {fy0_end.date()} too old")
        v0, v3 = hist[0][1], hist[3][1]
        inter[f"{name}_fy0"], inter[f"{name}_fy3"] = v0, v3
        inter[f"{name}_fy0_end"] = fy0_end
        if v0 <= 0 or v3 <= 0:
            if sentinel_on_nonpositive:
                return _r(None, UNFAVORABLE, "nonpositive endpoint")
            return _r(None, "OUTSIDE_METRIC_MODEL", "nonpositive revenue")
        return _r((v0 / v3) ** (1.0 / 3.0) - 1.0)
    f["revenue_cagr_3y"] = cagr(fund["rev_hist"], fund["rev_hist_status"], "revenue", False)
    f["eps_cagr_3y"] = cagr(fund["eps_hist"], fund["eps_hist_status"], "eps", True)

    # Resilience inputs
    inter["fcf_annual_last3"] = fund.get("fcf_annual_last3")
    for name in FACTOR_NAMES:
        v = f[name]
        if v["status"] == VALID and (v["value"] is None or not math.isfinite(v["value"])):
            f[name] = _r(None, "NONFINITE_VALUE")
    return {k: f[k] for k in FACTOR_NAMES}, inter
