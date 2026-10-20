import numpy as np
import pandas as pd
import pytest

from wic.accounting.fundamentals import IssuerFacts, View, _prep, annual_series, debt_at, flow_ttm, instant

T = pd.Timestamp


def fact(concept, start, end, val, filed, form="10-Q", accn=None, unit="USD"):
    return dict(cik=1, concept=concept, unit=unit, start=T(start) if start else pd.NaT, end=T(end), val=float(val),
                accn=accn or f"a-{filed}", fy=None, fp=None, form=form, filed=T(filed))


def view(rows, asof="2030-01-01"):
    return View(_prep(pd.DataFrame(rows)), T(asof))


def test_ttm_ytd_bridge():
    rows = [fact("Revenues", "2024-01-01", "2024-12-31", 400, "2025-02-20", "10-K"),
            fact("Revenues", "2025-01-01", "2025-06-30", 230, "2025-08-01"),
            fact("Revenues", "2024-01-01", "2024-06-30", 190, "2025-08-01")]
    q = flow_ttm(view(rows), ("Revenues",), T("2025-06-30"))
    assert q.ok and q.value == pytest.approx(440) and q.lineage["method"] == "YTD_BRIDGE"


def test_ttm_prefers_fiscal_year_value():
    rows = [fact("Revenues", "2024-01-01", "2024-12-31", 400, "2025-02-20", "10-K")]
    q = flow_ttm(view(rows), ("Revenues",), T("2024-12-31"))
    assert q.value == 400 and q.lineage["method"] == "FY"


def test_ttm_four_quarters_with_derived_q4():
    rows = [fact("X", "2024-01-01", "2024-12-31", 100, "2025-02-01", "10-K"),
            fact("X", "2024-01-01", "2024-09-30", 70, "2024-11-01"),
            fact("X", "2025-01-01", "2025-03-31", 30, "2025-05-01"),
            fact("X", "2025-04-01", "2025-06-30", 35, "2025-08-01"),
            fact("X", "2024-07-01", "2024-09-30", 25, "2024-11-01")]
    q = flow_ttm(view(rows), ("X",), T("2025-06-30"))
    # Q3'24 25 + Q4'24 (100-70) 30 + Q1 30 + Q2 35
    assert q.ok and q.value == pytest.approx(120) and q.lineage["method"] == "FOUR_QUARTERS"


def test_ttm_never_sums_incompatible_ytd():
    rows = [fact("X", "2025-01-01", "2025-06-30", 50, "2025-08-01")]
    assert not flow_ttm(view(rows), ("X",), T("2025-06-30")).ok


def test_point_in_time_restatement_invisible_before_filing():
    rows = [fact("Revenues", "2024-01-01", "2024-12-31", 400, "2025-02-20", "10-K", "a1"),
            fact("Revenues", "2024-01-01", "2024-12-31", 380, "2025-06-01", "10-K/A", "a2")]
    assert flow_ttm(view(rows, "2025-03-01"), ("Revenues",), T("2024-12-31")).value == 400
    assert flow_ttm(view(rows, "2025-07-01"), ("Revenues",), T("2024-12-31")).value == 380


def test_annual_series_requires_four_spaced_years():
    rows = [fact("Revenues", f"{y}-01-01", f"{y}-12-31", 100 + y, f"{y + 1}-02-20", "10-K") for y in (2021, 2022, 2024)]
    hist, status = annual_series(view(rows), ("Revenues",), 4)
    assert status == "INSUFFICIENT_ANNUAL_HISTORY"
    rows.append(fact("Revenues", "2023-01-01", "2023-12-31", 1, "2024-02-20", "10-K"))
    hist, status = annual_series(view(rows), ("Revenues",), 4)
    assert status == "VALID" and [h[0].year for h in hist] == [2024, 2023, 2022, 2021]


def test_debt_routes_and_no_double_count():
    D = "2025-06-30"
    rows = [fact("LongTermDebtNoncurrent", None, D, 900, "2025-08-01"),
            fact("LongTermDebtCurrent", None, D, 100, "2025-08-01"),
            fact("ShortTermBorrowings", None, D, 50, "2025-08-01"),
            fact("CommercialPaper", None, D, 50, "2025-08-01")]  # CP assumed inside short-term borrowings
    q = debt_at(view(rows), T(D))
    assert q.value == 1050 and q.lineage["route"] == "NONCURRENT+COMPONENTS"
    rows.append(fact("DebtCurrent", None, D, 150, "2025-08-01"))
    assert debt_at(view(rows), T(D)).value == 1050
    rows.append(fact("DebtAndCapitalLeaseObligations", None, D, 1070, "2025-08-01"))
    assert debt_at(view(rows), T(D)).value == 1070


def test_zero_debt_only_without_recent_tags():
    D = "2025-06-30"
    rows = [fact("StockholdersEquity", None, D, 10, "2025-08-01")]
    q = debt_at(view(rows), T(D))
    assert q.value == 0.0 and q.lineage["flag"] == "DEBT_ZERO_INFERRED"
    rows.append(fact("LongTermDebtNoncurrent", None, "2024-12-31", 500, "2025-02-01", "10-K"))
    assert debt_at(view(rows), T(D)).status == "DEBT_COMPONENT_MISSING"


def test_instant_requires_matching_date():
    rows = [fact("CashAndCashEquivalentsAtCarryingValue", None, "2025-03-31", 5, "2025-05-01")]
    assert not instant(view(rows), ("CashAndCashEquivalentsAtCarryingValue",), T("2025-06-30")).ok


def test_split_adjusted_shares_and_eps():
    rows = [fact("dei:EntityCommonStockSharesOutstanding", None, "2020-01-25", 100, "2020-02-01", "10-K", unit="shares"),
            fact("WeightedAverageNumberOfDilutedSharesOutstanding", "2019-10-01", "2019-12-31", 100, "2020-02-01",
                 "10-K", unit="shares"),
            fact("NetCashProvidedByUsedInOperatingActivities", "2019-01-01", "2019-12-31", 1, "2020-02-01", "10-K")]
    for y, e in zip(range(2016, 2020), (1.0, 1.2, 1.4, 1.6)):
        rows.append(fact("EarningsPerShareDiluted", f"{y}-01-01", f"{y}-12-31", e, f"{y + 1}-02-01", "10-K",
                         unit="USD/shares"))
    splits = pd.DataFrame({"date": [T("2020-08-31")], "splits": [4.0]})
    iss = IssuerFacts(1, pd.DataFrame(rows), splits)
    f = iss.fundamentals(T("2020-03-01"))
    assert f["q"]["shares"].value == pytest.approx(400)
    assert [round(v, 3) for _, v, _ in f["eps_hist"]] == [0.4, 0.35, 0.3, 0.25]


def test_fundamentals_ignore_future_filings():
    rows = [fact("NetCashProvidedByUsedInOperatingActivities", "2024-01-01", "2024-12-31", 10, "2025-02-20", "10-K"),
            fact("NetCashProvidedByUsedInOperatingActivities", "2025-01-01", "2025-03-31", 3, "2025-05-01")]
    iss = IssuerFacts(1, pd.DataFrame(rows))
    assert iss.fundamentals(T("2025-04-30"))["period_end"] == T("2024-12-31")
    assert iss.fundamentals(T("2025-05-01"))["period_end"] == T("2025-03-31")
