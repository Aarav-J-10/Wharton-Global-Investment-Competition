"""End-to-end checks on a SYNTHETIC snapshot (mechanics only, not research results)."""
import json
import shutil

import pandas as pd
import pytest

from tests.synthetic import build_snapshot
from wic.accounting.fundamentals import IssuerFacts
from wic.pipeline import run_screen
from wic.snapshot import Snapshot, seal, verify


@pytest.fixture(scope="module")
def snap(tmp_path_factory):
    path, truth = build_snapshot(tmp_path_factory.mktemp("data"))
    return path, truth


@pytest.fixture(scope="module")
def run(snap, tmp_path_factory):
    return run_screen(snap[0], tmp_path_factory.mktemp("out"))


def test_screen_publishes_and_validator_passes(run):
    status = json.loads((run / "STATUS.json").read_text())
    val = json.loads((run / "VALIDATION.json").read_text())
    assert status["status"] == "RANKING_PUBLISHED"
    assert val["passed"], val
    for f in ("run_manifest.json", "universe_audit.csv", "coverage_report.csv", "factor_dictionary.csv",
              "factor_values.csv", "ranked_universe.csv", "research_queue_top20.csv", "priority_queue_top10.csv",
              "sensitivity_results.csv", "factor_correlation.csv", "source_map.csv", "model_gate_memo.md",
              "lineage.jsonl", "diversified_research_view_top10.csv", "priority_queue_risk.json"):
        assert (run / f).exists(), f


def test_outputs_are_deterministic(snap, run, tmp_path):
    again = run_screen(snap[0], tmp_path)
    a = json.loads((run / "run_manifest.json").read_text())["outputs"]
    b = json.loads((again / "run_manifest.json").read_text())["outputs"]
    assert a == b


def test_excluded_sector_never_ranked(run):
    ranked = pd.read_csv(run / "ranked_universe.csv")
    audit = pd.read_csv(run / "universe_audit.csv")
    assert "Financials" not in set(ranked["sector"])
    assert (audit.loc[audit["sector"].eq("Financials"), "research_state"] == "OUTSIDE_STANDARD_MODEL").all()


def test_top10_has_no_buy_state(run):
    t = pd.read_csv(run / "priority_queue_top10.csv")
    assert set(t["research_state"]) == {"TOP10_PRIORITY"}
    assert list(t["rank"]) == list(range(1, 11))


def test_snapshot_tamper_is_detected(snap, tmp_path):
    copy = tmp_path / "s"
    shutil.copytree(snap[0], copy)
    p = copy / "universe.csv"
    p.write_text(p.read_text().replace("Synthetic", "Tampered", 1))
    assert verify(copy)
    with pytest.raises(RuntimeError):
        Snapshot(copy)


def test_failed_gate_removes_queues(snap, tmp_path):
    copy = tmp_path / "s"
    shutil.copytree(snap[0], copy)
    u = pd.read_csv(copy / "universe.csv")
    u.head(15).to_csv(copy / "universe.csv", index=False)  # too few names for any sector peer set
    seal(copy)
    out = run_screen(copy, tmp_path / "o")
    status = json.loads((out / "STATUS.json").read_text())
    assert status["status"] == "NO VALIDATED RANKING AVAILABLE"
    assert not (out / "priority_queue_top10.csv").exists()
    assert not (out / "priority_queue_risk.json").exists()


def test_no_lookahead_in_fundamentals(snap):
    s = Snapshot(snap[0])
    facts = s.facts()
    cik = int(facts["cik"].iloc[0])
    iss = IssuerFacts(cik, facts[facts["cik"].eq(cik)])
    asof = pd.Timestamp("2022-06-15")
    f = iss.fundamentals(asof)

    def walk(o):
        if isinstance(o, dict):
            if "filed" in o:
                assert pd.Timestamp(o["filed"]) <= asof
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    for q in f["q"].values():
        walk(q.lineage)
    assert f["period_end"] <= asof
