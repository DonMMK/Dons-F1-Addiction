"""
Common API routes - seasons, schedules, drivers.
"""

import fastf1
import pandas as pd
from fastapi import APIRouter, HTTPException
from pathlib import Path

router = APIRouter()

CACHE_DIR = Path(__file__).parent.parent.parent / "f1_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


@router.get("/seasons")
def get_seasons():
    """Return available F1 seasons (2018-2026)."""
    return {"seasons": list(range(2018, 2027))}


@router.get("/schedule/{year}")
def get_schedule(year: int):
    """Return full event schedule for a season."""
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=True)
        events = []
        testing_count = 0

        for _, row in schedule.iterrows():
            event_format = str(row.get("EventFormat", "")).lower()
            event_name = str(row.get("EventName", ""))

            if event_format == "testing" or "test" in event_name.lower():
                testing_count += 1
                events.append({
                    "roundNumber": 0,
                    "eventName": f"Pre-Season Testing {testing_count}",
                    "country": str(row.get("Country", "Unknown")),
                    "location": str(row.get("Location", "Unknown")),
                    "date": str(row.get("EventDate", ""))[:10],
                    "isTesting": True,
                    "testNumber": testing_count,
                })
                continue

            if pd.isna(row.get("RoundNumber")) or row.get("RoundNumber") == 0:
                continue

            events.append({
                "roundNumber": int(row["RoundNumber"]),
                "eventName": event_name,
                "country": str(row.get("Country", "Unknown")),
                "location": str(row.get("Location", event_name)),
                "date": str(row.get("EventDate", ""))[:10],
                "isTesting": False,
                "testNumber": 0,
            })

        return {"year": year, "events": events}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{year}/{round_number}")
def get_sessions(year: int, round_number: int):
    """Return available session types for a given event."""
    try:
        event = fastf1.get_event(year, round_number)
        sessions = []
        session_map = {
            "Practice 1": "FP1",
            "Practice 2": "FP2",
            "Practice 3": "FP3",
            "Qualifying": "Q",
            "Race": "R",
            "Sprint": "S",
            "Sprint Qualifying": "SQ",
            "Sprint Shootout": "SS",
        }
        for i in range(1, 6):
            session_name = event.get(f"Session{i}")
            if pd.notna(session_name) and session_name in session_map:
                sessions.append({
                    "key": session_map[session_name],
                    "name": session_name,
                })
        return {"sessions": sessions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/drivers/{year}/{round_number}/{session_type}")
def get_drivers(year: int, round_number: int, session_type: str):
    """Return drivers who participated in a session."""
    try:
        session = fastf1.get_session(year, round_number, session_type)
        session.load(telemetry=False, weather=False, messages=False)
        drivers = []
        for _, row in session.results.iterrows():
            drivers.append({
                "abbreviation": str(row.get("Abbreviation", "")),
                "fullName": str(row.get("FullName", "")),
                "team": str(row.get("TeamName", "")),
                "number": str(row.get("DriverNumber", "")),
            })
        return {"drivers": drivers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
