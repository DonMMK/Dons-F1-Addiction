"""
Best Car Analysis API routes.
Provides car dominance metrics, performance comparisons, and season progression.
"""

import numpy as np
import pandas as pd
import fastf1
from fastapi import APIRouter, HTTPException
from typing import Optional, List
from pathlib import Path

router = APIRouter()

from ..services.data import load_session, CACHE_DIR

# ---------------------------------------------------------------------------
# ERA configurations – mirrors formula1-best-car/data_loader.py
# ---------------------------------------------------------------------------
ERAS = {
    "2020": {
        "name": "2020 – Mercedes W11 Era",
        "year": 2020,
        "primaryCar": {
            "team": "Mercedes",
            "car": "W11",
            "drivers": ["HAM", "BOT"],
            "color": "#00D2BE",
        },
        "competitors": [
            {
                "team": "Red Bull",
                "car": "RB16",
                "drivers": ["VER", "ALB"],
                "color": "#0600EF",
            },
            {
                "team": "Racing Point",
                "car": "RP20",
                "drivers": ["PER", "STR"],
                "color": "#F596C8",
            },
        ],
    },
    "2023": {
        "name": "2023 – Red Bull RB19 Era",
        "year": 2023,
        "primaryCar": {
            "team": "Red Bull Racing",
            "car": "RB19",
            "drivers": ["VER", "PER"],
            "color": "#3671C6",
        },
        "competitors": [
            {
                "team": "Mercedes",
                "car": "W14",
                "drivers": ["HAM", "RUS"],
                "color": "#27F4D2",
            },
            {
                "team": "Ferrari",
                "car": "SF-23",
                "drivers": ["LEC", "SAI"],
                "color": "#E8002D",
            },
        ],
    },
    "2025": {
        "name": "2025 – McLaren MCL39 Era",
        "year": 2025,
        "primaryCar": {
            "team": "McLaren",
            "car": "MCL39",
            "drivers": ["NOR", "PIA"],
            "color": "#FF8700",
        },
        "competitors": [
            {
                "team": "Mercedes",
                "car": "W16",
                "drivers": ["RUS", "ANT"],
                "color": "#27F4D2",
            },
            {
                "team": "Red Bull Racing",
                "car": "RB21",
                "drivers": ["VER", "LAW"],
                "color": "#3671C6",
            },
        ],
    },
}


def _load_session(year, race, session_type):
    return load_session(year, race, session_type)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/eras")
def list_eras():
    """Return available comparison eras."""
    return {"eras": {k: v["name"] for k, v in ERAS.items()}}


@router.get("/era/{era_key}")
def get_era_detail(era_key: str):
    """Return full config for an era."""
    if era_key not in ERAS:
        raise HTTPException(status_code=404, detail=f"Era '{era_key}' not found")
    return ERAS[era_key]


@router.get("/gap-to-leader/{year}/{race}")
def gap_to_leader(year: int, race: str):
    """Qualifying gap-to-leader for a specific race."""
    try:
        session = _load_session(year, race, "Q")
        # Q1 is a common timing segment; do not compare a Q1 lap to a Q3 lap.
        fastest_laps = []
        for _, row in session.results.iterrows():
            if pd.notna(row.get("Q1")):
                fastest_laps.append(
                    {
                        "driver": str(row["Abbreviation"]),
                        "team": str(row["TeamName"]),
                        "lapTime": pd.Timedelta(row["Q1"]).total_seconds(),
                    }
                )

        if not fastest_laps:
            return {"gaps": []}

        fastest_laps.sort(key=lambda x: x["lapTime"])
        leader = fastest_laps[0]["lapTime"]
        for item in fastest_laps:
            item["gap"] = round(item["lapTime"] - leader, 3)
            item["gapPercent"] = round((item["gap"] / leader) * 100, 3) if leader else 0

        return {"race": race, "year": year, "gaps": fastest_laps}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _season_progression(era_key: str, progress=None):
    """
    Track qualifying gap-to-leader across the season for the primary team.
    Returns list of {round, race, gap} entries.
    """
    if era_key not in ERAS:
        raise HTTPException(status_code=404, detail="Era not found")

    era = ERAS[era_key]
    year = era["year"]
    drivers = era["primaryCar"]["drivers"]

    try:
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule["EventFormat"] != "testing"]["EventName"].tolist()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    progression, unavailable = [], []
    for i, race_name in enumerate(races):
        if progress:
            progress(i, len(races))
        try:
            session = _load_session(year, race_name, "Q")
            rows = session.results.dropna(subset=["Q1"])
            primary = rows[rows["TeamName"].eq(era["primaryCar"]["team"])]
            rivals = rows[~rows["TeamName"].eq(era["primaryCar"]["team"])]
            if primary.empty or rivals.empty:
                unavailable.append(race_name)
                continue
            p = primary["Q1"].min().total_seconds()
            r = rivals["Q1"].min().total_seconds()
            progression.append(
                {
                    "round": int(session.event["RoundNumber"]),
                    "race": race_name,
                    "gap": round(p - r, 4),
                    "gapPercent": round(100 * (p / r - 1), 4),
                }
            )
        except Exception:
            unavailable.append(race_name)
    if progress:
        progress(len(races), len(races))
    return {
        "eraKey": era_key,
        "team": era["primaryCar"]["team"],
        "progression": progression,
        "unavailable": unavailable,
        "method": "Best primary driver minus fastest other-team Q1 time; negative is an advantage. Q1 controls segment, not track conditions. Percent gaps improve scale comparability, not causal attribution.",
    }


@router.get("/race-pace/{year}/{race}")
def race_pace(year: int, race: str):
    """Return average race pace per driver for a given race."""
    try:
        session = _load_session(year, race, "R")
        pace_data = []

        for drv in session.drivers:
            from ..services.data import clean_laps

            dl = clean_laps(session.laps.pick_drivers(drv))
            if dl.empty:
                continue
            times = dl["LapTime"].dropna()
            if len(times) == 0:
                continue
            pace_data.append(
                {
                    "driver": str(drv),
                    "team": str(dl.iloc[0]["Team"]),
                    "avgLapTime": round(times.mean().total_seconds(), 3),
                    "medianLapTime": round(times.median().total_seconds(), 3),
                    "fastestLap": round(times.min().total_seconds(), 3),
                    "laps": len(times),
                }
            )

        pace_data.sort(key=lambda x: x["avgLapTime"])
        return {"year": year, "race": race, "pace": pace_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/season-progression/{era_key}")
def season_progression(era_key: str):
    """Compatibility endpoint; web UI uses the progress-reporting job instead."""
    return _season_progression(era_key)


@router.post("/season-jobs/{era_key}")
def start_season(era_key: str):
    from ..services import jobs

    if era_key not in ERAS:
        raise HTTPException(404, "Era not found")
    try:
        return jobs.start(
            era_key, lambda progress: _season_progression(era_key, progress)
        )
    except ValueError as exc:
        raise HTTPException(429, str(exc)) from exc


@router.get("/season-jobs/status/{job_id}")
def season_status(job_id: str):
    from ..services import jobs

    result = jobs.get(job_id)
    if result is None:
        raise HTTPException(
            404, "Analysis job expired or server restarted; reload the page"
        )
    return result
