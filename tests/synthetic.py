"""SYNTHETIC fixture generator for tests. Values are fabricated test data only.

Produces a snapshot directory with the same files/schemas as a real snapshot:
filings follow SEC companyfacts conventions (10-Q YTD cash flows, 3-month and
YTD income statements, prior-year comparatives, 10-K FY values, balance-sheet
instants, cover-page shares), including deliberate edge cases.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from wic.snapshot import seal
from wic.util import write_csv, write_json

SECTORS = {"Information Technology": 28, "Health Care": 26, "Industrials": 27, "Consumer Staples": 24,
           "Consumer Discretionary": 25, "Energy": 22, "Utilities": 21, "Financials": 8}


def _quarter_ends(start_year: int, end: pd.Timestamp) -> list[pd.Timestamp]:
    qs = pd.date_range(f"{start_year}-03-31", end, freq="QE")
    return [q.normalize() for q in qs]


def qstart(qe: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(year=qe.year, month=qe.month - 2, day=1)


def make_company(rng, cik: int, ticker: str, cutoff: pd.Timestamp, kind: str) -> tuple[list, dict]:
    """Return companyfacts-like rows and ground-truth parameters."""
    rows = []
    base_rev = rng.uniform(2e9, 40e9) / 4
    g = rng.uniform(-0.02, 0.05)          # quarterly growth
    margin = rng.uniform(0.08, 0.30)
    if kind == "loss":
        margin = -0.05
    da_ratio, capex_ratio, cfo_ratio = rng.uniform(0.03, 0.06), rng.uniform(0.03, 0.08), rng.uniform(0.12, 0.35)
    tax_rate = rng.uniform(0.15, 0.27)
    shares0 = rng.uniform(2e8, 2e9)
    debt0 = 0.0 if kind == "nodebt" else base_rev * rng.uniform(1, 6)
    cash0 = base_rev * rng.uniform(0.3, 2)
    eq0 = base_rev * rng.uniform(2, 8)
    qends = _quarter_ends(2014, cutoff - pd.Timedelta(days=50))
    quarter = {}
    for i, qe in enumerate(qends):
        rev = base_rev * (1 + g) ** i * (1 + rng.normal(0, 0.01))
        ebit = rev * margin
        quarter[qe] = dict(rev=rev, ebit=ebit, da=rev * da_ratio, cfo=rev * cfo_ratio, capex=rev * capex_ratio,
                           pretax=ebit - debt0 * 0.01, interest=debt0 * 0.01,
                           debt=debt0 * (1 + 0.01 * i), cash=cash0 * (1 + 0.02 * i), eq=eq0 * (1 + 0.015 * i))
        quarter[qe]["tax"] = max(quarter[qe]["pretax"], 0) * tax_rate
    split_date = pd.Timestamp("2020-08-31") if kind == "split" else None

    def shares_at(d):
        return shares0 * (4 if split_date is not None and d >= split_date else 1)

    def accn(i):
        return f"{cik:010d}-{i:02d}-{rng.integers(1e5, 9e5):06d}"

    def add(concept, start, end, val, a, form, filed, unit="USD"):
        rows.append(dict(cik=cik, concept=concept, unit=unit, start=start, end=end, val=float(val), accn=a,
                         fy=end.year, fp="FY" if form == "10-K" else f"Q{(end.month - 1) // 3 + 1}",
                         form=form, filed=filed))

    flows = {"Revenues": "rev", "OperatingIncomeLoss": "ebit", "IncomeTaxExpenseBenefit": "tax",
             "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest": "pretax",
             "InterestExpense": "interest"}
    cash_flows = {"NetCashProvidedByUsedInOperatingActivities": "cfo",
                  "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
                  "DepreciationDepletionAndAmortization": "da"}
    for i, qe in enumerate(qends):
        qn = (qe.month - 1) // 3 + 1
        fy_start = pd.Timestamp(year=qe.year, month=1, day=1)
        is_fy = qn == 4
        form = "10-K" if is_fy else "10-Q"
        filed = qe + pd.Timedelta(days=60 if is_fy else 40)
        if filed > cutoff:
            continue
        a = accn(i)
        ytd_q = [q for q in qends if fy_start <= q <= qe]
        py = qe - pd.DateOffset(years=1)
        py_ytd_q = [q for q in qends if q.year == py.year and q <= py]
        for concept, key in {**flows, **cash_flows}.items():
            if kind == "nocapex" and key == "capex":
                continue
            ytd = sum(quarter[q][key] for q in ytd_q)
            add(concept, fy_start, qe, ytd, a, form, filed)
            if py_ytd_q and all(q in quarter for q in py_ytd_q):
                add(concept, pd.Timestamp(year=py.year, month=1, day=1), py_ytd_q[-1],
                    sum(quarter[q][key] for q in py_ytd_q), a, form, filed)
            if concept in flows and not is_fy:  # discrete 3-month income statement
                add(concept, qstart(qe), qe, quarter[qe][key], a, form, filed)
        if is_fy:
            sh = shares_at(filed)
            ni = (sum(quarter[q]["pretax"] - quarter[q]["tax"] for q in ytd_q))
            add("EarningsPerShareDiluted", fy_start, qe, ni / sh, a, form, filed, "USD/shares")
        add("CashAndCashEquivalentsAtCarryingValue", None, qe, quarter[qe]["cash"], a, form, filed)
        if kind != "nodebt":
            add("LongTermDebtNoncurrent", None, qe, quarter[qe]["debt"] * 0.9, a, form, filed)
            add("LongTermDebtCurrent", None, qe, quarter[qe]["debt"] * 0.1, a, form, filed)
        add("StockholdersEquity", None, qe, quarter[qe]["eq"], a, form, filed)
        add("Liabilities", None, qe, quarter[qe]["debt"] * 1.5 + 1e9, a, form, filed)
        add("dei:EntityCommonStockSharesOutstanding", None, filed - pd.Timedelta(days=5), shares_at(filed), a, form,
            filed, "shares")
        add("WeightedAverageNumberOfDilutedSharesOutstanding", qstart(qe), qe, shares_at(filed), a, form, filed, "shares")
    truth = dict(quarter=quarter, split_date=split_date, shares0=shares0, tax_rate=tax_rate, kind=kind)
    return rows, truth


def make_prices(rng, tickers: list[str], start: str, end: pd.Timestamp, splits: dict) -> pd.DataFrame:
    dates = pd.bdate_range(start, end)
    frames = []
    for t in tickers:
        mu, sig = rng.uniform(-0.0002, 0.0008), rng.uniform(0.01, 0.03)
        r = rng.normal(mu, sig, len(dates))
        adj = 50 * np.exp(np.cumsum(r))
        div_yield_daily = rng.uniform(0, 0.03) / 252
        close = adj * np.exp(div_yield_daily * np.arange(len(dates))[::-1])  # adj < close in the past
        sp = np.zeros(len(dates))
        if t in splits:
            k = np.searchsorted(dates, splits[t])
            sp[k] = 4.0
        frames.append(pd.DataFrame({"date": dates, "ticker": t, "close": close, "adj_close": adj,
                                    "volume": rng.uniform(1e6, 5e6, len(dates)), "dividends": 0.0, "splits": sp}))
    return pd.concat(frames, ignore_index=True)


def build_snapshot(root: Path, cutoff: str = "2026-10-16", seed: int = 7) -> tuple[Path, dict]:
    rng = np.random.default_rng(seed)
    cutoff = pd.Timestamp(cutoff)
    snap = root / f"sp500_{cutoff.date()}"
    snap.mkdir(parents=True, exist_ok=True)
    uni, facts, truths, splits = [], [], {}, {}
    cik = 100000
    kinds = ["normal"] * 20 + ["nodebt", "loss", "split", "nocapex"]
    for sector, n in SECTORS.items():
        for j in range(n):
            cik += 1
            t = f"{"ABCDEFGH"[list(SECTORS).index(sector)]}X{j:02d}"
            kind = kinds[j % len(kinds)]
            rows, truth = make_company(rng, cik, t, cutoff, kind)
            facts += rows
            truths[t] = {**truth, "cik": cik}
            if truth["split_date"] is not None:
                splits[t] = truth["split_date"]
            uni.append(dict(ticker=t, security=f"Synthetic {t}", sector=sector, gics_sub_industry="X", cik=cik,
                            date_added="2000-01-01", yahoo_ticker=t))
    uni = pd.DataFrame(uni)
    prices = make_prices(rng, list(uni["ticker"]) + ["SPY", "RSP"], "2012-01-02", cutoff, splits)
    irx = pd.DataFrame({"date": pd.bdate_range("2012-01-02", cutoff), "ticker": "^IRX", "close": 4.0,
                        "adj_close": 4.0, "volume": 0.0, "dividends": 0.0, "splits": 0.0})
    prices = pd.concat([prices, irx], ignore_index=True)
    facts = pd.DataFrame(facts)
    for c in ("start", "end", "filed"):
        facts[c] = pd.to_datetime(facts[c])
    dates = pd.date_range("2013-01-01", cutoff, freq="YS")
    hist = pd.DataFrame({"date": dates, "tickers": ",".join(uni["ticker"])})
    sect = pd.concat([uni.assign(label_date=d)[["label_date", "ticker", "yahoo_ticker", "security", "sector", "cik"]]
                      for d in pd.date_range("2013-01-01", cutoff, freq="6MS")])
    write_csv(snap / "universe.csv", uni)
    write_csv(snap / "membership_history.csv", hist.assign(date=hist["date"].dt.date))
    write_csv(snap / "sector_history.csv", sect.assign(label_date=sect["label_date"].dt.date))
    prices.to_parquet(snap / "prices.parquet", index=False)
    facts.to_parquet(snap / "sec_facts.parquet", index=False)
    write_csv(snap / "sec_sources.csv", pd.DataFrame({"cik": uni["cik"], "url": "synthetic", "raw_sha256": "synthetic",
                                                      "entity_name": uni["security"]}))
    write_csv(snap / "sec_ticker_map.csv", uni[["ticker", "cik"]])
    write_json(snap / "SOURCES.json", {"cutoff": cutoff.date().isoformat(), "SYNTHETIC": True,
                                       "universe": {"source": "SYNTHETIC TEST FIXTURE"}})
    seal(snap)
    return snap, truths
