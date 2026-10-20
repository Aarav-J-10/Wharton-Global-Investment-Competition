"""Backtest report: markdown + static charts (light surface, validated palette)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

SURFACE, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3 (validated all-pairs set)
LABELS = {"TOP10": "Top 10 (EW)", "TOP20": "Top 20 (EW)", "TOP10_SECTOR_CAPPED": "Top 10 sector-capped",
          "SCORED_UNIVERSE_EW": "Scored universe (EW)", "PIT_MEMBERS_EW": "All PIT members w/ prices (EW)",
          "SPY": "S&P 500 (SPY)", "RSP": "S&P 500 equal weight (RSP)"}


def _style(ax):
    ax.set_facecolor(SURFACE)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def charts(out: Path, daily: pd.DataFrame, ic: pd.DataFrame, summary: dict) -> list[str]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    files = []
    trio = [c for c in ("TOP10", "SPY", "SCORED_UNIVERSE_EW") if c in daily]
    if trio:
        d = daily[trio].dropna()
        nav = (1 + d).cumprod()
        fig, ax = plt.subplots(figsize=(9, 4.6), facecolor=SURFACE)
        _style(ax)
        for c, col in zip(trio, SERIES):
            ax.plot(nav.index, nav[c], color=col, linewidth=2, label=LABELS[c])
        ax.set_yscale("log")
        from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter
        ax.yaxis.set_major_locator(LogLocator(base=10, subs=(1.0, 1.5, 2.0, 3.0, 5.0, 7.0)))
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:g}x"))
        ax.yaxis.set_minor_formatter(NullFormatter())
        # End labels, nudged apart in log space so they never overlap.
        ends = sorted(((float(np.log(nav[c].iloc[-1])), c) for c in trio))
        lo, hi = np.log(ax.get_ylim())
        gap = (hi - lo) * 0.045
        placed = []
        for y, c in ends:
            y = max(y, placed[-1] + gap) if placed else y
            placed.append(y)
            ax.annotate(f"{nav[c].iloc[-1]:.2f}x", (nav.index[-1], float(np.exp(y))), xytext=(4, 0),
                        textcoords="offset points", color=INK2, fontsize=9, va="center", annotation_clip=False)
        ax.set_title("Growth of $1, net of 10 bps one-way costs (log scale)", color=INK, fontsize=11, loc="left")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left")
        fig.tight_layout()
        fig.savefig(out / "chart_equity_curve.png", dpi=144)
        plt.close(fig)
        files.append("chart_equity_curve.png")

        fig, ax = plt.subplots(figsize=(9, 3.2), facecolor=SURFACE)
        _style(ax)
        for c, col in zip(trio, SERIES):
            dd = nav[c] / nav[c].cummax() - 1
            ax.plot(dd.index, dd * 100, color=col, linewidth=1.5, label=LABELS[c])
        ax.set_title("Drawdown from prior peak (%)", color=INK, fontsize=11, loc="left")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="lower left")
        fig.tight_layout()
        fig.savefig(out / "chart_drawdown.png", dpi=144)
        plt.close(fig)
        files.append("chart_drawdown.png")

    qs = [f"Q{k}" for k in range(1, 6)]
    qv = [summary["portfolios_net"].get(q, {}).get("cagr") for q in qs]
    if all(v is not None for v in qv):
        fig, ax = plt.subplots(figsize=(6, 3.4), facecolor=SURFACE)
        _style(ax)
        bars = ax.bar(qs, [v * 100 for v in qv], color=SERIES[0], width=0.6)
        for b, v in zip(bars, qv):
            ax.annotate(f"{v * 100:.1f}%", (b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, 3 if v >= 0 else -12), textcoords="offset points", ha="center",
                        color=INK2, fontsize=9)
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_title("Net CAGR by composite-score quintile (Q1 = best)", color=INK, fontsize=11, loc="left")
        fig.tight_layout()
        fig.savefig(out / "chart_quintiles.png", dpi=144)
        plt.close(fig)
        files.append("chart_quintiles.png")

    if "composite" in ic and ic["composite"].notna().sum() > 12:
        s = ic.set_index(pd.to_datetime(ic["date"]))["composite"]
        fig, ax = plt.subplots(figsize=(9, 3.2), facecolor=SURFACE)
        _style(ax)
        ax.bar(s.index, s, width=20, color=SERIES[0], alpha=0.45, label="Monthly rank IC")
        ax.plot(s.index, s.rolling(12).mean(), color=SERIES[1], linewidth=2, label="12-month average")
        ax.axhline(0, color=INK2, linewidth=0.8)
        ax.set_title("Composite score vs next-month return: Spearman rank IC", color=INK, fontsize=11, loc="left")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc="upper left")
        fig.tight_layout()
        fig.savefig(out / "chart_ic.png", dpi=144)
        plt.close(fig)
        files.append("chart_ic.png")
    return files


def _p(x, nd=1):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x * 100:.{nd}f}%"


def _n(x, nd=2):
    return "n/a" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:.{nd}f}"


def write_report(out: Path, summary: dict, daily: pd.DataFrame, ic: pd.DataFrame, cov: pd.DataFrame, cfg: dict) -> None:
    files = charts(out, daily, ic, summary)
    P = summary["portfolios_net"]
    rows = ["| Portfolio | CAGR | Vol | Sharpe | Max DD | Beta | Alpha (ann.) | Alpha t (HAC) | IR vs SPY | Turnover/mo |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    order = ["TOP10", "TOP10_SECTOR_CAPPED", "TOP20", "Q1", "Q2", "Q3", "Q4", "Q5", "SCORED_UNIVERSE_EW",
             "PIT_MEMBERS_EW"]
    for k in order:
        s = P.get(k)
        if not s:
            continue
        rows.append(f"| {LABELS.get(k, k)} | {_p(s['cagr'])} | {_p(s['ann_vol'])} | {_n(s['sharpe'])} | "
                    f"{_p(s['max_drawdown'])} | {_n(s.get('beta'))} | {_p(s.get('alpha_ann'))} | "
                    f"{_n(s.get('alpha_tstat_hac'))} | {_n(s.get('information_ratio'))} | "
                    f"{_p(s.get('avg_one_way_turnover'), 0)} |")
    for b, s in summary["benchmarks"].items():
        rows.append(f"| {LABELS.get(b, b)} | {_p(s['cagr'])} | {_p(s['ann_vol'])} | {_n(s['sharpe'])} | "
                    f"{_p(s['max_drawdown'])} | 1.00 | — | — | — | — |")
    ics = summary["ic"]
    ic_rows = ["| Signal | Mean IC | IC IR | t-stat | % months > 0 |", "|---|---:|---:|---:|---:|"]
    for k, v in ics.items():
        if v:
            ic_rows.append(f"| {k} | {_n(v['mean_ic'], 3)} | {_n(v['ic_ir'])} | {_n(v['t_stat'])} | {_p(v['pct_positive'], 0)} |")
    t10 = P.get("TOP10", {})
    rel = {k[len("vs_scored_universe_"):]: v for k, v in t10.items() if k.startswith("vs_scored_universe_")}
    cal = pd.read_csv(out / "calendar_year_returns_net.csv")
    cal_cols = [c for c in ("TOP10", "TOP10_SECTOR_CAPPED", "SCORED_UNIVERSE_EW", "SPY") if c in cal]
    cal_rows = ["| Year | " + " | ".join(LABELS[c] for c in cal_cols) + " |", "|---|" + "---:|" * len(cal_cols)]
    for _, r in cal.iterrows():
        cal_rows.append(f"| {int(r['year'])} | " + " | ".join(_p(r[c]) for c in cal_cols) + " |")
    lines = [
        f"# WIC-S003 Walk-Forward Backtest — {summary['run_id']}", "",
        f"Monthly rebalance {summary['first_rebalance']} → {summary['last_rebalance']} (returns through "
        f"{summary['end']}), {summary['rebalances']} rebalances, equal-weight books, "
        f"{summary['transaction_cost_bps_one_way']} bps one-way transaction cost on traded notional.", "",
        "**Model weights and factor definitions were fixed by the September 2026 specification before this "
        "test and were not tuned on it.** This is a historical simulation, not a forecast.", "",
        "## Performance (net of costs)", "", *rows, "",
        f"Quintile monotonic (Q1 ≥ Q2 ≥ … ≥ Q5 by CAGR): **{summary['quintile_monotonic']}**", "",
        "## Top 10 vs the scored universe (same survivorship exposure)", "",
        f"- Excess CAGR {_p(rel.get('excess_cagr'))}, tracking error {_p(rel.get('tracking_error'))}, "
        f"IR {_n(rel.get('information_ratio'))}, monthly hit rate {_p(rel.get('monthly_hit_rate'), 0)}, "
        f"monthly active-return t-stat (HAC) {_n(rel.get('monthly_active_tstat_hac'))}.",
        "- This comparison is the most robust read: both legs draw from the same point-in-time, "
        "price-available universe, so the survivorship gap affects them alike.", "",
        "## Signal quality: rank information coefficients (next-month total return)", "", *ic_rows, "",
        "## Calendar-year returns (net)", "", *cal_rows, "",
        *[f"![{f}]({f})" for f in files], "",
        "## Data coverage per rebalance", "",
        f"- Average point-in-time members: {summary['avg_pit_members']:.0f}; average complete 11-factor scores: "
        f"{summary['avg_complete_scores']:.0f}.",
        f"- Average members with no obtainable price history (delisted/renamed tickers absent from Yahoo): "
        f"{summary['avg_survivorship_gap_names']:.1f} — see rebalance_coverage.csv.", "",
        "## Method and controls", "",
        "- Universe: S&P 500 membership on each rebalance date (fja05680/sp500 point-in-time list). "
        "GICS sector and CIK labels from the most recent Wikipedia revision on or before the date.",
        "- Fundamentals: only SEC XBRL facts whose filing date is at least "
        f"{cfg['fundamentals']['filing_lag_days']} day before the rebalance; restatements filed later are not visible.",
        "- Prices: total-return (dividend + split adjusted) closes up to the rebalance close.",
        "- Scoring: identical production code as the live screen (sector-relative, 20-peer minimum, 5/95 "
        "winsorization, midrank percentiles, all 11 factors required, no imputation).",
        "- Execution: trades at the rebalance close; names that stop trading are held at last price (cash-like).", "",
        "## Known limitations (read before quoting any number)", "",
        "1. **Survivorship:** Yahoo Finance does not carry most delisted symbols, so members that were later "
        "acquired/bankrupt and lack price history are excluded from that month's universe. This biases "
        "absolute returns upward for every portfolio built from the universe; comparisons against the scored "
        "universe are less affected than comparisons against SPY.",
        "2. **Ticker identity:** price histories are keyed by ticker; a recycled ticker could in rare cases "
        "attach another issuer's prices.",
        "3. **Costs:** a flat cost assumption; no market impact, borrow or taxes. Long-only, no leverage.",
        "4. **Sector labels** come from semiannual Wikipedia snapshots, so a reclassification is picked up "
        "with up to ~6 months delay.",
        "5. Past simulated performance does not predict future returns. Ranks are research priorities, not orders.",
    ]
    (out / "BACKTEST_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
