"""Build the point-in-time cross-section for one as-of date.

Shared by the live screen and the backtest so the historical test exercises
exactly the production code path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .accounting.fundamentals import IssuerFacts
from .config import FACTOR_NAMES, SCOREABLE_STATES, VALID
from .factors import PriceSeries, compute_factors, market_block


class FundamentalsCache:
    """fundamentals() keyed by (cik, latest usable filing date)."""

    def __init__(self, issuers: dict[int, IssuerFacts]):
        self.issuers = issuers
        self._cache: dict[tuple[int, pd.Timestamp], dict] = {}

    def get(self, cik: int, usable_through: pd.Timestamp) -> dict:
        iss = self.issuers.get(int(cik)) if cik is not None and not pd.isna(cik) else None
        if iss is None or not iss.filing_dates:
            return {"status": "NO_SEC_FACTS"}
        i = np.searchsorted(np.array(iss.filing_dates, dtype="datetime64[ns]"), np.datetime64(usable_through),
                            side="right") - 1
        if i < 0:
            return {"status": "NO_FILINGS_BEFORE_ASOF"}
        fd = iss.filing_dates[i]
        key = (int(cik), fd)
        if key not in self._cache:
            self._cache[key] = iss.fundamentals(fd)
        return self._cache[key]


def build_cross_section(asof: pd.Timestamp, ref_session: pd.Timestamp, universe: pd.DataFrame,
                        prices: dict[str, PriceSeries], funds: FundamentalsCache, cfg: dict) -> pd.DataFrame:
    """universe columns: ticker, yahoo_ticker, security, sector, cik (+ optional extras)."""
    ucfg = cfg["universe"]
    lag = pd.Timedelta(days=cfg["fundamentals"]["filing_lag_days"])
    rows = []
    for u in universe.itertuples(index=False):
        rec = {"ticker": u.ticker, "yahoo_ticker": u.yahoo_ticker, "security": u.security,
               "sector": u.sector, "cik": None if pd.isna(u.cik) else int(u.cik)}
        rec["security_id"] = f"{rec['cik'] or 0:010d}:{u.ticker}"
        mkt = market_block(prices.get(u.yahoo_ticker), asof, ref_session, cfg["market_data"]["liquidity_window"])
        rec.update({k: mkt.get(k) for k in ("close", "raw_close", "liquidity_63", "last_price_date", "price_status")})
        status, reason = "ELIGIBLE", ""
        if u.sector in ucfg["excluded_sectors"]:
            status, reason = "OUTSIDE_STANDARD_MODEL", f"SECTOR_EXCLUDED:{u.sector}"
        elif rec["cik"] is None:
            status, reason = "DATA_BLOCKED", "NO_CIK"
        elif mkt["price_status"] in ("NO_PRICE_DATA", "STALE_PRICE", "INVALID_PRICE_DATA"):
            status, reason = "DATA_BLOCKED", mkt["price_status"]
        elif mkt.get("raw_close") is not None and mkt["raw_close"] < ucfg["min_raw_close_usd"]:
            status, reason = "INELIGIBLE", "BELOW_MIN_PRICE"
        elif mkt["price_status"] == "INSUFFICIENT_PRICE_HISTORY" or (
                mkt.get("history_months", 0) < ucfg["min_price_history_calendar_months"]):
            status, reason = "DATA_BLOCKED", "INSUFFICIENT_PRICE_HISTORY"
        rec["eligibility_status"], rec["eligibility_reason"] = status, reason
        if status in ("ELIGIBLE", "DATA_BLOCKED") and rec["cik"] is not None:
            fund = funds.get(rec["cik"], asof - lag)
            fac, inter = compute_factors(fund, mkt, asof, cfg)
        else:
            fac, inter = {n: {"value": None, "status": status, "detail": reason} for n in FACTOR_NAMES}, {}
        for n in FACTOR_NAMES:
            rec[n] = fac[n]["value"]
            rec[f"{n}_status"] = fac[n]["status"]
            rec[f"{n}_detail"] = fac[n]["detail"]
        rec.update(inter)
        rows.append(rec)
    cs = pd.DataFrame(rows)
    # Duplicate share classes of one issuer: keep the most liquid class.
    elig = cs["eligibility_status"].eq("ELIGIBLE")
    dup = cs.loc[elig & cs["cik"].notna()].copy()
    dup["_liq"] = dup["liquidity_63"].fillna(-1)
    dup = dup.sort_values(["cik", "_liq", "ticker"], ascending=[True, False, True])
    drop = dup.index[dup.duplicated("cik", keep="first")]
    cs.loc[drop, "eligibility_status"] = "DUPLICATE_CLASS_EXCLUDED"
    cs.loc[drop, "eligibility_reason"] = "LESS_LIQUID_SHARE_CLASS"
    return cs


def resilience(row: pd.Series, cfg: dict) -> tuple[bool, list[str]]:
    r = cfg["resilience"]
    fails = []
    for k, label in (("ebit_ttm", "EBIT"), ("cfo_ttm", "CFO"), ("fcf_ttm", "FCF")):
        v = row.get(k)
        if v is None or pd.isna(v) or v <= 0:
            fails.append(f"TTM_{label}_NOT_POSITIVE")
    years = row.get("fcf_annual_last3")
    if not isinstance(years, (list, tuple)) or sum(1 for y in years if y > 0) < r["positive_fcf_years_of_latest_three"]:
        fails.append("FCF_POSITIVE_YEARS")
    ebitda = row.get("ebitda_ttm")
    nd = row.get("net_debt_ebitda")
    if ebitda is None or pd.isna(ebitda) or ebitda <= 0 or nd is None or pd.isna(nd) or nd > r["max_net_debt_ebitda"]:
        fails.append("NET_DEBT_EBITDA")
    interest, ebit = row.get("interest_ttm"), row.get("ebit_ttm")
    if interest is not None and not pd.isna(interest) and interest > 0:
        if ebit is None or pd.isna(ebit) or ebit / interest < r["min_interest_coverage_if_interest_positive"]:
            fails.append("INTEREST_COVERAGE")
    if not (row.get("composite", np.nan) >= r["composite_score_floor_for_auto_priority"]):
        fails.append("COMPOSITE_FLOOR")
    if not (row.get("quality", np.nan) >= r["quality_family_floor_for_auto_priority"]):
        fails.append("QUALITY_FLOOR")
    return not fails, fails


def research_states(ranked: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    q = cfg["queues"]
    out = ranked.copy()
    states, core, fails = [], [], []
    for _, row in out.iterrows():
        rk = row["rank"]
        if pd.isna(rk):
            blocked = [n for n in FACTOR_NAMES if row[f"{n}_score_status"] not in SCOREABLE_STATES]
            only_peer = blocked and all(row[f"{n}_score_status"] == "PEER_SET_INSUFFICIENT" for n in blocked)
            states.append("SCORING_INCOMPLETE" if only_peer else "DATA_BLOCKED")
            core.append("")
            fails.append("")
            continue
        states.append("TOP10_PRIORITY" if rk <= q["priority_queue_size"] else
                      "TOP20_RESEARCH" if rk <= q["research_queue_size"] else "SCORED_NOT_PRIORITY")
        ok, f = resilience(row, cfg)
        core.append("CORE_POLICY_PASS" if ok else "OUTSIDE_CORE_POLICY")
        fails.append(";".join(f))
    out["research_state"] = states
    out["core_policy_status"] = core
    out["core_policy_failures"] = fails
    return out


def blocked_factor_summary(row: pd.Series) -> str:
    return ";".join(f"{n}:{row[f'{n}_score_status']}" for n in FACTOR_NAMES
                    if row[f"{n}_score_status"] not in SCOREABLE_STATES)


__all__ = ["FundamentalsCache", "build_cross_section", "research_states", "resilience",
           "blocked_factor_summary", "VALID"]
