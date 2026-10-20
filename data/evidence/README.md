# Primary-source evidence for the 2026-10-19 run

Raw documents behind the sealed snapshots, so every input can be inspected, not only hash-checked.
Hashes in `EVIDENCE_MANIFEST.json` match those recorded in
`data/snapshots/sp500_2026-10-19/SOURCES.json` and `sec_filing_supplement.csv`.

| Folder | Contents |
|---|---|
| `sec_xbrl_instances/` | 159 SEC XBRL instance documents (gzip) for the 160 filing records that SEC's companyfacts API had not ingested (one 10-Q was filed jointly by two registrants). `xml_sha256` is the SHA-256 of the decompressed XML exactly as served by EDGAR at `source_url`. |
| `wikipedia_revisions/` | 33 pinned revisions of *List of S&P 500 companies* (MediaWiki parse API JSON): 32 semiannual revisions used for point-in-time GICS/CIK labels in the backtest, plus revision 1380159481 used for the current universe. Wikipedia content is CC BY-SA 4.0. |
| `run_logs/` | Console logs of the acquisition and backtest runs (`acquire.log` is the first, aborted attempt showing the SEC 403 for a no-reply contact). The SEC contact header is never logged. |

Not included (re-downloadable; per-issuer SHA-256 recorded in `sec_sources.csv`): the raw SEC companyfacts
payloads (~250 MB) and EDGAR submissions indexes.

Verify: `python -c "import gzip,hashlib,json;m=json.load(open('data/evidence/EVIDENCE_MANIFEST.json'));print(all(hashlib.sha256(gzip.decompress(open('data/evidence/sec_xbrl_instances/'+k,'rb').read())).hexdigest()==v['xml_sha256'] for k,v in m['sec_xbrl_instances'].items()))"`
