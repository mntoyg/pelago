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

USER_AGENT = "pelago-ingest/0.1 (open-source research prototype)"   # generic on purpose: no person, no address
MAX_RESPONSE_BYTES = 8_000_000                                       # unbounded bodies are a denial-of-service risk

_CODE = re.compile(r"[a-z0-9_]{1,64}")
# deterministic failures: asking again gives the same answer, so the pipeline moves on to the next fetcher at once
_PERMANENT = {"empty_grid", "no_recent_data", "bad_shape", "bad_value", "http_400", "http_401", "http_403", "http_404",
              "http_410", "route_not_allowed", "too_large", "bad_config", "unknown_source", "bad_url"}


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


def http_get(url: str, timeout: float) -> bytes:
    """GET with a fixed generic User-Agent, a timeout and a size cap. Errors become FetchError codes only."""
    import requests
    if not url.startswith("https://"):
        raise FetchError("bad_url")
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, stream=True) as r:
            if r.status_code != 200:
                raise FetchError(f"http_{r.status_code}")
            body = bytearray()
            for chunk in r.iter_content(65536):
                body += chunk
                if len(body) > MAX_RESPONSE_BYTES:
                    raise FetchError("too_large")
            return bytes(body)
    except FetchError:
        raise
    except requests.Timeout as exc:
        raise FetchError("timeout") from exc
    except requests.RequestException as exc:
        raise FetchError("network_error") from exc
