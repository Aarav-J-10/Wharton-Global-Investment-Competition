import math

import numpy as np
import pandas as pd
import pytest

from wic.config import UNFAVORABLE, VALID, load_config
from wic.factors import PriceSeries, compute_factors, market_block


def series(adj, start="2024-01-01", close=None, volume=1e6):
    dates = pd.bdate_range(start, periods=len(adj))
    return PriceSeries(pd.DataFrame({"date": dates, "close": close if close is not None else adj, "adj_close": adj,
                                     "volume": volume, "dividends": 0.0, "splits": 0.0}))


def test_momentum_skips_last_month_and_uses_total_return():
    adj = np.linspace(100, 200, 300)
    ps = series(adj)
    asof = pd.Timestamp(ps.dates[-1])
    m = market_block(ps, asof, asof)
    i = len(adj) - 1
    assert m["momentum_12_1"] == pytest.approx(adj[i - 21] / adj[i - 252] - 1)
    assert m["momentum_6_1"] == pytest.approx(adj[i - 21] / adj[i - 126] - 1)


def test_volatility_and_drawdown():
    rng = np.random.default_rng(1)
    r = rng.normal(0, 0.01, 299)
    adj = 100 * np.concatenate([[1], np.cumprod(1 + r)])
    ps = series(adj)
    asof = pd.Timestamp(ps.dates[-1])
    m = market_block(ps, asof, asof)
    w = adj[-253:]
    assert m["volatility_252"] == pytest.approx(np.std(w[1:] / w[:-1] - 1, ddof=1) * math.sqrt(252))
    assert m["max_drawdown_252"] == pytest.approx(np.max(1 - w / np.maximum.accumulate(w)))
    assert m["max_drawdown_252"] >= 0


def test_insufficient_history_and_stale_price():
    ps = series(np.linspace(1, 2, 200))
    asof = pd.Timestamp(ps.dates[-1])
    assert market_block(ps, asof, asof)["price_status"] == "INSUFFICIENT_PRICE_HISTORY"
    assert market_block(ps, asof, asof + pd.Timedelta(days=3))["price_status"] == "STALE_PRICE"


def test_raw_close_reconstructed_from_splits():
    adj = np.full(300, 50.0)
    dates = pd.bdate_range("2024-01-01", periods=300)
    df = pd.DataFrame({"date": dates, "close": adj, "adj_close": adj, "volume": 1.0, "dividends": 0.0, "splits": 0.0})
    df.loc[250, "splits"] = 2.0
    ps = PriceSeries(df)
    m = market_block(ps, dates[100], dates[100])
    assert m["raw_close"] == pytest.approx(100.0)


class Qv:
    def __init__(self, v, status="VALID", lineage=None):
        self.value, self.status, self.lineage = v, status, lineage or {}

    @property
    def ok(self):
        return self.value is not None and self.status == "VALID"


def fund(**over):
    base = dict(revenue=1000, ebit=200, da=50, cfo=250, capex=60, interest=10, pretax=190, tax=40, cash=100,
                debt=500, equity=800, nci=0, preferred=0, liabilities=2000, shares=100, tax_rate=0.21,
                debt_prior=450, cash_prior=80, equity_prior=750, nci_prior=0, preferred_prior=0)
    base.update(over)
    q = {k: (v if isinstance(v, Qv) else Qv(v)) for k, v in base.items()}
    E = pd.Timestamp("2026-06-30")
    hist = [(E - pd.DateOffset(years=k), v, {}) for k, v in enumerate((1331, 1210, 1100, 1000))]
    eps = [(E - pd.DateOffset(years=k), v, {}) for k, v in enumerate((2.0, 1.5, 1.2, 1.0))]
    return {"status": "OK", "period_end": E, "q": q, "rev_hist": hist, "rev_hist_status": VALID,
            "eps_hist": eps, "eps_hist_status": VALID, "fcf_annual_last3": [1, 1, 1]}


MKT = {"price_status": "OK", "close": 20.0, "momentum_12_1": .1, "momentum_6_1": .05, "volatility_252": .2,
       "max_drawdown_252": .1}
CFG = load_config()
ASOF = pd.Timestamp("2026-10-15")


def test_factor_formulas():
    f, inter = compute_factors(fund(), MKT, ASOF, CFG)
    ic, icp = 500 + 800 - 100, 450 + 750 - 80
    assert f["roic"]["value"] == pytest.approx(200 * 0.79 / ((ic + icp) / 2))
    assert f["fcf_margin"]["value"] == pytest.approx(190 / 1000)
    assert f["net_debt_ebitda"]["value"] == pytest.approx(400 / 250)
    assert f["fcf_yield"]["value"] == pytest.approx(190 / 2000)
    assert f["ev_ebit"]["value"] == pytest.approx((2000 + 500 - 100) / 200)
    assert f["revenue_cagr_3y"]["value"] == pytest.approx(0.1)
    assert f["eps_cagr_3y"]["value"] == pytest.approx(2 ** (1 / 3) - 1)
    assert all(v["status"] == VALID for v in f.values())


def test_economic_sentinels():
    f, _ = compute_factors(fund(ebit=-10, da=5), MKT, ASOF, CFG)
    assert f["ev_ebit"]["status"] == UNFAVORABLE
    assert f["net_debt_ebitda"]["status"] == UNFAVORABLE
    assert f["roic"]["status"] == VALID and f["roic"]["value"] < 0  # loss: NOPAT = EBIT, no tax shield
    fu = fund()
    fu["eps_hist"][3] = (fu["eps_hist"][3][0], -1.0, {})
    f, _ = compute_factors(fu, MKT, ASOF, CFG)
    assert f["eps_cagr_3y"]["status"] == UNFAVORABLE and f["eps_cagr_3y"]["value"] is None


def test_missing_is_not_zero_and_not_sentinel():
    f, _ = compute_factors(fund(capex=Qv(None, "TTM_INCOMPLETE")), MKT, ASOF, CFG)
    assert f["fcf_margin"]["status"] == "TTM_INCOMPLETE" and f["fcf_margin"]["value"] is None
    assert f["fcf_yield"]["status"] == "TTM_INCOMPLETE"


def test_negative_fcf_is_valid_unfavorable_value():
    f, _ = compute_factors(fund(cfo=10, capex=60), MKT, ASOF, CFG)
    assert f["fcf_margin"]["status"] == VALID and f["fcf_margin"]["value"] < 0


def test_stale_fundamentals_blocked():
    f, _ = compute_factors(fund(), MKT, pd.Timestamp("2027-06-30"), CFG)
    assert f["roic"]["status"] == "STALE_INPUT"
