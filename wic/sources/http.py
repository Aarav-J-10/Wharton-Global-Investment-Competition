"""Polite HTTP client with retries, rate limiting and verified TLS only."""
from __future__ import annotations

import os
import threading
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SourceUnavailable(RuntimeError):
    """A required external source could not be reached; the run fails closed."""


def sec_user_agent() -> str:
    """SEC fair-access policy requires a declared contact in the User-Agent.

    The value is read from the environment and never written to artifacts.
    """
    ua = os.environ.get("WIC_SEC_USER_AGENT", "").strip()
    if not ua or "@" not in ua:
        raise SourceUnavailable(
            "Set WIC_SEC_USER_AGENT to 'Name contact@email' (SEC EDGAR fair-access requirement)")
    return ua


class PoliteSession:
    def __init__(self, user_agent: str, min_interval: float = 0.0, timeout: float = 60.0):
        self.session = requests.Session()
        retry = Retry(total=6, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504),
                      allowed_methods=("GET",), respect_retry_after_header=True)
        self.session.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=8))
        self.session.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.min_interval = min_interval
        self.timeout = timeout
        self._lock = threading.Lock()
        self._last = 0.0

    def get(self, url: str, **kwargs) -> requests.Response:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
        try:
            resp = self.session.get(url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:  # TLS/connection errors stay errors
            raise SourceUnavailable(f"{url}: {type(exc).__name__}: {exc}") from exc
        return resp
