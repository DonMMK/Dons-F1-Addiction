"""Cached, condition-specific pace boards and bounded background catch-up.

Stores separate strict matched evidence and broader adjusted package estimates
for completed races, with explicit between-weekend comparison rules.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid

import pandas as pd
from fastapi import HTTPException

from . import events
from .data import DATA_DIR, finished, load_session, number
from .pace_evidence import POLICY, analyse
from .pace_bridge import POLICY as BRIDGE_POLICY

LOG = logging.getLogger(__name__)
VERSION = hashlib.sha256(
    json.dumps(
        {"grid": 2, "matching": POLICY, "bridge": BRIDGE_POLICY}, sort_keys=True
    ).encode()
).hexdigest()[:12]
HISTORY = 6


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat() if value else None


def ttl(snapshot):
    pace = snapshot["pace"].get("coverageEstimate", snapshot["pace"])
    return 21600 if pace["teamPace"]["rows"] else 600


def make_snapshot(year, rd, session, pace, now=None):
    if session.name != "Race" or not finished(session):
        raise ValueError("Only completed race evidence can be stored in the pace board")
    if session.event.get("RoundNumber", rd) != rd:
        raise ValueError("Race identity does not match the requested round")
    colours = {}
    for team, frame in session.results.groupby("TeamName"):
        if "TeamColor" in frame:
            values = frame["TeamColor"].dropna().astype(str)
            colours[str(team)] = values.iloc[0] if len(values) else None
    return {
        "year": year,
        "round": rd,
        "eventName": str(session.event["EventName"]),
        "condition": pace["condition"],
        "version": VERSION,
        "checkedAt": iso(now or time.time()),
        "source": getattr(session, "data_source", "FastF1 recorded timing"),
        "pace": pace,
        "colours": colours,
    }


def build_board(current, previous=None, view="adjusted"):
    if previous and (
        previous["year"] != current["year"]
        or previous["condition"] != current["condition"]
        or previous["version"] != current["version"]
        or previous["round"] >= current["round"]
    ):
        previous = None

    def select(snapshot):
        pace = snapshot["pace"]
        return pace.get("coverageEstimate", pace) if view == "adjusted" else pace

    pace = select(current)
    baseline = pace.get("normalisationLapSeconds")
    old_rows = (
        {r["name"]: r for r in select(previous)["teamPace"]["rows"]}
        if previous
        and select(previous).get("view", "strict") == pace.get("view", "strict")
        else {}
    )
    old_baseline = select(previous).get("normalisationLapSeconds") if previous else None
    groups = []
    rows = pace["teamPace"]["rows"]
    for component in sorted({r["component"] for r in rows}):
        members = sorted(
            [r for r in rows if r["component"] == component],
            key=lambda r: (r["rank"], r["name"]),
        )
        # Preserve the estimator's fixed reference when score rounding creates a tie.
        references = {r.get("referenceTeam") for r in members if r.get("referenceTeam")}
        selected_reference = next(iter(references)) if len(references) == 1 else None
        reference = next(
            (r for r in members if r["name"] == selected_reference), None
        ) or min(members, key=lambda r: r["scoreSeconds"])
        names = {r["name"] for r in members}
        old_reference = old_rows.get(reference["name"])
        entries = []
        for row in members:
            gap = number(row["scoreSeconds"] - reference["scoreSeconds"])
            gap_percent = (
                number(100 * gap / baseline, 6) if baseline and baseline > 0 else None
            )
            old = old_rows.get(row["name"])
            linked = (
                old and old_reference and old["component"] == old_reference["component"]
            )
            previous_percent = (
                number(
                    100
                    * (old["scoreSeconds"] - old_reference["scoreSeconds"])
                    / old_baseline,
                    6,
                )
                if linked and old_baseline and old_baseline > 0
                else None
            )
            old_names = {
                r["name"]
                for r in old_rows.values()
                if old and r["component"] == old["component"]
            }
            same_members = bool(
                linked
                and old_names == names
                and all(
                    old_rows[n].get("evidenceTier")
                    == next(r for r in members if r["name"] == n).get("evidenceTier")
                    and old_rows[n]["drivers"]
                    == next(r for r in members if r["name"] == n)["drivers"]
                    for n in names
                )
            )
            # Do not animate an apparent improvement caused by switching a
            # team's observed driver set or single-car/two-car evidence tier.
            changed_basis = bool(
                linked
                and (
                    old.get("evidenceTier") != row.get("evidenceTier")
                    or old["drivers"] != row["drivers"]
                    or old_reference.get("evidenceTier")
                    != reference.get("evidenceTier")
                    or old_reference["drivers"] != reference["drivers"]
                )
            )
            if changed_basis:
                previous_percent = None
            entries.append(
                {
                    "team": row["name"],
                    "evidenceTier": row.get("evidenceTier", "strict_matched"),
                    "strictMatched": row.get("strictMatched", True),
                    "driverLaps": row.get("driverLaps", {}),
                    "expectedDrivers": row.get("expectedDrivers", row["drivers"]),
                    "colour": current.get("colours", {}).get(row["name"]),
                    "rank": row["rank"],
                    "rankRange95": row.get("rankRange95"),
                    "gapSeconds": gap,
                    "gapPercent": gap_percent,
                    "gapInterval95": (
                        row.get("gapInterval95")
                        if row.get("referenceTeam") == reference["name"]
                        else None
                    ),
                    "previousRank": old["rank"] if linked else None,
                    "rankChange": old["rank"] - row["rank"] if same_members else None,
                    "previousGapPercentToReference": previous_percent,
                    "previousEquivalentGapSeconds": (
                        number(previous_percent / 100 * baseline)
                        if previous_percent is not None and baseline
                        else None
                    ),
                    "deltaGapPercentagePoints": (
                        number(gap_percent - previous_percent, 6)
                        if gap_percent is not None and previous_percent is not None
                        else None
                    ),
                    "comparisonNote": (
                        "Same ranked team set"
                        if same_members
                        else "Rank movement unavailable: membership, drivers, evidence tier or previous coverage changed"
                    ),
                    "windows": row["windows"],
                    "drivers": row["drivers"],
                    "rivals": row["rivals"],
                }
            )
        groups.append(
            {
                "component": component,
                "referenceTeam": reference["name"],
                "rows": entries,
            }
        )
    board = {
        "year": current["year"],
        "round": current["round"],
        "eventName": current["eventName"],
        "checkedAt": current["checkedAt"],
        "source": current["source"],
        "condition": current["condition"],
        "view": pace.get("view", "strict"),
        "diagnostics": pace.get(
            "diagnostics",
            current["pace"].get("coverageEstimate", {}).get("diagnostics", []),
        ),
        "validation": pace.get("validation"),
        "totalTeams": len({r["name"] for r in rows} | set(pace["unrankedTeams"])),
        "previousRound": previous["round"] if previous else None,
        "previousEvent": previous["eventName"] if previous else None,
        "normalisationLapSeconds": baseline,
        "groups": groups,
        "unrankedTeams": pace["unrankedTeams"],
        "coverage": pace["coverage"],
        "warnings": pace.get("warnings", []),
        "method": pace["method"],
        "limitations": pace["limitations"],
        "comparisonMethod": "Current gaps use seconds per lap against the lowest point estimate in each connected group. Changes compare the same reference team in both races, as a percentage of each race's median eligible lap time. Negative percentage-point change means a smaller relative gap, not a measured physical upgrade. Rank movement requires exactly the same ranked team set. Changes have no uncertainty interval and do not establish improvement independently of circuit, conditions or sampling.",
    }
    if view == "adjusted" and "coverageEstimate" in current["pace"]:
        board["strictBoard"] = build_board(current, previous, "strict")
    return board


class PerformanceService:
    def __init__(self, directory, *, enabled=True, clock=time.time):
        self.path = Path(directory) / "performance.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.enabled, self.clock = enabled, clock
        self.stop_event, self.wake = threading.Event(), threading.Event()
        self.thread = None
        with self.db() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS snapshots(year INTEGER, round INTEGER, condition TEXT, version TEXT, body TEXT, PRIMARY KEY(year,round,condition,version));
            CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, payload TEXT, priority INTEGER, state TEXT DEFAULT 'queued', due REAL DEFAULT 0, lease REAL DEFAULT 0, token TEXT, checked REAL, message TEXT, result TEXT);
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

    def enqueue(self, key, payload, priority):
        if self.enabled:
            with self.db() as db:
                db.execute(
                    "INSERT OR IGNORE INTO jobs(key,payload,priority) VALUES(?,?,?)",
                    (key, json.dumps(payload), priority),
                )
                db.execute(
                    "UPDATE jobs SET priority=MAX(priority,?) WHERE key=?",
                    (priority, key),
                )
            self.wake.set()

    def request(self, year, condition="slick", rd=None):
        key = f"{VERSION}:scan:{year}:{condition}:{rd or 'latest'}"
        self.enqueue(
            key,
            {"kind": "scan", "year": year, "condition": condition, "through": rd},
            1000,
        )
        return key

    def record(self, snapshot, guard=None):
        body = json.dumps(snapshot, allow_nan=False)
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            if guard:
                owner = db.execute(
                    "SELECT token FROM jobs WHERE key=?", (guard[0],)
                ).fetchone()
                if not owner or owner[0] != guard[1]:
                    return False
            db.execute(
                "INSERT OR REPLACE INTO snapshots VALUES(?,?,?,?,?)",
                (
                    snapshot["year"],
                    snapshot["round"],
                    snapshot["condition"],
                    VERSION,
                    body,
                ),
            )
            if not guard:
                key = f"{VERSION}:race:{snapshot['year']}:{snapshot['round']}:{snapshot['condition']}"
                db.execute(
                    "UPDATE jobs SET state='ready', due=MAX(due,?), checked=?, message='Pace evidence updated from the weekend analysis.' WHERE key=? AND lease<=?",
                    (self.clock() + ttl(snapshot), self.clock(), key, self.clock()),
                )
        return True

    def capture(self, year, rd, session, pace, guard=None):
        return self.record(make_snapshot(year, rd, session, pace, self.clock()), guard)

    def snapshots(self, year, condition):
        with self.db() as db:
            rows = db.execute(
                "SELECT round,body FROM snapshots WHERE year=? AND condition=? AND version=? ORDER BY round",
                (year, condition, VERSION),
            ).fetchall()
        return {r["round"]: json.loads(r["body"]) for r in rows}

    def job(self, key):
        with self.db() as db:
            row = db.execute("SELECT * FROM jobs WHERE key=?", (key,)).fetchone()
        return dict(row) if row else None

    def scan(self, year, condition, through):
        schedule = events.get_schedule(year, include_testing=False)
        now = pd.Timestamp(self.clock(), unit="s", tz="UTC")
        races = []
        for _, event in schedule.iterrows():
            rd = event.get("RoundNumber")
            if pd.isna(rd) or rd < 1 or (through is not None and rd > through):
                continue
            start = next(
                (
                    event.get(f"Session{i}DateUtc")
                    for i in range(1, 6)
                    if event.get(f"Session{i}") == "Race"
                ),
                None,
            )
            if start is None or pd.isna(start):
                # Date-only schedules get a conservative next-day boundary.
                start = pd.to_datetime(
                    event.get("EventDate"), utc=True, errors="coerce"
                )
                delay = pd.Timedelta(days=1)
            else:
                start = pd.to_datetime(start, utc=True, errors="coerce")
                delay = pd.Timedelta(minutes=150)
            if pd.isna(start) or start.year != year or start + delay > now:
                continue
            races.append({"round": int(rd), "eventName": str(event["EventName"])})
        races.sort(key=lambda r: r["round"])
        recent = races[-HISTORY:]
        cached = self.snapshots(year, condition)
        for race in reversed(recent):
            value = cached.get(race["round"])
            if value and self.clock() - pd.Timestamp(
                value["checkedAt"]
            ).timestamp() < ttl(value):
                continue
            self.enqueue(
                f"{VERSION}:race:{year}:{race['round']}:{condition}",
                {
                    "kind": "race",
                    "year": year,
                    "round": race["round"],
                    "condition": condition,
                },
                race["round"],
            )
        return recent

    def run_once(self):
        if not self.enabled:
            return False
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            job = db.execute(
                "SELECT * FROM jobs WHERE due<=? AND lease<=? ORDER BY priority DESC LIMIT 1",
                (self.clock(), self.clock()),
            ).fetchone()
            if not job:
                return False
            job = dict(job)
            token = uuid.uuid4().hex
            db.execute(
                "UPDATE jobs SET state='checking', lease=?, token=?, message='Refreshing cached race-pace evidence.' WHERE key=?",
                (self.clock() + 900, token, job["key"]),
            )
        payload = json.loads(job["payload"])
        result, state, message, delay = None, "ready", "Pace evidence updated.", 21600
        try:
            if payload["kind"] == "scan":
                result = self.scan(
                    payload["year"], payload["condition"], payload["through"]
                )
                delay, message = (
                    600,
                    "Eligible weekends discovered. Missing pace evidence is being prepared.",
                )
            else:
                session = load_session(payload["year"], payload["round"], "R")
                if not finished(session):
                    raise HTTPException(425, "Race results are still provisional")
                evidence = analyse(session, payload["condition"])
                snapshot = make_snapshot(
                    payload["year"], payload["round"], session, evidence, self.clock()
                )
                self.record(snapshot, (job["key"], token))
                delay = ttl(snapshot)
                if not evidence.get("coverageEstimate", evidence)["teamPace"]["rows"]:
                    message = "No connected team ranking under these conditions; coverage will be checked again."
        except Exception as exc:
            state, delay = "error", 600
            if isinstance(exc, HTTPException):
                message = str(exc.detail)
                state = "pending" if exc.status_code == 425 else "error"
                retry = (exc.headers or {}).get("Retry-After", "")
                if str(retry).isdigit():
                    delay = max(delay, min(int(retry), 3600))
            else:
                message = (
                    "Pace evidence could not be prepared; cached results are retained."
                )
                LOG.exception("Performance snapshot refresh failed")
        with self.db() as db:
            db.execute(
                "UPDATE jobs SET state=?, due=?, lease=0, token=NULL, checked=?, message=?, result=COALESCE(?,result) WHERE key=? AND token=?",
                (
                    state,
                    self.clock() + delay,
                    self.clock(),
                    message,
                    json.dumps(result) if result is not None else None,
                    job["key"],
                    token,
                ),
            )
        return True

    def response(self, year, condition="slick", rd=None):
        scan_key = self.request(year, condition, rd)
        scan_job = self.job(scan_key)
        planned = (
            json.loads(scan_job["result"]) if scan_job and scan_job["result"] else []
        )
        cached = self.snapshots(year, condition)
        if rd is not None:
            cached = {r: v for r, v in cached.items() if r <= rd}
        target = rd or (planned[-1]["round"] if planned else max(cached, default=None))
        shown = (
            rd
            if rd is not None
            else (target if target in cached else max(cached, default=None))
        )
        current = cached.get(shown)
        earlier = [
            r["round"] for r in planned if shown is not None and r["round"] < shown
        ]
        previous_round = max(earlier, default=None)
        previous = cached.get(previous_round)
        history = [
            {
                **r,
                "board": (
                    build_board(cached[r["round"]]) if r["round"] in cached else None
                ),
            }
            for r in planned
        ]
        race_job = (
            self.job(f"{VERSION}:race:{year}:{target}:{condition}") if target else None
        )
        job = race_job or scan_job or {}
        return {
            "year": year,
            "condition": condition,
            "requestedRound": target,
            "displayedRound": shown if current else None,
            "board": build_board(current, previous) if current else None,
            "history": history,
            "update": {
                "enabled": self.enabled,
                "state": job.get("state", "queued") if self.enabled else "disabled",
                "checkedAt": iso(job.get("checked")),
                "nextCheckAt": iso(max(job.get("due", 0), job.get("lease", 0))),
                "message": job.get("message")
                or "Preparing cached race-pace evidence in the background.",
                "showingEarlierRound": bool(current and target != shown),
            },
        }

    def _loop(self):
        next_scan = 0
        while not self.stop_event.is_set():
            try:
                if self.clock() >= next_scan:
                    self.request(
                        datetime.fromtimestamp(self.clock(), timezone.utc).year
                    )
                    next_scan = self.clock() + 600
                if self.run_once():
                    continue
            except Exception:
                LOG.exception("Performance background refresh paused")
            self.wake.wait(15)
            self.wake.clear()

    def start(self):
        if self.enabled and (self.thread is None or not self.thread.is_alive()):
            self.stop_event.clear()
            self.thread = threading.Thread(
                target=self._loop, name="performance-grid", daemon=True
            )
            self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.wake.set()
        if self.thread:
            self.thread.join(timeout=1)


_service, _lock = None, threading.Lock()


def get_performance():
    global _service
    with _lock:
        if _service is None:
            _service = PerformanceService(
                DATA_DIR,
                enabled=os.getenv("F1_PERFORMANCE_AUTO_REFRESH", "true").lower()
                not in ("false", "0", "no"),
            )
        return _service
