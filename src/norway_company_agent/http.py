from __future__ import annotations

import json
import hashlib
import time
import urllib.error
import urllib.request
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class FetchResult:
    url: str
    status: int
    elapsed_ms: int
    bytes_received: int
    body: Any = None
    error: str | None = None
    content_sha256: str | None = None
    retrieved_at: str | None = None
    effective_at: str | None = None
    cached: bool = False


_cache_lock = threading.Lock()
_request_cache: dict[str, FetchResult] = {}


def clear_request_cache() -> None:
    with _cache_lock:
        _request_cache.clear()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fetch_json(url: str, *, timeout: float = 20.0, attempts: int = 3, use_cache: bool = True) -> FetchResult:
    if use_cache:
        with _cache_lock:
            hit = _request_cache.get(url)
            if hit is not None:
                return FetchResult(
                    url=hit.url,
                    status=hit.status,
                    elapsed_ms=0,
                    bytes_received=0,
                    body=hit.body,
                    error=hit.error,
                    content_sha256=hit.content_sha256,
                    retrieved_at=hit.retrieved_at,
                    effective_at=hit.effective_at,
                    cached=True,
                )

    last_error = "request failed"
    for attempt in range(attempts):
        started = time.monotonic()
        request = urllib.request.Request(
            url,
            headers={"Accept": "application/json", "User-Agent": "builderr-signalpost-poc/0.1 (+https://builderr.ai)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                elapsed = int((time.monotonic() - started) * 1000)
                res = FetchResult(url, response.status, elapsed, len(raw), json.loads(raw), content_sha256=hashlib.sha256(raw).hexdigest(), retrieved_at=_utc_now())
                if use_cache:
                    with _cache_lock:
                        _request_cache[url] = res
                return res
        except urllib.error.HTTPError as exc:
            elapsed = int((time.monotonic() - started) * 1000)
            raw = exc.read()
            if exc.code in {404, 410}:
                res = FetchResult(url, exc.code, elapsed, len(raw), error=f"HTTP {exc.code}", content_sha256=hashlib.sha256(raw).hexdigest(), retrieved_at=_utc_now())
                if use_cache:
                    with _cache_lock:
                        _request_cache[url] = res
                return res
            last_error = f"HTTP {exc.code}"
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = type(exc).__name__
        if attempt + 1 < attempts:
            time.sleep(0.4 * (2**attempt))
    return FetchResult(url, 0, 0, 0, error=last_error, retrieved_at=_utc_now())

