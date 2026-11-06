"""Live F1 sessions plus source-labelled cross-series event calendars."""

import json
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import fastf1
from fastapi import APIRouter, HTTPException

from ..services.data import iso, utc_now

router = APIRouter()


@lru_cache(maxsize=6)
def f1_calendar(year, bucket):
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    events = []
    for _, event in schedule.iterrows():
        for index in range(1, 6):
            name = event.get(f"Session{index}")
            start = iso(event.get(f"Session{index}DateUtc"))
            if not name or str(name) in ("None", "nan") or not start:
                continue
            events.append(
                {
                    "id": f'f1-{year}-{event["RoundNumber"]}-{index}',
                    "series": "f1",
                    "title": f'{event["EventName"]} — {name}',
                    "event": str(event["EventName"]),
                    "session": str(name),
                    "round": int(event["RoundNumber"]),
                    "start": start,
                    "end": None,
                    "dateOnly": False,
                    "location": str(event.get("Location", "")),
                    "source": "FastF1 event schedule",
                    "sourceUrl": "https://www.formula1.com/en/racing",
                    "verifiedAt": utc_now(),
                    "status": "published schedule",
                }
            )
    return events


@router.get("/f1/{year}")
def get_f1_calendar(year: int):
    try:
        events = f1_calendar(year, int(time.time() // 300))
        now = datetime.now(timezone.utc)
        future = [e for e in events if datetime.fromisoformat(e["start"]) > now]
        return {
            "events": events,
            "nextSession": min(future, key=lambda e: e["start"]) if future else None,
            "asOf": utc_now(),
            "year": year,
        }
    except Exception as exc:
        raise HTTPException(
            502, "F1 session schedule is temporarily unavailable"
        ) from exc


@router.get("/motorsport/{year}")
def motorsport(year: int):
    path = Path(__file__).resolve().parents[2] / "data" / f"motorsport-{year}.json"
    seed = (
        json.loads(path.read_text()) if path.exists() else {"events": [], "sources": []}
    )
    warnings = []
    try:
        events = f1_calendar(year, int(time.time() // 300)) + seed["events"]
    except Exception:
        events = seed["events"]
        warnings.append("Live F1 schedule unavailable; other series remain visible")
    return {
        "year": year,
        "events": sorted(events, key=lambda e: e["start"]),
        "sources": seed["sources"],
        "warnings": warnings,
        "note": "Other-series dates are a checked-in snapshot, not a live feed. Import a current .ics calendar in your browser for session times or later seasons. Date-only weekends stay in venue dates.",
    }
