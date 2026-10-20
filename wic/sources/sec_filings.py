"""Supplement companyfacts with filings SEC's aggregated API has not ingested.

SEC's companyfacts endpoint can lag or omit recent filings (observed live on
2026-10-20: e.g. Coca-Cola's 10-Q filed 2026-07-29 was absent). For every
10-K/10-Q listed in the issuer's submissions index but missing from
companyfacts, this module reads the filing's own XBRL instance document from
EDGAR and extracts the same non-dimensional facts companyfacts would carry.
"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import pandas as pd
from lxml import etree

from ..accounting.concepts import ALL_CONCEPTS, ALLOWED_FORMS
from ..util import sha256_bytes, utc_now
from .http import PoliteSession, SourceUnavailable
from .sec import COLUMNS

SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/"
XBRLI = "http://www.xbrl.org/2003/instance"
XBRLDI = "http://xbrl.org/2006/xbrldi"
UNIT_MAP = {"iso4217:USD": "USD", "xbrli:shares": "shares", "shares": "shares", "USD": "USD"}


def _cached_get(http: PoliteSession, url: str, cache: Path | None) -> bytes | None:
    if cache and cache.exists():
        return gzip.decompress(cache.read_bytes())
    r = http.get(url)
    if r.status_code == 404:
        return None
    if r.status_code != 200:
        raise SourceUnavailable(f"{url} HTTP {r.status_code}")
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(gzip.compress(r.content, mtime=0))
    return r.content


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _unit_label(unit_el) -> str | None:
    measures = [m.text.strip() for m in unit_el.iter(f"{{{XBRLI}}}measure")]
    if len(measures) == 1:
        return UNIT_MAP.get(measures[0], None)
    if len(measures) == 2 and unit_el.find(f"{{{XBRLI}}}divide") is not None:
        num, den = (UNIT_MAP.get(m) for m in measures)
        if num == "USD" and den == "shares":
            return "USD/shares"
    return None


def parse_instance(xml: bytes, cik: int, accn: str, form: str, filed: str) -> pd.DataFrame:
    root = etree.fromstring(xml, parser=etree.XMLParser(huge_tree=True, recover=True))
    contexts = {}
    for c in root.iter(f"{{{XBRLI}}}context"):
        if c.find(f".//{{{XBRLI}}}segment") is not None or c.find(f".//{{{XBRLI}}}scenario") is not None:
            continue  # dimensional context: companyfacts excludes these too
        inst = c.find(f".//{{{XBRLI}}}instant")
        if inst is not None:
            contexts[c.get("id")] = (None, inst.text.strip())
        else:
            s, e = c.find(f".//{{{XBRLI}}}startDate"), c.find(f".//{{{XBRLI}}}endDate")
            if s is not None and e is not None:
                contexts[c.get("id")] = (s.text.strip(), e.text.strip())
    units = {u.get("id"): _unit_label(u) for u in root.iter(f"{{{XBRLI}}}unit")}
    wanted = set(ALL_CONCEPTS)
    rows = []
    for el in root:
        if not isinstance(el.tag, str):
            continue
        ns = el.tag[1:].split("}")[0] if el.tag.startswith("{") else ""
        name = _local(el.tag)
        if "fasb.org/us-gaap" in ns:
            key = name
        elif "xbrl.sec.gov/dei" in ns:
            key = f"dei:{name}"
        else:
            continue
        if key not in wanted or el.get("contextRef") not in contexts:
            continue
        unit = units.get(el.get("unitRef"))
        if unit is None or el.text is None:
            continue
        try:
            val = float(el.text.strip())
        except ValueError:
            continue
        start, end = contexts[el.get("contextRef")]
        rows.append((cik, key, unit, start, end, val, accn, None, None, form, filed))
    df = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates()
    for c in ("start", "end", "filed"):
        df[c] = pd.to_datetime(df[c])
    return df


def missing_filings(submissions: dict, present_accns: set[str], since: str) -> list[dict]:
    rec = submissions.get("filings", {}).get("recent", {})
    out = []
    for i, form in enumerate(rec.get("form", [])):
        if form not in ALLOWED_FORMS or rec["filingDate"][i] < since:
            continue
        accn = rec["accessionNumber"][i]
        if accn in present_accns or not rec.get("isXBRL", [1] * (i + 1))[i]:
            continue
        out.append({"accn": accn, "form": form, "filed": rec["filingDate"][i],
                    "primary": rec["primaryDocument"][i], "report_date": rec["reportDate"][i]})
    return out


def supplement_issuer(http: PoliteSession, cik: int, present_accns: set[str], since: str,
                      cache_dir: Path | None) -> tuple[pd.DataFrame, list[dict]]:
    sub_raw = _cached_get(http, SUBMISSIONS_URL.format(cik=cik),
                          cache_dir / "submissions" / f"CIK{cik:010d}.json.gz" if cache_dir else None)
    if sub_raw is None:
        return pd.DataFrame(columns=COLUMNS), []
    frames, log = [], []
    for f in missing_filings(json.loads(sub_raw), present_accns, since):
        acc = f["accn"].replace("-", "")
        base = ARCHIVE.format(cik=cik, acc=acc)
        stem = f["primary"].rsplit(".", 1)[0]
        cache = cache_dir / "instances" / f"{acc}.xml.gz" if cache_dir else None
        xml = _cached_get(http, base + f"{stem}_htm.xml", cache)
        if xml is None:  # non-inline filings: find the instance via the directory index
            idx = _cached_get(http, base + "index.json", None)
            names = [x["name"] for x in json.loads(idx)["directory"]["item"]] if idx else []
            inst = [n for n in names if n.endswith(".xml") and not n.endswith(
                ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")) and n != "FilingSummary.xml"]
            xml = _cached_get(http, base + inst[0], cache) if inst else None
        if xml is None:
            log.append({**f, "cik": cik, "status": "INSTANCE_NOT_FOUND"})
            continue
        df = parse_instance(xml, cik, f["accn"], f["form"], f["filed"])
        frames.append(df)
        log.append({**f, "cik": cik, "status": "SUPPLEMENTED", "facts": int(len(df)),
                    "instance_sha256": sha256_bytes(xml), "url": base, "retrieved_utc": utc_now()})
    facts = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)
    return facts, log
