"""Point-in-time accounting normalization from SEC companyfacts.

`IssuerFacts.fundamentals(asof)` uses only facts whose SEC filing date is on
or before `asof` and returns canonical quantities (spec section 10) with:
  * a status per quantity (VALID or an explicit missing reason), and
  * lineage: concept, route, accession and filing date of every input.

Engineering conventions (logged in docs/MODEL_CHANGE_LOG.md):
  * TTM = FY value when the latest period is a fiscal year end, else
    fiscal-YTD + prior FY - prior-year YTD (same duration), else the sum of
    four contiguous discrete quarters. Never Q1+H1+9M+FY.
  * Restatements: the latest version filed on or before `asof` is used.
  * Debt = interest-bearing borrowings as tagged by the issuer (finance-lease
    liabilities included only where the issuer's own debt tag includes them,
    so leases are never counted twice; operating leases excluded).
  * Debt is inferred to be zero only if the issuer tags no borrowing concept
    at the balance-sheet date AND tagged none in the prior two years.
  * Preferred / NCI claims are taken from their tags; if the issuer reports no
    such balance they are zero and flagged *_NOT_REPORTED.
  * Effective tax = TTM tax / TTM pretax when pretax > 0 and 0 <= rate <= 50%,
    else 3-fiscal-year aggregate under the same bounds, else ROIC blocked.
  * Share counts and EPS are restated to the price data's split basis using
    split events dated after the filing date.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import concepts as C

DAY = pd.Timedelta(days=1)
FY_DUR = (350, 380)
Q_DUR = (80, 100)
YTD_DUR = (80, 290)


@dataclass
class Q:
    """A resolved quantity: value or None with an explicit status/reason."""
    value: float | None
    status: str = "VALID"
    lineage: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.value is not None and self.status == "VALID" and math.isfinite(self.value)


def _missing(reason: str, **lineage) -> Q:
    return Q(None, reason, lineage)


class FA:
    """Column arrays for one concept (numpy; far cheaper than DataFrame slicing)."""
    __slots__ = ("start", "end", "val", "filed", "dur", "accn", "form")

    def __init__(self, start, end, val, filed, dur, accn, form):
        self.start, self.end, self.val, self.filed = start, end, val, filed
        self.dur, self.accn, self.form = dur, accn, form

    @classmethod
    def from_frame(cls, df: pd.DataFrame) -> "FA":
        return cls(df["start"].to_numpy("datetime64[ns]"), df["end"].to_numpy("datetime64[ns]"),
                   df["val"].to_numpy(float), df["filed"].to_numpy("datetime64[ns]"), df["dur"].to_numpy(float),
                   df["accn"].to_numpy(object), df["form"].to_numpy(object))

    def __len__(self):
        return len(self.val)

    def sel(self, mask) -> "FA":
        return FA(*(getattr(self, k)[mask] for k in self.__slots__))

    @property
    def is_instant(self) -> np.ndarray:
        return np.isnat(self.start)

    def row(self, i: int) -> dict:
        st = self.start[i]
        return {"start": None if np.isnat(st) else pd.Timestamp(st), "end": pd.Timestamp(self.end[i]),
                "val": float(self.val[i]), "filed": pd.Timestamp(self.filed[i]), "dur": self.dur[i],
                "accn": self.accn[i], "form": self.form[i]}


class View:
    """Facts visible at `asof` (latest version per period)."""

    def __init__(self, by_concept: dict[str, FA], asof: pd.Timestamp):
        self.asof = np.datetime64(asof, "ns")
        self._src = by_concept
        self._cache: dict[str, FA | None] = {}

    def get(self, concept: str) -> FA | None:
        if concept in self._cache:
            return self._cache[concept]
        fa = self._src.get(concept)
        if fa is not None:
            n = int(np.searchsorted(fa.filed, self.asof, side="right"))  # sorted by filed
            if n == 0:
                fa = None
            else:
                fa = fa.sel(slice(0, n))
                # keep the latest-filed version per (start, end)
                st = np.where(np.isnat(fa.start), np.int64(-1), fa.start.astype("int64"))
                key = np.stack([st, fa.end.astype("int64")], axis=1)
                _, first_rev = np.unique(key[::-1], axis=0, return_index=True)
                keep = np.sort(len(key) - 1 - first_rev)
                fa = fa.sel(keep)
        self._cache[concept] = fa
        return fa


def _lin(row: dict, concept, route, **extra) -> dict:
    d = {"concept": concept, "route": route, "accn": row["accn"], "filed": row["filed"].date().isoformat(),
         "end": row["end"].date().isoformat(), "form": row["form"]}
    if row.get("start") is not None:
        d["start"] = row["start"].date().isoformat()
    d.update(extra)
    return d


def _near(arr: np.ndarray, target, tol_days: int) -> np.ndarray:
    delta = (arr - np.datetime64(pd.Timestamp(target), "ns")).astype("timedelta64[D]").astype(np.int64)
    return np.abs(delta) <= tol_days


# ----------------------------------------------------------------------------
# Flows
# ----------------------------------------------------------------------------

def _last(fa: FA, mask) -> dict | None:
    idx = np.flatnonzero(mask)
    return fa.row(idx[-1]) if len(idx) else None


def _ttm_one(fa: FA, E: pd.Timestamp, concept: str) -> Q:
    dur = fa.dur
    has_start = ~fa.is_instant
    at_end = _near(fa.end, E, 3) & has_start
    is_fy = (dur >= FY_DUR[0]) & (dur <= FY_DUR[1])
    r = _last(fa, at_end & is_fy)
    if r:
        return Q(r["val"], "VALID", {"inputs": [_lin(r, concept, "FY")], "method": "FY"})
    ytd_idx = np.flatnonzero(at_end & (dur >= YTD_DUR[0]) & (dur <= YTD_DUR[1]))
    ytd_idx = ytd_idx[np.argsort(-dur[ytd_idx], kind="stable")]
    prior_end = E - pd.DateOffset(years=1)
    for i in ytd_idx:
        y = fa.row(i)
        pfy = _last(fa, is_fy & _near(fa.end, y["start"] - DAY, 7))
        if pfy is None:
            continue
        pytd = _last(fa, _near(fa.end, prior_end, 10) & (np.abs(dur - y["dur"]) <= 10) & has_start)
        if pytd is None:
            continue
        val = y["val"] + pfy["val"] - pytd["val"]
        return Q(val, "VALID", {"method": "YTD_BRIDGE", "inputs": [
            _lin(y, concept, "YTD"), _lin(pfy, concept, "PRIOR_FY"), _lin(pytd, concept, "PRIOR_YTD")]})
    # Four contiguous discrete quarters (Q4 may be derived as FY - 9M).
    quarters = []
    end = E
    is_q = (dur >= Q_DUR[0]) & (dur <= Q_DUR[1])
    for _ in range(4):
        r = _last(fa, _near(fa.end, end, 3) & is_q)
        if r:
            quarters.append((r["val"], _lin(r, concept, "Q")))
            end = r["start"] - DAY
            continue
        f = _last(fa, is_fy & _near(fa.end, end, 3))
        if f:
            nine = _last(fa, _near(fa.end, end - pd.DateOffset(months=3), 10) & (dur >= 260) & (dur <= 285)
                         & has_start & _near(np.where(has_start, fa.start, fa.end), f["start"], 7))
            if nine:
                quarters.append((f["val"] - nine["val"],
                                 {"derived": "FY-9M", "inputs": [_lin(f, concept, "FY"), _lin(nine, concept, "9M")]}))
                end = nine["end"]
                continue
        break
    if len(quarters) == 4:
        return Q(math.fsum(v for v, _ in quarters), "VALID",
                 {"method": "FOUR_QUARTERS", "inputs": [l for _, l in quarters]})
    return _missing("TTM_INCOMPLETE", concept=concept, period_end=E.date().isoformat())


def flow_ttm(view: View, concepts: tuple, E: pd.Timestamp) -> Q:
    reason = None
    for c in concepts:
        fa = view.get(c)
        if fa is None:
            continue
        q = _ttm_one(fa, E, c)
        if q.ok:
            return q
        reason = reason or q
    return reason or _missing("CONCEPT_NOT_REPORTED", concepts=list(concepts))


def annual_series(view: View, concepts: tuple, n: int = 4) -> tuple[list[tuple[pd.Timestamp, float, dict]], str]:
    """Latest n fiscal-year values, one per FY end, ~1 year apart."""
    by_end: dict[pd.Timestamp, tuple[float, dict]] = {}
    for c in concepts:
        fa = view.get(c)
        if fa is None:
            continue
        for i in np.flatnonzero((fa.dur >= FY_DUR[0]) & (fa.dur <= FY_DUR[1])):
            r = fa.row(i)
            e = r["end"]
            if not any(abs((e - k).days) <= 7 for k in by_end):
                by_end[e] = (r["val"], _lin(r, c, "FY"))
    if not by_end:
        return [], "CONCEPT_NOT_REPORTED"
    ends = sorted(by_end, reverse=True)
    out = [(ends[0], *by_end[ends[0]])]
    for k in range(1, n):
        target = ends[0] - pd.DateOffset(years=k)
        hit = [e for e in ends if abs((e - target).days) <= 20]
        if not hit:
            return out, "INSUFFICIENT_ANNUAL_HISTORY"
        out.append((hit[0], *by_end[hit[0]]))
    return out, "VALID"


# ----------------------------------------------------------------------------
# Instants
# ----------------------------------------------------------------------------

def instant(view: View, concepts: tuple, D: pd.Timestamp, tol: int = 3) -> Q:
    for c in concepts:
        fa = view.get(c)
        if fa is None:
            continue
        r = _last(fa, fa.is_instant & _near(fa.end, D, tol))
        if r:
            return Q(r["val"], "VALID", {"inputs": [_lin(r, c, "INSTANT")]})
    return _missing("NOT_REPORTED_AT_DATE", concepts=list(concepts), date=D.date().isoformat())


def _sum_present(view, D, groups) -> tuple[float, list, int]:
    total, lin, n = 0.0, [], 0
    for g in groups:
        q = instant(view, g, D)
        if q.ok:
            total += q.value
            lin += q.lineage["inputs"]
            n += 1
    return total, lin, n


def debt_at(view: View, D: pd.Timestamp) -> Q:
    tot = instant(view, C.DEBT_TOTAL, D)
    if tot.ok:
        return Q(tot.value, "VALID", {"route": "TOTAL_TAG", **tot.lineage})
    st_borrow = (C.SHORT_TERM[0],) if instant(view, (C.SHORT_TERM[0],), D).ok else (C.SHORT_TERM[1],)
    nc = instant(view, C.DEBT_NONCURRENT, D)
    if nc.ok:
        cur = instant(view, C.DEBT_CURRENT_TOTAL, D)
        if cur.ok:
            return Q(nc.value + cur.value, "VALID", {"route": "NONCURRENT+CURRENT_TOTAL",
                                                     "inputs": nc.lineage["inputs"] + cur.lineage["inputs"]})
        extra, lin, n = _sum_present(view, D, [C.LTD_CURRENT, st_borrow])
        return Q(nc.value + extra, "VALID", {"route": "NONCURRENT+COMPONENTS",
                                             "current_components_found": n,
                                             "inputs": nc.lineage["inputs"] + lin})
    ltd = instant(view, C.LTD_INCL_CURRENT, D)
    if ltd.ok:
        extra, lin, n = _sum_present(view, D, [st_borrow])
        return Q(ltd.value + extra, "VALID", {"route": "LTD_INCL_CURRENT+SHORT_TERM",
                                              "inputs": ltd.lineage["inputs"] + lin})
    cur = instant(view, C.DEBT_CURRENT_TOTAL, D)
    other, lin, n = _sum_present(view, D, [(c,) for c in C.OTHER_DEBT[:3]] + [st_borrow, C.LTD_CURRENT])
    if cur.ok or n:
        v = (cur.value if cur.ok else 0.0) + other
        return Q(v, "VALID", {"route": "OTHER_DEBT_COMPONENTS",
                              "inputs": (cur.lineage["inputs"] if cur.ok else []) + lin})
    # Zero only when the issuer has not tagged borrowings at all for two years.
    recent = False
    for c in C.DEBT_ALL:
        fa = view.get(c)
        if fa is not None and np.any((fa.end >= np.datetime64(D - pd.DateOffset(years=2), "ns")) & (fa.val != 0)):
            recent = True
            break
    if recent:
        return _missing("DEBT_COMPONENT_MISSING", date=D.date().isoformat())
    return Q(0.0, "VALID", {"route": "NO_BORROWINGS_TAGGED_2Y", "flag": "DEBT_ZERO_INFERRED"})


def equity_claims_at(view: View, D: pd.Timestamp) -> dict[str, Q]:
    parent = instant(view, C.EQUITY_PARENT, D)
    total = instant(view, C.EQUITY_TOTAL, D)
    nci = instant(view, C.NCI, D)
    if not parent.ok and total.ok and nci.ok:
        parent = Q(total.value - nci.value, "VALID", {"route": "TOTAL_MINUS_NCI",
                                                      "inputs": total.lineage["inputs"] + nci.lineage["inputs"]})
    if not parent.ok and total.ok and not nci.ok:
        parent = Q(total.value, "VALID", {"route": "TOTAL_NO_NCI", **total.lineage})
    if not nci.ok:
        if parent.ok and total.ok:
            nci = Q(total.value - parent.value, "VALID", {"route": "TOTAL_MINUS_PARENT"})
        else:
            nci = Q(0.0, "VALID", {"route": "NOT_REPORTED", "flag": "NCI_NOT_REPORTED"})
    pref = instant(view, C.PREFERRED, D)
    if not pref.ok:
        pref = Q(0.0, "VALID", {"route": "NOT_REPORTED", "flag": "PREFERRED_NOT_REPORTED"})
    return {"equity": parent, "nci": nci, "preferred": pref}


# ----------------------------------------------------------------------------
# Issuer
# ----------------------------------------------------------------------------

def _prep(facts: pd.DataFrame) -> dict[str, FA]:
    f = facts[["concept", "start", "end", "val", "filed", "accn", "form"]].copy()
    f["dur"] = ((f["end"] - f["start"]).dt.days + 1).astype("float")
    f = f.sort_values(["filed", "accn"], kind="stable")
    return {c: FA.from_frame(g) for c, g in f.groupby("concept", sort=False)}


class IssuerFacts:
    def __init__(self, cik: int, facts: pd.DataFrame, splits: pd.DataFrame | None = None):
        self.cik = int(cik)
        self.by_concept = _prep(facts) if len(facts) else {}
        filed = facts.loc[facts["form"].isin(C.ALLOWED_FORMS), "filed"] if len(facts) else pd.Series([], dtype="datetime64[ns]")
        self.filing_dates = sorted(pd.to_datetime(filed.unique()))
        # Split events on the price-data basis: (date, ratio)
        self.splits = splits if splits is not None else pd.DataFrame(columns=["date", "splits"])

    def split_factor_after(self, date: pd.Timestamp) -> float:
        s = self.splits.loc[self.splits["date"] > date, "splits"]
        return float(np.prod(s.to_numpy())) if len(s) else 1.0

    def period_end(self, view: View) -> pd.Timestamp | None:
        ends = []
        for c in C.CFO + C.REVENUE[:3] + C.OPERATING_INCOME:
            fa = view.get(c)
            if fa is not None and (~fa.is_instant).any():
                ends.append(pd.Timestamp(fa.end[~fa.is_instant].max()))
        return max(ends) if ends else None

    def shares(self, view: View, E: pd.Timestamp) -> Q:
        wad = None
        fa = view.get(C.SHARES_WAD[0])
        if fa is not None:
            wad = _last(fa, _near(fa.end, E, 3) & (fa.dur <= 100))
        cands = []
        cov = view.get(C.SHARES_COVER[0])
        if cov is not None:
            latest_accn = cov.accn[-1]
            same = cov.accn == latest_accn
            last_end = cov.end[same].max()
            rows = np.flatnonzero(same & (cov.end == last_end))
            r = cov.row(rows[-1])
            if (E - r["end"]).days <= 200:  # cover-page date near the latest period
                cands.append(("COVER_PAGE", float(cov.val[rows].sum()), r, C.SHARES_COVER[0]))
        bs = view.get(C.SHARES_BS[0])
        if bs is not None:
            r = _last(bs, bs.is_instant & _near(bs.end, E, 3))
            if r:
                cands.append(("BALANCE_SHEET", r["val"], r, C.SHARES_BS[0]))
        ref = float(wad["val"]) if wad is not None else None
        for route, val, row, concept in cands:
            if val <= 0:
                continue
            if ref is None or 0.75 <= val / ref <= 1.25:
                f = self.split_factor_after(row["filed"])
                return Q(val * f, "VALID", {"inputs": [_lin(row, concept, route)], "split_factor": f,
                                            "wad_check": None if ref is None else round(val / ref, 4)})
        if wad is not None and float(wad["val"]) > 0:
            f = self.split_factor_after(wad["filed"])
            return Q(float(wad["val"]) * f, "VALID", {"inputs": [_lin(wad, C.SHARES_WAD[0], "WEIGHTED_DILUTED")],
                                                      "split_factor": f, "flag": "SHARES_FROM_WEIGHTED_AVERAGE"})
        return _missing("SHARES_MISSING")

    def fundamentals(self, asof: pd.Timestamp) -> dict:
        """Canonical quantities known at `asof` (filing date <= asof)."""
        view = View(self.by_concept, asof)
        out: dict = {"cik": self.cik, "asof": asof}
        E = self.period_end(view)
        if E is None:
            out["status"] = "NO_FINANCIAL_STATEMENTS"
            return out
        out["period_end"] = E
        q = {}
        q["revenue"] = flow_ttm(view, C.REVENUE, E)
        ebit = flow_ttm(view, C.OPERATING_INCOME, E)
        if not ebit.ok:
            pre, intr = flow_ttm(view, C.PRETAX_INCOME, E), flow_ttm(view, C.INTEREST_EXPENSE, E)
            if pre.ok and intr.ok:
                ebit = Q(pre.value + intr.value, "VALID", {"method": "PRETAX_PLUS_INTEREST",
                                                          "inputs": [pre.lineage, intr.lineage]})
        q["ebit"] = ebit
        da = flow_ttm(view, C.DA, E)
        if not da.ok:
            dep, amo = flow_ttm(view, C.DEPRECIATION, E), flow_ttm(view, C.AMORTIZATION, E)
            if dep.ok:
                da = Q(dep.value + (amo.value if amo.ok else 0.0), "VALID",
                       {"method": "DEPRECIATION+AMORTIZATION" if amo.ok else "DEPRECIATION_ONLY",
                        "inputs": [dep.lineage] + ([amo.lineage] if amo.ok else [])})
        q["da"] = da
        q["cfo"] = flow_ttm(view, C.CFO, E)
        q["capex"] = flow_ttm(view, C.CAPEX, E)
        q["interest"] = flow_ttm(view, C.INTEREST_EXPENSE, E)
        q["pretax"] = flow_ttm(view, C.PRETAX_INCOME, E)
        q["tax"] = flow_ttm(view, C.INCOME_TAX, E)
        q["cash"] = instant(view, C.CASH, E)
        q["debt"] = debt_at(view, E)
        q.update(equity_claims_at(view, E))
        q["liabilities"] = instant(view, C.LIABILITIES, E)
        q["shares"] = self.shares(view, E)

        # Debt sanity: borrowings cannot exceed total liabilities.
        if q["debt"].ok and q["liabilities"].ok and q["debt"].value > q["liabilities"].value * 1.0001:
            q["debt"] = _missing("MAPPING_REVIEW_REQUIRED", detail="debt exceeds total liabilities")

        # Prior-year invested capital for the ROIC average.
        Ep = E - pd.DateOffset(years=1)
        prior_dates = [d for d in self._instant_dates(view) if abs((d - Ep).days) <= 10]
        if prior_dates:
            Dp = prior_dates[0]
            pc = equity_claims_at(view, Dp)
            q["debt_prior"], q["cash_prior"] = debt_at(view, Dp), instant(view, C.CASH, Dp)
            q["equity_prior"], q["nci_prior"], q["preferred_prior"] = pc["equity"], pc["nci"], pc["preferred"]
        else:
            for k in ("debt_prior", "cash_prior", "equity_prior", "nci_prior", "preferred_prior"):
                q[k] = _missing("PRIOR_YEAR_BALANCE_SHEET_MISSING")

        # Tax rate
        tax_rate = _missing("TAX_RATE_UNDEFINED")
        if q["tax"].ok and q["pretax"].ok and q["pretax"].value > 0:
            r = q["tax"].value / q["pretax"].value
            if 0 <= r <= 0.5:
                tax_rate = Q(r, "VALID", {"method": "TTM_EFFECTIVE"})
        if not tax_rate.ok:
            t_series, ts = annual_series(view, C.INCOME_TAX, 3)
            p_series, ps = annual_series(view, C.PRETAX_INCOME, 3)
            if ts == "VALID" and ps == "VALID":
                tsum, psum = sum(v for _, v, _ in t_series), sum(v for _, v, _ in p_series)
                if psum > 0 and 0 <= tsum / psum <= 0.5:
                    tax_rate = Q(tsum / psum, "VALID", {"method": "3FY_AGGREGATE_EFFECTIVE"})
        q["tax_rate"] = tax_rate

        # Annual histories
        rev_hist, rev_status = annual_series(view, C.REVENUE, 4)
        eps_hist, eps_status = annual_series(view, C.EPS, 4)
        cfo_hist, cfo_status = annual_series(view, C.CFO, 3)
        capex_hist, capex_status = annual_series(view, C.CAPEX, 3)
        out["rev_hist"], out["rev_hist_status"] = rev_hist, rev_status
        eps_adj = []
        for end, val, lin in eps_hist:
            f = self.split_factor_after(pd.Timestamp(lin["filed"]))
            eps_adj.append((end, val / f, {**lin, "split_factor": f}))
        out["eps_hist"], out["eps_hist_status"] = eps_adj, eps_status
        fcf_years = []
        if cfo_status == "VALID" and capex_status == "VALID":
            cap = {e: v for e, v, _ in capex_hist}
            for e, v, _ in cfo_hist:
                m = [k for k in cap if abs((k - e).days) <= 7]
                if m:
                    fcf_years.append(v - cap[m[0]])
        out["fcf_annual_last3"] = fcf_years if len(fcf_years) == 3 else None
        out["q"] = q
        out["max_filed_used"] = self._max_filed(q)
        out["status"] = "OK"
        return out

    def _instant_dates(self, view: View) -> list[pd.Timestamp]:
        dates = set()
        for c in C.EQUITY_PARENT + C.EQUITY_TOTAL + C.CASH:
            fa = view.get(c)
            if fa is not None:
                dates.update(pd.Timestamp(d) for d in fa.end[fa.is_instant])
        return sorted(dates, reverse=True)

    @staticmethod
    def _max_filed(q: dict) -> str | None:
        best = None

        def walk(o):
            nonlocal best
            if isinstance(o, dict):
                if "filed" in o:
                    best = max(best or o["filed"], o["filed"])
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o:
                    walk(v)
        for v in q.values():
            walk(v.lineage)
        return best
