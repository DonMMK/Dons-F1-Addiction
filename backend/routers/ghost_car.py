"""
Ghost Car API routes.
Provides telemetry data, track layouts, and driver comparison data
for the React frontend to render interactive visualizations.
"""

import numpy as np
import pandas as pd
import fastf1
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from pathlib import Path

router = APIRouter()

CACHE_DIR = Path(__file__).parent.parent.parent / "formula1-ghost-car" / ".fastf1_cache"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))


# ---------------------------------------------------------------------------
# Helpers – reuse data_loader logic without importing the CLI module
# ---------------------------------------------------------------------------

def _load_session(year: int, round_number: int, session_type: str, test_number: int = None):
    """Load a FastF1 session with telemetry."""
    if test_number is not None:
        session_num = int(session_type[1]) if session_type.startswith("T") else 1
        session = fastf1.get_testing_session(year, test_number, session_num)
    else:
        session = fastf1.get_session(year, round_number, session_type)
    session.load(telemetry=True, weather=True, messages=False)
    return session


def _telemetry_to_dict(telemetry) -> dict:
    """Convert FastF1 telemetry DataFrame to JSON-safe dict of arrays."""
    return {
        "x": telemetry["X"].tolist(),
        "y": telemetry["Y"].tolist(),
        "speed": telemetry["Speed"].tolist(),
        "throttle": telemetry["Throttle"].tolist(),
        "brake": telemetry["Brake"].astype(float).tolist(),
        "gear": telemetry["nGear"].tolist(),
        "distance": telemetry["Distance"].tolist(),
        "time": telemetry["Time"].dt.total_seconds().tolist(),
        "drs": telemetry["DRS"].tolist(),
    }


def _format_lap_time(td) -> str:
    total = td.total_seconds()
    mins = int(total // 60)
    secs = total % 60
    return f"{mins}:{secs:06.3f}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/track/{year}/{round_number}/{session_type}")
def get_track_layout(year: int, round_number: int, session_type: str):
    """Return track X/Y coordinates from the fastest lap."""
    try:
        session = _load_session(year, round_number, session_type)
        fastest = session.laps.pick_fastest()
        if fastest is None:
            raise HTTPException(status_code=404, detail="No fastest lap found")
        tel = fastest.get_telemetry()
        if tel is None or tel.empty:
            raise HTTPException(status_code=404, detail="No telemetry data")

        circuit_info = {}
        try:
            ci = session.get_circuit_info()
            circuit_info = {
                "rotation": float(ci.rotation) if hasattr(ci, "rotation") else 0.0,
                "corners": ci.corners.to_dict("records") if hasattr(ci, "corners") else [],
            }
        except Exception:
            pass

        return {
            "track": {"x": tel["X"].tolist(), "y": tel["Y"].tolist()},
            "circuitInfo": circuit_info,
            "eventName": str(session.event.get("EventName", "")),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fastest-lap/{year}/{round_number}/{session_type}/{driver}")
def get_fastest_lap(year: int, round_number: int, session_type: str, driver: str):
    """Return telemetry for a driver's fastest lap."""
    try:
        session = _load_session(year, round_number, session_type)
        laps = session.laps.pick_drivers(driver)
        fastest = laps.pick_fastest()
        if fastest is None:
            raise HTTPException(status_code=404, detail=f"No fastest lap for {driver}")

        tel = fastest.get_telemetry()
        if tel is None or tel.empty:
            raise HTTPException(status_code=404, detail="No telemetry")

        lap_time = fastest["LapTime"]
        return {
            "driver": driver,
            "team": str(fastest.get("Team", "Unknown")),
            "lapTime": _format_lap_time(lap_time),
            "lapTimeSeconds": lap_time.total_seconds(),
            "compound": str(fastest.get("Compound", "Unknown")),
            "telemetry": _telemetry_to_dict(tel),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare/{year}/{round_number}/{session_type}/{driver1}/{driver2}")
def compare_drivers(year: int, round_number: int, session_type: str, driver1: str, driver2: str):
    """Compare fastest laps of two drivers – returns telemetry for both."""
    try:
        session = _load_session(year, round_number, session_type)

        def _get_lap(drv):
            laps = session.laps.pick_drivers(drv)
            fastest = laps.pick_fastest()
            if fastest is None:
                raise HTTPException(status_code=404, detail=f"No lap for {drv}")
            tel = fastest.get_telemetry()
            if tel is None or tel.empty:
                raise HTTPException(status_code=404, detail=f"No telemetry for {drv}")
            return fastest, tel

        lap1, tel1 = _get_lap(driver1)
        lap2, tel2 = _get_lap(driver2)

        # Interpolate onto common distance axis for delta chart
        max_dist = min(tel1["Distance"].max(), tel2["Distance"].max())
        dist_pts = np.linspace(0, max_dist, 500).tolist()
        speed1_interp = np.interp(dist_pts, tel1["Distance"].values, tel1["Speed"].values).tolist()
        speed2_interp = np.interp(dist_pts, tel2["Distance"].values, tel2["Speed"].values).tolist()
        delta = [round(s1 - s2, 2) for s1, s2 in zip(speed1_interp, speed2_interp)]

        return {
            "eventName": str(session.event.get("EventName", "")),
            "driver1": {
                "abbreviation": driver1,
                "team": str(lap1.get("Team", "")),
                "lapTime": _format_lap_time(lap1["LapTime"]),
                "lapTimeSeconds": lap1["LapTime"].total_seconds(),
                "compound": str(lap1.get("Compound", "")),
                "telemetry": _telemetry_to_dict(tel1),
            },
            "driver2": {
                "abbreviation": driver2,
                "team": str(lap2.get("Team", "")),
                "lapTime": _format_lap_time(lap2["LapTime"]),
                "lapTimeSeconds": lap2["LapTime"].total_seconds(),
                "compound": str(lap2.get("Compound", "")),
                "telemetry": _telemetry_to_dict(tel2),
            },
            "comparison": {
                "distance": dist_pts,
                "speed1": speed1_interp,
                "speed2": speed2_interp,
                "speedDelta": delta,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather/{year}/{round_number}/{session_type}")
def get_weather(year: int, round_number: int, session_type: str):
    """Return session weather data."""
    try:
        session = _load_session(year, round_number, session_type)
        wd = session.weather_data
        if wd is None or wd.empty:
            return {"weather": None}
        return {
            "weather": {
                "airTemp": round(float(wd["AirTemp"].mean()), 1),
                "trackTemp": round(float(wd["TrackTemp"].mean()), 1),
                "humidity": round(float(wd["Humidity"].mean()), 1),
                "windSpeed": round(float(wd["WindSpeed"].mean()), 1),
                "rainfall": bool(wd["Rainfall"].any()),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
