"""Public historical OpenF1 transport with a shared disk cache and rate limit.

No account, token, browser, or F1TV authentication is used here. SQLite shares
the 30/minute budget between API workers using the same F1_DATA_DIR.
"""

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests

from .loading_errors import SessionDataError

BASE_URL = "https://api.openf1.org/v1"
ENDPOINTS = {
    "sessions",
    "drivers",
    "laps",
    "stints",
    "pit",
    "race_control",
    "weather",
    "session_result",
    "car_data",
    "location",
}


class OpenF1Client:
    def __init__(self, cache_dir):
        self.path = Path(cache_dir) / "openf1.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS responses "
                "(key TEXT PRIMARY KEY, expires REAL NOT NULL, body TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS budget "
                "(id INTEGER PRIMARY KEY CHECK(id=1), next_request REAL NOT NULL)"
            )
            db.execute("INSERT OR IGNORE INTO budget VALUES (1, 0)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            with db:
                yield db
        finally:
            db.close()

    def _reserve(self):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            now = time.time()
            next_request = db.execute(
                "SELECT next_request FROM budget WHERE id=1"
            ).fetchone()[0]
            delay = max(0, next_request - now)
            # Do not hold an API worker in a long sleep during provider backoff.
            if delay > 5:
                raise SessionDataError(
                    "openf1_rate_limited",
                    "OpenF1 is cooling down. Retry after the indicated delay.",
                    503,
                    max(1, int(delay) + 1),
                )
            db.execute(
                "UPDATE budget SET next_request=? WHERE id=1",
                (max(now, next_request) + 2.1,),
            )
        if delay:
            time.sleep(delay)

    def _backoff(self, seconds):
        with self.connect() as db:
            db.execute(
                "UPDATE budget SET next_request=MAX(next_request, ?) WHERE id=1",
                (time.time() + seconds,),
            )

    def get(self, endpoint, params, ttl=7 * 86400):
        if endpoint not in ENDPOINTS:
            raise ValueError("Unsupported OpenF1 endpoint")
        key = hashlib.sha256(
            json.dumps([endpoint, params], sort_keys=True).encode()
        ).hexdigest()
        # Serialize cold identical queries; successful requests are reused on disk.
        with self.lock:
            with self.connect() as db:
                row = db.execute(
                    "SELECT expires, body FROM responses WHERE key=?", (key,)
                ).fetchone()
            if row and row[0] > time.time():
                try:
                    cached = json.loads(row[1])
                    if isinstance(cached, list) and all(
                        isinstance(r, dict) for r in cached
                    ):
                        return cached
                except ValueError:
                    pass
            self._reserve()
            try:
                response = requests.get(
                    f"{BASE_URL}/{endpoint}",
                    params=params,
                    timeout=(10, 30),
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "F1EvidenceDashboard/1",
                    },
                )
            except requests.RequestException as exc:
                raise SessionDataError(
                    "openf1_network_error",
                    "OpenF1 could not be reached. Retry shortly.",
                    502,
                    20,
                ) from exc
            if response.status_code == 429:
                raw = response.headers.get("Retry-After", "60")
                try:
                    delay = int(raw)
                except ValueError:
                    try:
                        delay = int(
                            parsedate_to_datetime(raw).timestamp() - time.time()
                        )
                    except (ValueError, TypeError, OverflowError):
                        delay = 60
                delay = min(max(delay, 1), 3600)
                self._backoff(delay)
                raise SessionDataError(
                    "openf1_rate_limited",
                    "OpenF1's free request limit was reached. Cached data remains available.",
                    503,
                    delay,
                )
            if response.status_code in (401, 403):
                raise SessionDataError(
                    "openf1_access_unavailable",
                    "OpenF1 denied this request. Only historical sessions outside the live window are supported without an account.",
                    503,
                    60,
                )
            if response.status_code == 404:
                raise SessionDataError(
                    "openf1_not_published",
                    f"OpenF1 has not published {endpoint} for this session.",
                    425,
                    60,
                )
            if response.status_code != 200:
                raise SessionDataError(
                    "openf1_upstream_error",
                    f"OpenF1 returned HTTP {response.status_code}. Retry shortly.",
                    502,
                    30,
                )
            try:
                body = response.json()
            except ValueError as exc:
                raise SessionDataError(
                    "openf1_invalid_response",
                    "OpenF1 returned an invalid JSON response.",
                    502,
                    30,
                ) from exc
            if not isinstance(body, list) or not all(isinstance(r, dict) for r in body):
                raise SessionDataError(
                    "openf1_invalid_response",
                    "OpenF1 returned an unexpected data format.",
                    502,
                    30,
                )
            # Empty data is not a permanent historical cache hit.
            with self.connect() as db:
                db.execute(
                    "INSERT OR REPLACE INTO responses VALUES (?, ?, ?)",
                    (
                        key,
                        time.time() + (ttl if body else min(ttl, 60)),
                        json.dumps(body, allow_nan=False),
                    ),
                )
            return body
