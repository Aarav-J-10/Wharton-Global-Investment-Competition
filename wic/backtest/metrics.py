"""Performance and attribution statistics."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

ANN = 252


def drawdown(nav: pd.Series) -> pd.Series:
    return nav / nav.cummax() - 1.0


def perf_stats(r: pd.Series, rf: pd.Series, bench: pd.Series | None = None) -> dict:
    r = r.dropna()
    if len(r) < 2:
        return {}
    rf = rf.reindex(r.index).fillna(0.0)
    nav = (1 + r).cumprod()
    years = len(r) / ANN
    ex = r - rf
    downside = ex[ex < 0]
    monthly = (1 + r).resample("ME").prod() - 1
    dd = drawdown(nav)
    out = {
        "start": r.index[0].date().isoformat(), "end": r.index[-1].date().isoformat(), "days": int(len(r)),
        "total_return": float(nav.iloc[-1] - 1),
        "cagr": float(nav.iloc[-1] ** (1 / years) - 1) if years > 0 else np.nan,
        "ann_vol": float(r.std(ddof=1) * math.sqrt(ANN)),
        "sharpe": float(ex.mean() / ex.std(ddof=1) * math.sqrt(ANN)) if ex.std(ddof=1) > 0 else np.nan,
        "sortino": float(ex.mean() * ANN / (math.sqrt((downside ** 2).sum() / len(ex)) * math.sqrt(ANN)))
        if len(downside) else np.nan,
        "max_drawdown": float(dd.min()),
        "max_drawdown_trough": dd.idxmin().date().isoformat(),
        "best_month": float(monthly.max()), "worst_month": float(monthly.min()),
        "pct_positive_months": float((monthly > 0).mean()),
    }
    out["calmar"] = out["cagr"] / abs(out["max_drawdown"]) if out["max_drawdown"] < 0 else np.nan
    if bench is not None:
        out.update(relative_stats(r, bench.reindex(r.index), rf))
    return out


def relative_stats(r: pd.Series, b: pd.Series, rf: pd.Series) -> dict:
    import statsmodels.api as sm

    df = pd.concat({"r": r, "b": b, "rf": rf}, axis=1).dropna()
    active = df["r"] - df["b"]
    te = active.std(ddof=1) * math.sqrt(ANN)
    X = sm.add_constant(df["b"] - df["rf"])
    fit = sm.OLS(df["r"] - df["rf"], X).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    m = ((1 + df[["r", "b"]]).resample("ME").prod() - 1)
    m_active = m["r"] - m["b"]
    tm = sm.OLS(m_active.to_numpy(), np.ones(len(m_active))).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
    return {"beta": float(fit.params.iloc[1]), "alpha_ann": float(fit.params.iloc[0] * ANN),
            "alpha_tstat_hac": float(fit.tvalues.iloc[0]), "tracking_error": float(te),
            "information_ratio": float(active.mean() * ANN / te) if te > 0 else np.nan,
            "excess_cagr": float(((1 + df["r"]).prod()) ** (ANN / len(df)) - ((1 + df["b"]).prod()) ** (ANN / len(df))),
            "monthly_hit_rate": float((m_active > 0).mean()),
            "monthly_active_mean": float(m_active.mean()),
            "monthly_active_tstat_hac": float(tm.tvalues[0])}


def ic_summary(ic: pd.Series) -> dict:
    ic = ic.dropna()
    if len(ic) < 3:
        return {}
    sd = ic.std(ddof=1)
    return {"months": int(len(ic)), "mean_ic": float(ic.mean()), "ic_std": float(sd),
            "ic_ir": float(ic.mean() / sd) if sd > 0 else np.nan,
            "t_stat": float(ic.mean() / sd * math.sqrt(len(ic))) if sd > 0 else np.nan,
            "pct_positive": float((ic > 0).mean())}


def calendar_returns(daily: pd.DataFrame) -> pd.DataFrame:
    y = (1 + daily).groupby(daily.index.year).prod() - 1
    y.index.name = "year"
    return y
