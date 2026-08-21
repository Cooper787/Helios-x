"""HTTP plumbing shared by every data source.

Standard-library only. The SEC mandates a descriptive User-Agent and returns
403 without one; both SEC and clinicaltrials.gov rate-limit, so retries use
exponential backoff with jitter to avoid a thundering herd against public
infrastructure.
"""

from __future__ import annotations

import gzip
import json
import logging
import random
import time
import urllib.error
import urllib.request
import zlib
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class SourceError(RuntimeError):
    """A data source could not be read. Callers must fail closed on this."""


class HttpJsonClient:
    """Minimal JSON-over-HTTP client with backoff.

    Deliberately not the requests library: every dependency added to a job that
    produces trade recommendations is a dependency that can break the job or be
    compromised. The standard library covers this need.
    """

    def __init__(
        self,
        user_agent: str,
        timeout_s: int = 30,
        max_retries: int = 4,
        base_delay_s: float = 1.5,
        sleep=time.sleep,
        rng: Optional[random.Random] = None,
    ) -> None:
        if not user_agent or "@" not in user_agent:
            # SEC's fair-access policy requires a contactable identity.
            raise ValueError("user_agent must identify the operator and include an email")
        self.user_agent = user_agent
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self._sleep = sleep
        self._rng = rng or random.Random()

    def get_json(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        hdrs = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }
        if headers:
            hdrs.update(headers)

        last_error: Optional[Exception] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=hdrs)
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    raw = resp.read()
                    encoding = resp.headers.get("Content-Encoding", "")
                return json.loads(_decode_body(raw, encoding))

            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 403:
                    # Not transient. Retrying a 403 just burns the rate limit
                    # and risks an IP block.
                    raise SourceError(
                        f"403 Forbidden for {url}. The SEC requires a descriptive "
                        f"User-Agent with contact details; current value is "
                        f"{self.user_agent!r}."
                    ) from exc
                if exc.code == 404:
                    raise SourceError(f"404 Not Found for {url}") from exc
                if exc.code not in (429, 500, 502, 503, 504):
                    raise SourceError(f"HTTP {exc.code} for {url}") from exc
                logger.warning(
                    "HTTP %s from %s (attempt %d/%d)", exc.code, url, attempt, self.max_retries
                )

            except (
                urllib.error.URLError,
                TimeoutError,
                json.JSONDecodeError,
                UnicodeDecodeError,
                zlib.error,
                OSError,
            ) as exc:
                last_error = exc
                logger.warning(
                    "%s reading %s (attempt %d/%d)",
                    type(exc).__name__,
                    url,
                    attempt,
                    self.max_retries,
                )

            if attempt < self.max_retries:
                delay = min(self.base_delay_s * (2 ** (attempt - 1)), 60.0)
                delay *= self._rng.uniform(0.5, 1.5)  # jitter
                logger.info("Retrying %s in %.1fs", url, delay)
                self._sleep(delay)

        raise SourceError(
            f"Failed to read {url} after {self.max_retries} attempts: {last_error}"
        ) from last_error


def _decode_body(raw: bytes, content_encoding: str) -> str:
    """Decode a response body, honouring Content-Encoding.

    The client advertises `Accept-Encoding: gzip, deflate` because these are
    large JSON payloads over public infrastructure and it is rude not to. urllib
    does not decompress for you, so without this the first byte of a gzip stream
    (0x1f 0x8b) reaches json.loads and the run dies with a UnicodeDecodeError
    that names neither gzip nor the URL. That is exactly what happened on the
    first live run: clinicaltrials.gov honoured the header and the pipeline
    crashed before it could write a ledger entry.

    Some servers gzip regardless of the header, so the magic-number check runs
    even when Content-Encoding is absent.
    """
    enc = (content_encoding or "").strip().lower()
    if enc == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    elif enc == "deflate":
        try:
            raw = zlib.decompress(raw)
        except zlib.error:
            # Raw deflate stream without the zlib wrapper.
            raw = zlib.decompress(raw, -zlib.MAX_WBITS)
    return raw.decode("utf-8")


def dig(obj: Any, *path: str, default: Any = None) -> Any:
    """Walk a nested dict safely.

    Every external schema in this pipeline is owned by someone else and can
    change without notice. Reaching into it with chained subscripts turns a
    renamed field into a crash at 09:00 UTC; this turns it into a missing
    value that the caller can report.
    """
    cur = obj
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur if cur is not None else default
