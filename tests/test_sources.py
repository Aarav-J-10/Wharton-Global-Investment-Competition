"""Source adapters parsed against fixed payloads (no network)."""
import pandas as pd

from wic.sources import prices as P
from wic.sources.sec import extract_facts
from wic.sources.universe import members_on, parse_constituents_html, yahoo_symbol

HTML = """<table id="constituents"><tr><th>Symbol</th><th>Security</th><th>GICS Sector</th>
<th>GICS Sub-Industry</th><th>Headquarters Location</th><th>Date added</th><th>CIK</th><th>Founded</th></tr>
""" + "".join(f"<tr><td>T{i}{'.B' if i == 0 else ''}</td><td>Co {i}</td><td>Industrials</td><td>X</td><td>Y</td>"
              f"<td>2000-01-01</td><td>{1000 + i}</td><td>1900</td></tr>" for i in range(320)) + "</table>"


def test_parse_constituents():
    df = parse_constituents_html(HTML)
    assert len(df) == 320
    assert df.loc[0, "ticker"] == "T0.B" and df.loc[0, "yahoo_ticker"] == "T0-B"
    assert df["cik"].dtype.name == "Int64" and df.loc[5, "cik"] == 1005


def test_yahoo_symbol():
    assert yahoo_symbol("brk.b") == "BRK-B"


def test_members_on_uses_latest_row_not_after_date():
    h = pd.DataFrame({"date": pd.to_datetime(["2020-01-01", "2020-06-01"]), "tickers": ["A,B", "A,C"]})
    assert members_on(h, pd.Timestamp("2020-05-31")) == ["A", "B"]
    assert members_on(h, pd.Timestamp("2020-06-01")) == ["A", "C"]
    assert members_on(h, pd.Timestamp("2019-12-31")) == []


def test_extract_facts_keeps_pit_versions_and_filters():
    def f(val, filed, form="10-K", accn="a"):
        return {"start": "2024-01-01", "end": "2024-12-31", "val": val, "accn": accn, "fy": 2024, "fp": "FY",
                "form": form, "filed": filed}
    payload = {"facts": {
        "us-gaap": {
            "Revenues": {"units": {"USD": [f(100, "2025-02-01"), f(100, "2026-02-01", accn="b"),
                                           f(90, "2026-03-01", "10-K/A", "c"), f(5, "2025-02-01", "8-K")]}},
            "SomethingElse": {"units": {"USD": [f(1, "2025-02-01")]}}},
        "dei": {"EntityCommonStockSharesOutstanding": {"units": {"shares": [
            {"end": "2025-01-20", "val": 7, "accn": "a", "fy": 2024, "fp": "FY", "form": "10-K", "filed": "2025-02-01"}]}}}}}
    df = extract_facts(payload, 42)
    rev = df[df["concept"].eq("Revenues")].sort_values("filed")
    # duplicate re-report (same value) dropped, restatement kept, 8-K ignored
    assert list(rev["val"]) == [100, 90]
    assert set(df["concept"]) == {"Revenues", "dei:EntityCommonStockSharesOutstanding"}
    assert pd.isna(df.loc[df["concept"].str.startswith("dei"), "start"]).all()


def test_yfinance_frame_normalization(monkeypatch):
    idx = pd.DatetimeIndex(pd.bdate_range("2025-01-01", periods=3), name="Date")
    cols = pd.MultiIndex.from_product([["AAA", "BBB"], ["Open", "High", "Low", "Close", "Adj Close", "Volume",
                                                        "Dividends", "Stock Splits"]])
    data = pd.DataFrame(1.0, index=idx, columns=cols)
    data[("BBB", "Close")] = float("nan")
    data[("BBB", "Adj Close")] = float("nan")

    class FakeYF:
        @staticmethod
        def download(*a, **k):
            return data
    import sys
    monkeypatch.setitem(sys.modules, "yfinance", FakeYF)
    out = P._download_batch(["AAA", "BBB"], "2025-01-01", pd.Timestamp("2025-01-10"))
    assert set(out["ticker"]) == {"AAA"}
    assert list(out.columns) == ["date", "ticker", *P.FIELDS]
    assert out["date"].dtype.kind == "M"
