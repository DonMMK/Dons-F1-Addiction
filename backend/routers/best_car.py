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

CACHE_DIR = Path(__file__).parent.parent.parent / "formula1-best-car" / "cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))

# ---------------------------------------------------------------------------
# ERA configurations – mirrors formula1-best-car/data_loader.py
# ---------------------------------------------------------------------------
ERAS = {
    "2020": {
        "name": "2020 – Mercedes W11 Era",
        "year": 2020,
        "primaryCar": {"team": "Mercedes", "car": "W11", "drivers": ["HAM", "BOT"], "color": "#00D2BE"},
        "competitors": [
            {"team": "Red Bull", "car": "RB16", "drivers": ["VER", "ALB"], "color": "#0600EF"},
            {"team": "Racing Point", "car": "RP20", "drivers": ["PER", "STR"], "color": "#F596C8"},
        ],
    },
    "2023": {
        "name": "2023 – Red Bull RB19 Era",
        "year": 2023,
        "primaryCar": {"team": "Red Bull Racing", "car": "RB19", "drivers": ["VER", "PER"], "color": "#3671C6"},
        "competitors": [
            {"team": "Mercedes", "car": "W14", "drivers": ["HAM", "RUS"], "color": "#27F4D2"},
            {"team": "Ferrari", "car": "SF-23", "drivers": ["LEC", "SAI"], "color": "#E8002D"},
        ],
    },
    "2025": {
        "name": "2025 – McLaren MCL39 Era",
        "year": 2025,
        "primaryCar": {"team": "McLaren", "car": "MCL39", "drivers": ["NOR", "PIA"], "color": "#FF8700"},
        "competitors": [
            {"team": "Mercedes", "car": "W16", "drivers": ["RUS", "ANT"], "color": "#27F4D2"},
            {"team": "Red Bull Racing", "car": "RB21", "drivers": ["VER", "LAW"], "color": "#3671C6"},
        ],
    },
}


def _load_session(year, race, session_type):
    session = fastf1.get_session(year, race, session_type)
    session.load(telemetry=True, laps=True, weather=True, messages=False)
    return session


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
        fastest_laps = []
        for driver in session.drivers:
            drv_laps = session.laps.pick_drivers(driver)
            if drv_laps.empty:
                continue
            fl = drv_laps.pick_fastest()
            if fl is not None and pd.notna(fl["LapTime"]):
                fastest_laps.append({
                    "driver": str(fl["Driver"]),
                    "team": str(fl.get("Team", "")),
                    "lapTime": fl["LapTime"].total_seconds(),
                })

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


@router.get("/season-progression/{era_key}")
def season_progression(era_key: str):
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

    progression = []
    for i, race_name in enumerate(races):
        try:
            session = _load_session(year, race_name, "Q")
            all_laps = []
            for drv in session.drivers:
                dl = session.laps.pick_drivers(drv)
                if dl.empty:
                    continue
                fl = dl.pick_fastest()
                if fl is not None and pd.notna(fl["LapTime"]):
                    all_laps.append({"driver": str(fl["Driver"]), "time": fl["LapTime"].total_seconds()})

            if not all_laps:
                continue

            all_laps.sort(key=lambda x: x["time"])
            leader_time = all_laps[0]["time"]

            best_gap = None
            for item in all_laps:
                if item["driver"] in drivers:
                    gap = item["time"] - leader_time
                    if best_gap is None or gap < best_gap:
                        best_gap = gap

            if best_gap is not None:
                progression.append({
                    "round": i + 1,
                    "race": race_name,
                    "gap": round(best_gap, 3),
                })
        except Exception:
            continue

    return {"eraKey": era_key, "team": era["primaryCar"]["team"], "progression": progression}


@router.get("/race-pace/{year}/{race}")
def race_pace(year: int, race: str):
    """Return average race pace per driver for a given race."""
    try:
        session = _load_session(year, race, "R")
        pace_data = []

        for drv in session.drivers:
            dl = session.laps.pick_drivers(drv).pick_accurate().pick_wo_box()
            if dl.empty:
                continue
            times = dl["LapTime"].dropna()
            if len(times) == 0:
                continue
            pace_data.append({
                "driver": str(drv),
                "team": str(dl.iloc[0]["Team"]),
                "avgLapTime": round(times.mean().total_seconds(), 3),
                "medianLapTime": round(times.median().total_seconds(), 3),
                "fastestLap": round(times.min().total_seconds(), 3),
                "laps": len(times),
            })

        pace_data.sort(key=lambda x: x["avgLapTime"])
        return {"year": year, "race": race, "pace": pace_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
