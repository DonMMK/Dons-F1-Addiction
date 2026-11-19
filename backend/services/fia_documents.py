"""Automatic, durable FIA catalogue indexing, separate from timing requests.

SQLite leases share work between uvicorn workers using the same DATA_DIR.
The worker discovers season/event identifiers rather than maintaining PDF URLs.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

import pandas as pd
import requests
from fastf1.ergast import Ergast

from .data import DATA_DIR
from . import events, weekend_sources as sources

LOG = logging.getLogger(__name__)


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None


class FiaDocumentIndexer:
    def __init__(
        self,
        directory,
        *,
        enabled=True,
        check_seconds=21600,
        retry_seconds=3600,
        clock=time.time,
    ):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / "fia_documents.sqlite3"
        self.enabled, self.check_seconds, self.retry_seconds = (
            enabled,
            max(60, check_seconds),
            max(60, retry_seconds),
        )
        self.clock = clock
        self.stop_event = threading.Event()
        self.wake = threading.Event()
        self.thread = None
        with self.db() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    kind TEXT, year INTEGER, round INTEGER, payload TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued', priority INTEGER NOT NULL,
                    next_check REAL NOT NULL DEFAULT 0, checked REAL, success REAL,
                    lease REAL NOT NULL DEFAULT 0, token TEXT, failures INTEGER NOT NULL DEFAULT 0,
                    message TEXT, documents TEXT NOT NULL DEFAULT '[]',
                    PRIMARY KEY (kind, year, round)
                );
                CREATE TABLE IF NOT EXISTS http_cache (url TEXT PRIMARY KEY, expires REAL, body BLOB);
                CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), next_request REAL NOT NULL);
                INSERT OR IGNORE INTO budget VALUES(1, 0);
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, kind, year, rd, payload, priority=0):
        if not self.enabled:
            return
        body = json.dumps(payload, sort_keys=True)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            old = db.execute(
                "SELECT payload, priority FROM jobs WHERE kind=? AND year=? AND round=?",
                (kind, year, rd),
            ).fetchone()
            if old:
                previous = json.loads(old["payload"])
                # A season scan without roster data must not erase a richer request.
                if previous.get("roster") and (
                    not payload.get("roster") or priority < old["priority"]
                ):
                    payload = {**payload, "roster": previous["roster"]}
                    body = json.dumps(payload, sort_keys=True)
                db.execute(
                    "UPDATE jobs SET priority=MAX(priority, ?), payload=?, next_check=CASE WHEN payload<>? THEN MIN(next_check, ?) ELSE next_check END WHERE kind=? AND year=? AND round=?",
                    (priority, body, body, self.clock(), kind, year, rd),
                )
            else:
                db.execute(
                    "INSERT INTO jobs(kind,year,round,payload,priority) VALUES(?,?,?,?,?)",
                    (kind, year, rd, body, priority),
                )
        self.wake.set()

    def request(self, year, rd=None, event_name=None, roster=None):
        self.enqueue("season", year, 0, {}, 100)
        if rd is not None and event_name:
            self.enqueue(
                "event",
                year,
                rd,
                {"eventName": event_name, "roster": sorted(roster or [])},
                200,
            )

    def event_payload(self, year, rd):
        with self.db() as db:
            row = db.execute(
                "SELECT payload FROM jobs WHERE kind='event' AND year=? AND round=?",
                (year, rd),
            ).fetchone()
        return json.loads(row[0]) if row else {}

    def status(self, year, rd):
        with self.db() as db:
            row = db.execute(
                "SELECT * FROM jobs WHERE kind='event' AND year=? AND round=?",
                (year, rd),
            ).fetchone()
            season = db.execute(
                "SELECT * FROM jobs WHERE kind='season' AND year=? AND round=0", (year,)
            ).fetchone()
        row = row or season
        return {
            "enabled": self.enabled,
            "state": (
                "disabled" if not self.enabled else row["state"] if row else "queued"
            ),
            "scope": "event" if row and row["kind"] == "event" else "season",
            "checkedAt": iso(row["checked"]) if row else None,
            "lastSuccessAt": iso(row["success"]) if row else None,
            "nextCheckAt": iso(max(row["next_check"], row["lease"])) if row else None,
            "message": (
                row["message"]
                if row
                else "Automatic discovery will run in the background."
            ),
            "documents": (
                json.loads(row["documents"]) if row and row["kind"] == "event" else []
            ),
        }

    def claim(self):
        now = self.clock()
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute("SELECT next_request FROM budget WHERE id=1").fetchone()[0]
                > now + 5
            ):
                return None
            row = db.execute(
                "SELECT * FROM jobs WHERE next_check<=? AND lease<=? ORDER BY priority DESC, year DESC, round DESC LIMIT 1",
                (now, now),
            ).fetchone()
            if not row:
                return None
            token = uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET lease=?, token=?, state='checking' WHERE kind=? AND year=? AND round=?",
                (now + 600, token, row["kind"], row["year"], row["round"]),
            )
        return {**dict(row), "token": token}

    def finish(self, job, state, delay, message, *, success=False):
        now = self.clock()
        with self.db() as db:
            # If a richer roster arrived mid-flight, immediately process it next.
            db.execute(
                "UPDATE jobs SET state=CASE WHEN payload=? THEN ? ELSE 'queued' END, next_check=CASE WHEN payload=? THEN ? ELSE ? END, lease=0, token=NULL, checked=?, success=CASE WHEN ? THEN ? ELSE success END, failures=CASE WHEN ? THEN failures+1 ELSE 0 END, message=? WHERE kind=? AND year=? AND round=? AND token=?",
                (
                    job["payload"],
                    state,
                    job["payload"],
                    now + delay,
                    now,
                    now,
                    success,
                    now,
                    state == "error",
                    message,
                    job["kind"],
                    job["year"],
                    job["round"],
                    job["token"],
                ),
            )

    def throttle(self):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            slot = max(
                self.clock(),
                db.execute("SELECT next_request FROM budget WHERE id=1").fetchone()[0],
            )
            if slot - self.clock() > 5:
                raise RuntimeError("FIA provider cooldown is active")
            db.execute("UPDATE budget SET next_request=? WHERE id=1", (slot + 2.5,))
        delay = slot - self.clock()
        if delay > 0 and self.stop_event.wait(delay):
            raise RuntimeError("FIA indexer is stopping")

    def fetch(self, url):
        url = sources.fia_url(url)
        with self.db() as db:
            row = db.execute(
                "SELECT body FROM http_cache WHERE url=? AND expires>?",
                (url, self.clock()),
            ).fetchone()
        if row:
            return bytes(row[0])
        body = sources.download(url, before_request=self.throttle)
        with self.db() as db:
            db.execute(
                "INSERT OR REPLACE INTO http_cache VALUES(?,?,?)",
                (
                    url,
                    self.clock() + min(self.retry_seconds, self.check_seconds, 3600),
                    body,
                ),
            )
        return body

    def scan_season(self, year):
        schedule = events.get_schedule(year, include_testing=False)
        now = pd.Timestamp(self.clock(), unit="s", tz="UTC")
        roster = []
        try:
            constructors = Ergast().get_constructor_info(season=year, limit=100)
            if "constructorName" in constructors:
                roster = sorted(
                    set(constructors["constructorName"].dropna().astype(str))
                )
        except Exception:
            LOG.info(
                "FIA discovery continuing without a published season constructor roster"
            )
        selected = 0
        for _, event in schedule.iterrows():
            rd = event.get("RoundNumber")
            date = pd.to_datetime(event.get("EventDate"), utc=True, errors="coerce")
            if (
                pd.isna(rd)
                or rd < 1
                or pd.isna(date)
                or date.year != year
                or date > now + pd.Timedelta(days=7)
            ):
                continue
            self.enqueue(
                "event",
                year,
                int(rd),
                {"eventName": str(event["EventName"]), "roster": roster},
                int(rd),
            )
            selected += 1
        return selected

    def run_once(self):
        if not self.enabled:
            return False
        job = self.claim()
        if job is None:
            return False
        try:
            year, rd = job["year"], job["round"]
            if job["kind"] == "season":
                count = self.scan_season(year)
                self.finish(
                    job,
                    "idle" if count else "not_published",
                    3600,
                    f"{count} eligible weekends queued from the public season schedule. Documents are checked within seven days of a scheduled race.",
                    success=True,
                )
                return True
            payload = json.loads(job["payload"])
            previous = sources.snapshots(year).get(rd)
            if previous and sources.normal(
                sources.official_event(previous["eventName"])
            ) != sources.normal(sources.official_event(payload["eventName"])):
                previous = None

            def catalogue(documents):
                with self.db() as db:
                    db.execute(
                        "UPDATE jobs SET documents=? WHERE kind='event' AND year=? AND round=? AND token=?",
                        (json.dumps(documents), year, rd, job["token"]),
                    )

            result = sources.refresh(
                year,
                rd,
                payload["eventName"],
                roster=payload.get("roster"),
                fetch=self.fetch,
                save=False,
                previous=previous,
                on_documents=catalogue,
            )
            state = result["submissionStatus"]
            if state == "indexed":
                # The lease is still ours before an atomic evidence replacement.
                with self.db() as db:
                    db.execute("BEGIN IMMEDIATE")
                    owned = db.execute(
                        "SELECT token FROM jobs WHERE kind='event' AND year=? AND round=?",
                        (year, rd),
                    ).fetchone()
                    if not owned or owned[0] != job["token"]:
                        return True
                    sources.save_snapshot(result)
            message = {
                "indexed": "Published FIA submissions were indexed automatically.",
                "not_published": "Car-presentation submissions are not published in the discovered catalogue yet. Missing does not mean no upgrades.",
                "needs_review": "The PDF is published, but its layout or team names could not be parsed reliably. Previous evidence is retained.",
            }[state]
            self.finish(
                job,
                state,
                self.check_seconds if state == "indexed" else self.retry_seconds,
                message,
                success=state == "indexed",
            )
        except Exception as exc:
            status = (
                exc.response.status_code
                if isinstance(exc, requests.HTTPError) and exc.response is not None
                else None
            )
            delay = min(21600, 600 * 2 ** min(job["failures"], 5))
            if status in (429, 503):
                raw = exc.response.headers.get("Retry-After", "")
                try:
                    retry = (
                        float(raw)
                        if raw.isdigit()
                        else parsedate_to_datetime(raw).timestamp() - self.clock()
                    )
                    delay = max(delay, min(max(retry, 0), 86400))
                except (ValueError, TypeError, OverflowError):
                    pass
                with self.db() as db:
                    db.execute(
                        "UPDATE budget SET next_request=MAX(next_request,?) WHERE id=1",
                        (self.clock() + delay,),
                    )
            # A season/event absent from the catalogue is normal, but a parse or network failure is not.
            absent = isinstance(exc, ValueError) and "discoverable" in str(exc)
            message = (
                str(exc)
                if isinstance(exc, ValueError)
                else f"Schedule or FIA publication check failed{f' (HTTP {status})' if status else ''}; cached evidence remains available."
            )
            self.finish(
                job,
                "not_published" if absent else "error",
                self.retry_seconds if absent else delay,
                message,
            )
            LOG.info("FIA %s/%s refresh: %s", job["year"], job["round"], message)
        return True

    def _loop(self):
        next_enqueue = 0
        while not self.stop_event.is_set():
            try:
                now = datetime.fromtimestamp(self.clock(), timezone.utc)
                if self.clock() >= next_enqueue:
                    self.request(now.year)
                    if now.month == 1:
                        self.request(now.year - 1)
                    next_enqueue = self.clock() + 3600
                if self.run_once():
                    continue
            except Exception:
                LOG.exception("FIA background discovery paused; retrying later")
            self.wake.wait(30)
            self.wake.clear()

    def start(self):
        if self.enabled and (self.thread is None or not self.thread.is_alive()):
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._loop, name="fia-documents", daemon=True
            )
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=1)


_indexer = None
_lock = threading.Lock()


def get_indexer():
    global _indexer
    with _lock:
        if _indexer is None:
            _indexer = FiaDocumentIndexer(
                DATA_DIR / "weekend_evidence",
                enabled=os.getenv("F1_FIA_AUTO_REFRESH", "true").lower()
                not in ("false", "0", "no"),
            )
        return _indexer
