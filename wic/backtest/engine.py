"""Point-in-time walk-forward backtest of the WIC-S003 screen.

At every month-end session t:
  * universe   = S&P 500 members on t (fja05680 point-in-time list)
  * labels     = GICS sector / CIK from the latest Wikipedia revision <= t
  * fundamentals = SEC facts filed on or before t - filing_lag
  * prices     = data on or before t
  * scoring    = the production cross-section + sector scoring code, unchanged
Portfolios are formed at the close of t and held (buy-and-hold, drifting
weights) to the next rebalance close. Weights/factors were fixed ex ante by the
September 2026 specification; nothing is fitted to these results.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from ..config import FACTOR_NAMES, FAMILIES, load_config
from ..cross_section import FundamentalsCache, build_cross_section
from ..pipeline import code_hash, load_issuers, load_market
from ..scoring import diversified_view, score_universe
from ..snapshot import Snapshot
from ..sources.universe import members_on, yahoo_symbol
from ..util import canonical_json, sha256_bytes, sha256_file, utc_now, write_csv, write_json
from . import metrics as M

log = logging.getLogger("wic.backtest")
QUINTILES = 5


def month_end_sessions(sessions: pd.DatetimeIndex, start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    s = pd.Series(sessions, index=sessions)
    s = s[(s >= start) & (s <= end)]
    return list(s.groupby([s.index.year, s.index.month]).max())


class LabelBook:
    """Point-in-time ticker -> (sector, cik, security) from revision history."""

    def __init__(self, sect: pd.DataFrame, current: pd.DataFrame, sec_map: pd.DataFrame):
        sect = sect.sort_values(["ticker", "label_date"])
        self.by_ticker = {t: g.reset_index(drop=True) for t, g in sect.groupby("ticker")}
        self.current = current.set_index("ticker")
        self.sec_cik = dict(zip(sec_map["ticker"].astype(str).str.replace("-", "."), sec_map["cik"]))

    def label(self, ticker: str, t: pd.Timestamp) -> dict | None:
        g = self.by_ticker.get(ticker)
        row = None
        if g is not None:
            before = g.loc[g["label_date"] <= t]
            row = before.iloc[-1] if len(before) else g.iloc[0]
            cik = row["cik"]
            if pd.isna(cik):
                known = g["cik"].dropna()
                cik = known.iloc[(g.loc[known.index, "label_date"] - t).abs().argmin()] if len(known) else pd.NA
            return {"sector": row["sector"], "cik": cik, "security": row["security"]}
        if ticker in self.current.index:
            r = self.current.loc[ticker]
            return {"sector": r["sector"], "cik": r["cik"], "security": r["security"]}
        return None


def _pnl(adj: pd.DataFrame, holdings: dict[str, float], t0: pd.Timestamp, t1: pd.Timestamp) -> tuple[pd.Series, dict]:
    """Daily returns over (t0, t1] for a buy-and-hold book; returns end weights."""
    window = adj.loc[t0:t1, list(holdings)]
    window = window.ffill()  # a name that stops trading is held at its last price (cash-like)
    base = window.iloc[0]
    growth = window / base
    w0 = pd.Series(holdings)
    value = growth.mul(w0, axis=1).sum(axis=1)
    rets = value.pct_change().iloc[1:]
    end_w = growth.iloc[-1] * w0
    end_w = end_w / end_w.sum()
    return rets, end_w.to_dict()


def run_backtest(snapshot_path: str | Path, out_root: str | Path, config_path: str | Path | None = None,
                 start: str | None = None, end: str | None = None) -> Path:
    cfg = load_config(config_path)
    bcfg = cfg["backtest"]
    snap = Snapshot(snapshot_path)
    cfg_hash = sha256_bytes(canonical_json(cfg).encode())[:12]
    run_id = f"{snap.manifest['snapshot_id']}__backtest__cfg{cfg_hash}"
    out = Path(out_root) / run_id
    out.mkdir(parents=True, exist_ok=True)
    started = utc_now()

    prices, series = load_market(snap)
    adj = prices.pivot(index="date", columns="ticker", values="adj_close").sort_index()
    sessions = adj["SPY"].dropna().index
    hist = snap.membership_history()
    sect = snap.sector_history()
    current = snap.universe()
    sec_map = pd.read_csv(snap.path / "sec_ticker_map.csv")
    labels = LabelBook(sect, current, sec_map)

    ticker_for_cik = {}
    for r in sect.sort_values("label_date").itertuples():
        if pd.notna(r.cik):
            ticker_for_cik[int(r.cik)] = r.yahoo_ticker
    for r in current.itertuples():
        if pd.notna(r.cik):
            ticker_for_cik[int(r.cik)] = r.yahoo_ticker
    funds = FundamentalsCache(load_issuers(snap, ticker_for_cik, series))

    t_start = pd.Timestamp(start or bcfg["start"])
    t_end = pd.Timestamp(end) if end else snap.cutoff
    rebal = month_end_sessions(sessions, t_start, t_end)
    if len(rebal) < 2:
        raise RuntimeError("Backtest window needs at least two rebalance dates")

    sc = cfg["scoring"]
    books_by_date, coverage, holdings_rows, ic_rows = {}, [], [], []
    for t in rebal:
        members = members_on(hist, t)
        rows, unlabeled = [], 0
        for tk in members:
            lab = labels.label(tk, t)
            if lab is None:
                unlabeled += 1
                continue
            rows.append({"ticker": tk, "yahoo_ticker": yahoo_symbol(tk), "security": lab["security"],
                         "sector": lab["sector"], "cik": lab["cik"]})
        uni = pd.DataFrame(rows)
        uni["cik"] = pd.to_numeric(uni["cik"], errors="coerce").astype("Int64")
        cs = build_cross_section(t, t, uni, series, funds, cfg)
        eligible = cs.loc[cs["eligibility_status"].eq("ELIGIBLE")]
        ranked = score_universe(eligible, min_peers=sc["min_valid_peers_per_metric"],
                                winsor=tuple(sc["winsor_quantiles"]), sentinel_score=sc["economic_sentinel_score"])
        comp = ranked.loc[ranked["rank"].notna()].sort_values("rank")
        with_price = int((~cs["price_status"].isin(["NO_PRICE_DATA"])).sum())
        coverage.append({"date": t.date(), "pit_members": len(members), "unlabeled": unlabeled,
                         "with_price_data": with_price, "no_price_data_survivorship_gap": len(members) - unlabeled - with_price,
                         "outside_standard_model": int(cs["eligibility_status"].eq("OUTSIDE_STANDARD_MODEL").sum()),
                         "eligible": len(eligible), "complete_scores": len(comp)})
        books = {}
        if len(comp) >= 20:
            books["TOP10"] = list(comp.head(10)["yahoo_ticker"])
            books["TOP20"] = list(comp.head(20)["yahoo_ticker"])
            dv = diversified_view(comp, 10, cfg["queues"]["max_priority_names_same_sector"])
            books["TOP10_SECTOR_CAPPED"] = list(dv["yahoo_ticker"])
            q = pd.qcut(comp["rank"].astype(float), QUINTILES, labels=False)
            for k in range(QUINTILES):
                books[f"Q{k + 1}"] = list(comp.loc[q.eq(k).to_numpy(), "yahoo_ticker"])
            books["SCORED_UNIVERSE_EW"] = list(comp["yahoo_ticker"])
        pit = cs.loc[~cs["price_status"].isin(["NO_PRICE_DATA", "STALE_PRICE", "INVALID_PRICE_DATA"]), "yahoo_ticker"]
        books["PIT_MEMBERS_EW"] = sorted(set(pit) & set(adj.columns))
        books_by_date[t] = books
        for name in ("TOP10", "TOP20", "TOP10_SECTOR_CAPPED"):
            for tk in books.get(name, []):
                r = comp.loc[comp["yahoo_ticker"].eq(tk)].iloc[0]
                holdings_rows.append({"date": t.date(), "portfolio": name, "ticker": r["ticker"], "sector": r["sector"],
                                      "rank": int(r["rank"]), "composite": r["composite"], "quality": r["quality"]})
        ic_rows.append((t, comp[["yahoo_ticker", "composite", *[f.lower() for f in FAMILIES],
                                 *[f"{n}_score" for n in FACTOR_NAMES]]].copy()))
        log.info("%s members=%d eligible=%d complete=%d", t.date(), len(members), len(eligible), len(comp))

    # ---------------- P&L
    cost = bcfg["transaction_cost_bps_one_way"] / 1e4
    names = sorted({k for b in books_by_date.values() for k in b})
    gross, net, turnover_rows = {}, {}, []
    for name in names:
        g_parts, n_parts, prev_end = [], [], {}
        for i, t0 in enumerate(rebal):
            t1 = rebal[i + 1] if i + 1 < len(rebal) else t_end
            if t1 <= t0:
                break
            book = [x for x in books_by_date[t0].get(name, []) if x in adj.columns and pd.notna(adj.at[t0, x])]
            if not book:
                prev_end = {}
                continue
            target = {x: 1.0 / len(book) for x in book}
            keys = set(target) | set(prev_end)
            traded = sum(abs(target.get(k, 0.0) - prev_end.get(k, 0.0)) for k in keys)
            turnover_rows.append({"date": t0.date(), "portfolio": name, "one_way_turnover": traded / 2,
                                  "holdings": len(book)})
            rets, prev_end = _pnl(adj, target, t0, t1)
            g_parts.append(rets)
            nr = rets.copy()
            if len(nr):
                nr.iloc[0] = (1 + nr.iloc[0]) * (1 - traded * cost) - 1
            n_parts.append(nr)
        if g_parts:
            gross[name] = pd.concat(g_parts)
            net[name] = pd.concat(n_parts)
    span = (adj.index > rebal[0]) & (adj.index <= t_end)
    bench = {b: adj[b].pct_change().loc[span] for b in bcfg["benchmarks"] if b in adj.columns}
    irx = prices.loc[prices["ticker"].eq("^IRX")].set_index("date")["close"]
    rf = (irx.reindex(adj.index).ffill() / 100.0 / M.ANN).loc[span].fillna(0.0)

    daily_net = pd.DataFrame(net)
    daily_gross = pd.DataFrame(gross)
    daily_bench = pd.DataFrame(bench)
    daily = pd.concat([daily_net, daily_bench], axis=1).sort_index()
    write_csv(out / "daily_returns_net.csv", daily.reset_index().rename(columns={"index": "date"}))
    write_csv(out / "daily_returns_gross.csv", daily_gross.reset_index().rename(columns={"index": "date"}))
    monthly = (1 + daily).resample("ME").prod() - 1
    write_csv(out / "monthly_returns_net.csv", monthly.reset_index().rename(columns={"index": "month"}))
    write_csv(out / "calendar_year_returns_net.csv", M.calendar_returns(daily).reset_index())
    write_csv(out / "holdings.csv", pd.DataFrame(holdings_rows))
    write_csv(out / "turnover.csv", pd.DataFrame(turnover_rows))
    cov = pd.DataFrame(coverage)
    write_csv(out / "rebalance_coverage.csv", cov)

    # ---------------- information coefficients (forward 1-month total return)
    ic_records = []
    for i, (t0, frame) in enumerate(ic_rows[:-1]):
        t1 = rebal[i + 1]
        cols = [c for c in frame["yahoo_ticker"] if c in adj.columns]
        fwd = adj.loc[t1, cols] / adj.loc[t0, cols] - 1
        f = frame.set_index("yahoo_ticker").loc[cols].assign(fwd=fwd).dropna(subset=["fwd"])
        rec = {"date": t0.date(), "n": len(f)}
        if len(f) >= 20:
            for c in ["composite", *[x.lower() for x in FAMILIES], *[f"{n}_score" for n in FACTOR_NAMES]]:
                rec[c] = spearmanr(f[c], f["fwd"]).statistic
        ic_records.append(rec)
    ic = pd.DataFrame(ic_records)
    write_csv(out / "ic_series.csv", ic)

    rf_series = rf
    summary = {"run_id": run_id, "snapshot_id": snap.manifest["snapshot_id"], "code_sha256": code_hash(),
               "config_sha256_12": cfg_hash, "rebalances": len(rebal), "first_rebalance": rebal[0].date().isoformat(),
               "last_rebalance": rebal[-1].date().isoformat(), "end": t_end.date().isoformat(),
               "transaction_cost_bps_one_way": bcfg["transaction_cost_bps_one_way"],
               "avg_complete_scores": float(cov["complete_scores"].mean()),
               "avg_pit_members": float(cov["pit_members"].mean()),
               "avg_survivorship_gap_names": float(cov["no_price_data_survivorship_gap"].mean()),
               "portfolios_net": {}, "portfolios_gross": {}, "benchmarks": {}, "ic": {}}
    spy = daily_bench.get("SPY")
    ew = daily_net.get("SCORED_UNIVERSE_EW")
    for name in daily_net:
        s = M.perf_stats(daily_net[name], rf_series, spy)
        if ew is not None and name != "SCORED_UNIVERSE_EW":
            rel = M.relative_stats(daily_net[name], ew, rf_series)
            s.update({f"vs_scored_universe_{k}": v for k, v in rel.items()})
        to = pd.DataFrame(turnover_rows)
        sel = to.loc[to["portfolio"].eq(name)]
        s["avg_one_way_turnover"] = float(sel["one_way_turnover"].iloc[1:].mean()) if len(sel) > 1 else np.nan
        s["avg_holdings"] = float(sel["holdings"].mean()) if len(sel) else np.nan
        summary["portfolios_net"][name] = s
        summary["portfolios_gross"][name] = M.perf_stats(daily_gross[name], rf_series, spy)
    for b in daily_bench:
        summary["benchmarks"][b] = M.perf_stats(daily_bench[b], rf_series)
    for c in [c for c in ic.columns if c not in ("date", "n")]:
        summary["ic"][c] = M.ic_summary(ic[c])
    q_cagr = {q: summary["portfolios_net"].get(q, {}).get("cagr") for q in [f"Q{k + 1}" for k in range(QUINTILES)]}
    vals = [v for v in q_cagr.values() if v is not None]
    summary["quintile_cagr_net"] = q_cagr
    summary["quintile_monotonic"] = bool(len(vals) == QUINTILES and all(np.diff(vals) <= 0))
    write_json(out / "BACKTEST_SUMMARY.json", summary)

    from .report import write_report
    write_report(out, summary, daily, ic, cov, cfg)
    manifest = {"run_id": run_id, "snapshot_manifest_sha256": sha256_file(snap.path / "MANIFEST.json"),
                "code_sha256": summary["code_sha256"],
                "outputs": {p.name: sha256_file(p) for p in sorted(out.iterdir())
                            if p.is_file() and p.suffix in (".csv", ".json", ".md") and p.name not in
                            ("run_manifest.json", "RUN_LOG.json")}}
    write_json(out / "run_manifest.json", manifest)
    write_json(out / "RUN_LOG.json", {"started_utc": started, "finished_utc": utc_now()})
    return out
