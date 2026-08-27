from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import requests

from finchat.config import CACHE_DIR, FILINGS_DIR, SEC_RATE_SLEEP, SEC_USER_AGENT

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"


class Edgar:
    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self._last_call = 0.0

    def _throttle(self) -> None:
        wait = SEC_RATE_SLEEP - (time.time() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

    def get_json(self, url: str, cache: bool = True) -> Any:
        cache_path = CACHE_DIR / ("json_" + url.replace("https://", "").replace("/", "_").replace("?", "_")[:180] + ".json")
        if cache and cache_path.exists():
            return json.loads(cache_path.read_text())
        for attempt in range(4):
            self._throttle()
            resp = self.session.get(url, timeout=60)
            if resp.status_code in (403, 429, 503):
                time.sleep(2**attempt * 2)
                continue
            resp.raise_for_status()
            data = resp.json()
            if cache:
                cache_path.write_text(json.dumps(data))
            return data
        raise RuntimeError(f"EDGAR kept failing for {url}")

    def get_text(self, url: str) -> str:
        for attempt in range(4):
            self._throttle()
            resp = self.session.get(url, timeout=120)
            if resp.status_code in (403, 429, 503):
                time.sleep(2**attempt * 2)
                continue
            resp.raise_for_status()
            return resp.text
        raise RuntimeError(f"EDGAR kept failing for {url}")

    def cik_for(self, ticker: str) -> tuple[str, str]:
        mapping = self.get_json(TICKER_MAP_URL)
        wanted = ticker.upper().strip()
        for entry in mapping.values():
            if entry["ticker"].upper() == wanted:
                return str(entry["cik_str"]).zfill(10), entry["title"]
        raise KeyError(f"Ticker {ticker} not found on EDGAR")

    def companyfacts(self, cik: str) -> dict[str, Any]:
        return self.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json")

    def submissions(self, cik: str) -> dict[str, Any]:
        data = self.get_json(f"https://data.sec.gov/submissions/CIK{cik}.json")
        filings = data.get("filings", {})
        pages = filings.get("files", []) or []
        if pages:
            merged = {k: list(v) for k, v in filings.get("recent", {}).items()}
            for page in pages:
                try:
                    extra = self.get_json(f"https://data.sec.gov/submissions/{page['name']}")
                except Exception:
                    continue
                for key, values in extra.items():
                    merged.setdefault(key, []).extend(values)
            out = dict(data)
            out["filings"] = {**filings, "recent": merged}
            return out
        return data

    def tenk_filings(self, cik: str, fy_start: int, fy_end: int) -> list[dict[str, Any]]:
        sub = self.submissions(cik)
        recent = sub["filings"]["recent"]
        out: list[dict[str, Any]] = []
        seen_accessions = set()
        for form, acc, doc, filed, report in zip(
            recent["form"], recent["accessionNumber"], recent["primaryDocument"],
            recent["filingDate"], recent["reportDate"],
        ):
            if form != "10-K" or acc in seen_accessions:
                continue
            seen_accessions.add(acc)
            fy = int(filed[:4])
            if report[:4].isdigit():
                fy = max(fy, int(report[:4]))
            if not (fy_start <= fy <= fy_end + 1):
                continue
            out.append({
                "form": form,
                "accession": acc,
                "accession_nodash": acc.replace("-", ""),
                "primary_document": doc,
                "filed": filed,
                "report_date": report,
                "fy_label_guess": fy,
                "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}/{doc}",
            })
        out.sort(key=lambda f: f["filed"])
        return out

    def download_filing(self, filing: dict[str, Any], cik: str) -> Path:
        dest = FILINGS_DIR / cik / filing["accession_nodash"] / filing["primary_document"]
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            text = self.get_text(filing["url"])
            dest.write_text(text, encoding="utf-8")
        return dest
