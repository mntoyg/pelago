"""The one small interface every source implements, plus the HTTP helper they share.

    fetcher.fetch(area, run_date) -> list[Row]      one Row per cell of the area (value None = no observation)

A fetcher raises FetchError(code) on any failure. `code` is a short machine word (timeout, http_503, empty_grid, ...);
it is the ONLY thing that is stored in job_runs. Upstream text, URLs and exception messages are never put into it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable, Mapping, Protocol
from urllib.parse import urljoin, urlsplit

USER_AGENT = "pelago-ingest/0.1 (open-source research prototype)"   # generic on purpose: no person, no address
MAX_RESPONSE_BYTES = 8_000_000                                       # unbounded bodies are a denial-of-service risk

_CODE = re.compile(r"[a-z0-9_]{1,64}")
# deterministic failures: asking again gives the same answer, so the pipeline moves on to the next fetcher at once
_PERMANENT = {"empty_grid", "no_recent_data", "bad_shape", "bad_value", "http_400", "http_401", "http_403", "http_404",
              "http_410", "route_not_allowed", "too_large", "bad_config", "unknown_source", "bad_url",
              "host_not_allowed", "redirect_limit", "bad_redirect"}


class FetchError(Exception):
    def __init__(self, code: str):
        if not _CODE.fullmatch(code):
            code = "error"
        super().__init__(code)
        self.code = code

    @property
    def retryable(self) -> bool:
        return self.code not in _PERMANENT


@dataclass(frozen=True)
class Row:
    cell_id: int
    value: float | None                      # the variable's main value; None = no observation (never 0)
    observed_at: datetime | None             # UTC; None only when value is None (wave_wind: retrieval time)
    source_id: str
    product: str | None = None               # 'daily' for chlorophyll, else None
    extra: Mapping[str, float | None] = field(default_factory=dict)   # sst: grad_c_per_km; wave_wind: wind_kmh


HttpGet = Callable[[str, float], bytes]


class Fetcher(Protocol):
    source_id: str
    variable: str            # 'sst' | 'chl' | 'depth' | 'wave_wind'
    routes: tuple[str, ...]  # licence routes this source may be used on (ARCHITECTURE.md A7), e.g. ('A',)

    def fetch(self, area, run_date: date) -> list[Row]: ...


def http_get(url: str, timeout: float, *, allowed_hosts: tuple[str, ...] = ()) -> bytes:
    """GET an allowlisted HTTPS host, following at most two allowlisted redirects."""
    import requests
    def check_url(candidate: str) -> None:
        try:
            parsed = urlsplit(candidate)
            host = parsed.hostname
            valid_port = parsed.port in (None, 443)
        except (TypeError, ValueError):
            raise FetchError("bad_url") from None
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or not valid_port:
            raise FetchError("bad_url")
        if host.lower() not in allowed_hosts:
            raise FetchError("host_not_allowed")

    if not isinstance(allowed_hosts, tuple) or not allowed_hosts:
        raise FetchError("bad_config")
    check_url(url)
    try:
        current = url
        for redirect_count in range(3):
            with requests.get(current, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True,
                              allow_redirects=False) as r:
                if r.status_code in (301, 302, 303, 307, 308):
                    location = r.headers.get("Location")
                    if not location:
                        raise FetchError("bad_redirect")
                    if redirect_count == 2:
                        raise FetchError("redirect_limit")
                    current = urljoin(current, location)
                    check_url(current)
                    continue
                if r.status_code != 200:
                    raise FetchError(f"http_{r.status_code}")
                body = bytearray()
                for chunk in r.iter_content(65536):
                    body += chunk
                    if len(body) > MAX_RESPONSE_BYTES:
                        raise FetchError("too_large")
                return bytes(body)
        raise FetchError("redirect_limit")
    except FetchError:
        raise
    except requests.Timeout as exc:
        raise FetchError("timeout") from exc
    except requests.RequestException as exc:
        raise FetchError("network_error") from exc
