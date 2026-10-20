"""Independent validator for a screen run.

Deliberately does NOT import wic.scoring: it re-derives every normalized score,
composite and rank from the published factor_values.csv using a separate
implementation (scipy.stats.rankdata) and the weight table restated from the
specification. Any disagreement fails the run's publication gate.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

SPEC = {  # restated from WIC-S003 spec v1.1 section 11 (independent copy)
    "roic": (0.12, 1, "QUALITY"), "fcf_margin": (0.10, 1, "QUALITY"), "net_debt_ebitda": (0.08, -1, "QUALITY"),
    "fcf_yield": (0.10, 1, "VALUATION"), "ev_ebit": (0.10, -1, "VALUATION"),
    "revenue_cagr_3y": (0.10, 1, "GROWTH"), "eps_cagr_3y": (0.10, 1, "GROWTH"),
    "momentum_12_1": (0.12, 1, "MOMENTUM"), "momentum_6_1": (0.08, 1, "MOMENTUM"),
    "volatility_252": (0.05, -1, "RISK"), "max_drawdown_252": (0.05, -1, "RISK"),
}
TOL = 1e-6


def _expected_scores(fv: pd.DataFrame, min_peers: int, lo: float, hi: float) -> pd.Series:
    exp = pd.Series(np.nan, index=fv.index)
    for (sector, factor), g in fv.groupby(["sector", "factor"]):
        valid = g["status"].eq("VALID") & np.isfinite(g["raw_value"].astype(float))
        n = int(valid.sum())
        if n < min_peers:
            continue
        x = g.loc[valid, "raw_value"].astype(float).to_numpy()
        a, b = np.quantile(x, [lo, hi])
        r = rankdata(np.minimum(np.maximum(x, a), b), method="average")
        p = 100.0 * (r - 0.5) / n
        exp.loc[g.index[valid.to_numpy()]] = p if SPEC[factor][1] > 0 else 100.0 - p
        exp.loc[g.index[g["status"].eq("ECONOMICALLY_UNFAVORABLE").to_numpy()]] = 0.0
    return exp


def validate_run(run_dir: str | Path, cutoff: pd.Timestamp, min_peers: int = 20,
                 winsor: tuple[float, float] = (0.05, 0.95)) -> dict:
    run = Path(run_dir)
    checks: dict[str, bool] = {}
    notes: list[str] = []
    checks["weights_sum_to_one"] = math.isclose(math.fsum(w for w, _, _ in SPEC.values()), 1.0)

    fv = pd.read_csv(run / "factor_values.csv")
    fv["raw_value"] = pd.to_numeric(fv["raw_value"], errors="coerce")
    fv["score"] = pd.to_numeric(fv["score"], errors="coerce")
    exp = _expected_scores(fv, min_peers, *winsor)
    both = exp.notna() | fv["score"].notna()
    diff = (exp[both] - fv.loc[both, "score"]).abs()
    checks["scores_recomputed_match"] = bool(len(diff) == 0 or (diff.fillna(np.inf) <= TOL).all())
    if not checks["scores_recomputed_match"]:
        notes.append(f"{int((diff.fillna(np.inf) > TOL).sum())} score mismatches")
    s = fv["score"].dropna()
    checks["scores_within_0_100"] = bool(((s >= 0) & (s <= 100)).all())
    unf = fv.loc[fv["status"].eq("ECONOMICALLY_UNFAVORABLE") & fv["score"].notna(), "score"]
    checks["sentinels_scored_zero"] = bool((unf == 0).all())

    # Direction: within a sector-metric, a strictly better raw value never scores lower.
    mono = True
    for (sector, factor), g in fv.loc[fv["status"].eq("VALID") & fv["score"].notna()].groupby(["sector", "factor"]):
        order = np.argsort(g["raw_value"].to_numpy() * SPEC[factor][1], kind="stable")
        sc = g["score"].to_numpy()[order]
        if np.any(np.diff(sc) < -TOL):
            mono = False
            notes.append(f"direction violation {sector}/{factor}")
    checks["direction_monotone"] = mono

    ranked = pd.read_csv(run / "ranked_universe.csv")
    wide = fv.pivot(index="security_id", columns="factor", values="score")
    comp = {}
    for sid, row in wide.iterrows():
        if row.notna().all():
            comp[sid] = math.fsum(row[f] * SPEC[f][0] for f in SPEC)
    rk = ranked.set_index("security_id")
    has = rk["composite"].notna()
    checks["composite_only_when_all_11"] = set(rk.index[has]) == set(comp)
    cdiff = [abs(comp[s] - rk.loc[s, "composite"]) for s in comp]
    checks["composite_recomputed_match"] = bool(not cdiff or max(cdiff) <= TOL)

    fam_ok = True
    for fam in ("QUALITY", "VALUATION", "GROWTH", "MOMENTUM", "RISK"):
        names = [f for f, v in SPEC.items() if v[2] == fam]
        fw = math.fsum(SPEC[f][0] for f in names)
        for sid in comp:
            e = math.fsum(wide.loc[sid, f] * SPEC[f][0] for f in names) / fw
            if abs(e - rk.loc[sid, fam.lower()]) > TOL:
                fam_ok = False
    checks["family_scores_match"] = fam_ok

    r = ranked.loc[ranked["rank"].notna()].copy()
    r["_liq"] = r["liquidity_63"].fillna(-np.inf)
    order = r.sort_values(["composite", "quality", "_liq", "security_id"],
                          ascending=[False, False, False, True], kind="stable")
    checks["rank_order_and_tiebreak"] = bool((order["rank"].to_numpy() == np.arange(1, len(order) + 1)).all())
    checks["ranks_contiguous"] = bool(sorted(r["rank"].astype(int)) == list(range(1, len(r) + 1)))

    top = run / "priority_queue_top10.csv"
    if top.exists():
        t10 = pd.read_csv(top)
        checks["top10_is_rank_1_to_10"] = list(t10["ticker"]) == list(order.head(10)["ticker"])

    dates_ok = True
    for col in ("max_filed_used", "period_end"):
        d = pd.to_datetime(ranked[col], errors="coerce").dropna()
        if (d > cutoff).any():
            dates_ok = False
            notes.append(f"{col} after cutoff")
    audit = pd.read_csv(run / "universe_audit.csv")
    lp = pd.to_datetime(audit["last_price_date"], errors="coerce").dropna()
    if (lp > cutoff).any():
        dates_ok = False
        notes.append("price dates after cutoff")
    checks["source_dates_le_cutoff"] = dates_ok
    checks["no_buy_state"] = not ranked["research_state"].astype(str).str.contains("BUY").any()
    return {"passed": all(checks.values()), "checks": checks, "notes": notes,
            "scored_rows_checked": int(both.sum()), "composites_checked": len(comp)}
