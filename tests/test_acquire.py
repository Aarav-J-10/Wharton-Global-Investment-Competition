"""acquire() wiring with every network call stubbed by SYNTHETIC fixture data."""
import json

import pandas as pd

from tests.synthetic import build_snapshot
from wic import snapshot as SN
from wic.pipeline import run_screen
from wic.snapshot import Snapshot


def test_acquire_wiring(tmp_path, monkeypatch):
    fixture, _ = build_snapshot(tmp_path / "fixture")
    fx = Snapshot(fixture)
    uni = fx.universe().rename(columns={"sector": "gics_sector"})
    sect = fx.sector_history()
    facts = fx.facts()
    prices = fx.prices()

    from wic.sources import prices as P
    from wic.sources import sec as S
    from wic.sources import universe as U

    class FakeWiki:
        def __init__(self, *a, **k):
            pass

        def snapshot(self, cutoff, out_dir):
            (out_dir / "raw").mkdir(parents=True, exist_ok=True)
            (out_dir / "raw" / "rev.json").write_text("{}")
            return uni.copy(), {"source": "fake", "revision_id": 1}

        def sector_history(self, start, end, out_dir):
            return sect.rename(columns={"sector": "gics_sector"}), [{"revision_id": 1}]

    monkeypatch.setattr(U, "WikipediaUniverse", FakeWiki)
    monkeypatch.setattr(U, "fetch_membership_history",
                        lambda session=None: (fx.membership_history(), {"source": "fake"}))
    monkeypatch.setenv("WIC_SEC_USER_AGENT", "Test test@example.com")
    monkeypatch.setattr(S, "fetch_ticker_map", lambda http: (
        uni[["ticker", "cik"]].assign(sec_name="x"), {"source": "fake"}))
    meta = pd.DataFrame({"cik": sorted(facts["cik"].unique()), "url": "u", "raw_sha256": "h", "entity_name": "e"})
    monkeypatch.setattr(S, "fetch_all_facts", lambda ciks, cache_dir=None: (facts, meta))
    from wic.sources import sec_filings as SF
    monkeypatch.setattr(SF, "supplement_issuer", lambda http, c, present, since, cache: (
        pd.DataFrame(columns=S.COLUMNS), [{"cik": c, "accn": "x", "status": "SUPPLEMENTED"}]))
    monkeypatch.setattr(P, "download_prices", lambda tickers, start, end: (
        prices[prices["ticker"].isin(tickers) & (prices["date"] <= end)], {"provider": "fake"}))

    snap = SN.acquire(pd.Timestamp("2026-10-16"), tmp_path / "data")
    assert SN.verify(snap) == []
    s = Snapshot(snap)
    assert s.cutoff == pd.Timestamp("2026-10-16")
    out = run_screen(snap, tmp_path / "out")
    assert json.loads((out / "STATUS.json").read_text())["status"] == "RANKING_PUBLISHED"


def test_last_completed_session():
    ny = "America/New_York"
    assert SN.last_completed_session(pd.Timestamp("2026-10-20 15:00", tz=ny).tz_convert("UTC")) == pd.Timestamp("2026-10-19")
    assert SN.last_completed_session(pd.Timestamp("2026-10-20 18:00", tz=ny).tz_convert("UTC")) == pd.Timestamp("2026-10-20")
    assert SN.last_completed_session(pd.Timestamp("2026-10-19 09:00", tz=ny).tz_convert("UTC")) == pd.Timestamp("2026-10-16")
