import math

import numpy as np
import pandas as pd
import pytest

from wic.config import (DIRECTIONS, FACTOR_NAMES, FAMILY_WEIGHTS, UNFAVORABLE, VALID, WEIGHTS,
                        family_weights_to_metric_weights)
from wic.scoring import diversified_view, score_universe


def frame(n=25, sectors=("A",), seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in sectors:
        for i in range(n):
            r = {"ticker": f"{s}{i:02d}", "sector": s, "security_id": f"{s}{i:02d}", "liquidity_63": 1e6 + i}
            for f in FACTOR_NAMES:
                r[f] = rng.normal()
                r[f"{f}_status"] = VALID
            rows.append(r)
    return pd.DataFrame(rows)


def test_weights_and_families():
    assert math.isclose(sum(WEIGHTS.values()), 1.0)
    assert {k: round(v, 10) for k, v in FAMILY_WEIGHTS.items()} == {
        "QUALITY": .3, "VALUATION": .2, "GROWTH": .2, "MOMENTUM": .2, "RISK": .1}


@pytest.mark.parametrize("factor", FACTOR_NAMES)
def test_direction_better_raw_gets_higher_score(factor):
    """Spec 12.2 non-negotiable direction tests, one per factor."""
    df = frame()
    better, worse = df.index[0], df.index[1]
    d = DIRECTIONS[factor]
    df.loc[better, factor] = 10.0 * d
    df.loc[worse, factor] = -10.0 * d
    out = score_universe(df).set_index("ticker")
    assert out.loc[df.loc[better, "ticker"], f"{factor}_score"] > out.loc[df.loc[worse, "ticker"], f"{factor}_score"]


def test_percentile_formula_and_winsorization():
    df = frame(n=20)
    df["roic"] = np.arange(20, dtype=float)
    df.loc[19, "roic"] = 1e9  # outlier gets clipped, but rank is unchanged
    out = score_universe(df).set_index("security_id")
    expected = 100 * (np.arange(1, 21) - 0.5) / 20
    got = out.loc[df["security_id"], "roic_score"].to_numpy()
    assert np.allclose(got, expected)
    # lower-is-better metric reverses
    df["ev_ebit"] = np.arange(20, dtype=float)
    out = score_universe(df).set_index("security_id")
    assert np.allclose(out.loc[df["security_id"], "ev_ebit_score"].to_numpy(), 100 - expected)


def test_ties_receive_midranks():
    df = frame(n=20)
    df["fcf_margin"] = 1.0
    out = score_universe(df)
    assert np.allclose(out["fcf_margin_score"], 50.0)


def test_peer_minimum_blocks_sector_metric():
    df = frame(n=19)
    out = score_universe(df, min_peers=20)
    assert out["composite"].isna().all()
    assert (out["roic_score_status"] == "PEER_SET_INSUFFICIENT").all()
    assert out["rank"].isna().all()


def test_sentinel_scores_zero_and_is_not_a_peer():
    df = frame(n=21)
    df.loc[0, "ev_ebit"] = None
    df.loc[0, "ev_ebit_status"] = UNFAVORABLE
    out = score_universe(df).set_index("security_id")
    assert out.loc[df.loc[0, "security_id"], "ev_ebit_score"] == 0.0
    assert (out["ev_ebit_peers"] == 20).all()
    assert out.loc[df.loc[0, "security_id"], "composite"] == out.loc[df.loc[0, "security_id"], "composite"]


def test_missing_factor_blocks_composite_without_renormalization():
    df = frame(n=21)
    df.loc[3, "eps_cagr_3y"] = None
    df.loc[3, "eps_cagr_3y_status"] = "INSUFFICIENT_ANNUAL_HISTORY"
    out = score_universe(df).set_index("security_id")
    sid = df.loc[3, "security_id"]
    assert np.isnan(out.loc[sid, "composite"])
    assert pd.isna(out.loc[sid, "rank"])
    assert out.loc[sid, "complete_factors"] == 10
    assert np.isnan(out.loc[sid, "growth"])
    assert not np.isnan(out.loc[sid, "quality"])


def test_composite_is_weighted_sum_and_sorted():
    out = score_universe(frame(n=30, sectors=("A", "B")))
    s = out[[f"{f}_score" for f in FACTOR_NAMES]].to_numpy()
    w = np.array([WEIGHTS[f] for f in FACTOR_NAMES])
    assert np.allclose(out["composite"], s @ w)
    assert list(out["rank"]) == list(range(1, 61))
    assert out["composite"].is_monotonic_decreasing


def test_tie_break_quality_then_liquidity_then_id():
    df = frame(n=20)
    for f in FACTOR_NAMES:
        df[f] = 1.0  # everybody tied on every metric
    out = score_universe(df)
    assert list(out["security_id"]) == list(df.sort_values("liquidity_63", ascending=False)["security_id"])


def test_sectors_scored_independently():
    df = frame(n=20, sectors=("A", "B"))
    df.loc[df["sector"].eq("B"), "roic"] += 100
    out = score_universe(df)
    assert np.isclose(out.groupby("sector")["roic_score"].mean(), 50).all()


def test_family_reweight_preserves_within_family_ratios():
    fw = {"QUALITY": .4, "VALUATION": .15, "GROWTH": .15, "MOMENTUM": .15, "RISK": .15}
    w = family_weights_to_metric_weights(fw)
    assert math.isclose(sum(w.values()), 1.0)
    assert math.isclose(w["roic"] / w["fcf_margin"], .12 / .10)
    assert math.isclose(w["momentum_12_1"] + w["momentum_6_1"], .15)


def test_diversified_view_caps_sector():
    out = score_universe(frame(n=20, sectors=("A", "B", "C", "D")))
    out.loc[out["sector"].eq("A"), "rank"] = range(1, 21)
    out.loc[out["sector"].ne("A"), "rank"] = range(21, 81)
    dv = diversified_view(out, 10, 3)
    assert len(dv) == 10
    assert (dv["sector"] == "A").sum() == 3
    assert not dv["sector_cap_exception"].any()


def test_diversified_view_flags_unavoidable_cap_exception():
    out = score_universe(frame(n=20, sectors=("A", "B", "C")))
    dv = diversified_view(out, 10, 3)
    assert len(dv) == 10 and dv["sector_cap_exception"].sum() == 1
