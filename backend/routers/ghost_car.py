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

from ..services.data import load_session, CACHE_DIR, optional_data, number
from ..services.openf1 import TELEMETRY_NOTE


def _provenance(session):
    warnings = list(getattr(session, "data_warnings", []))
    if getattr(session, "data_provider", None) == "openf1":
        warnings.append(TELEMETRY_NOTE)
    return {
        "dataSource": getattr(session, "data_source", "FastF1"),
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Helpers – reuse data_loader logic without importing the CLI module
# ---------------------------------------------------------------------------


def _load_session(year, round_number, session_type):
    return load_session(year, round_number, session_type, telemetry=True)


def _telemetry_to_dict(telemetry) -> dict:
    """Convert FastF1 telemetry DataFrame to JSON-safe dict of arrays."""
    required = [
        "X",
        "Y",
        "Speed",
        "Throttle",
        "Brake",
        "nGear",
        "Distance",
        "Time",
    ]
    telemetry = (
        telemetry.dropna(subset=required).sort_values("Time").drop_duplicates("Time")
    )
    if len(telemetry) < 2:
        raise HTTPException(404, "Not enough finite telemetry samples")
    result = {
        key: telemetry[column].astype(float).tolist()
        for key, column in {
            "x": "X",
            "y": "Y",
            "speed": "Speed",
            "throttle": "Throttle",
            "brake": "Brake",
            "gear": "nGear",
            "distance": "Distance",
        }.items()
    }
    result["drs"] = [
        number(v)
        for v in telemetry.get("DRS", pd.Series(np.nan, index=telemetry.index))
    ]
    result["time"] = telemetry["Time"].dt.total_seconds().tolist()
    if not all(
        v is None or np.isfinite(v) for values in result.values() for v in values
    ):
        raise HTTPException(404, "Telemetry contains non-finite values")
    return result


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
                "corners": (
                    ci.corners.to_dict("records") if hasattr(ci, "corners") else []
                ),
            }
        except Exception:
            pass

        return {
            **_provenance(session),
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
            **_provenance(session),
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
def compare_drivers(
    year: int, round_number: int, session_type: str, driver1: str, driver2: str
):
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

        # Sanitize before interpolation as well as before serialization.
        clean1, clean2 = _telemetry_to_dict(tel1), _telemetry_to_dict(tel2)
        max_dist = min(max(clean1["distance"]), max(clean2["distance"]))
        dist_pts = np.linspace(
            max(min(clean1["distance"]), min(clean2["distance"])), max_dist, 500
        ).tolist()
        comparison = {"distance": dist_pts}
        for index, clean in enumerate((clean1, clean2), 1):
            order = np.argsort(clean["distance"])
            dist = np.asarray(clean["distance"])[order]
            for channel in ("speed", "throttle", "brake", "gear", "drs", "time"):
                values = np.asarray(clean[channel])[order]
                if channel == "time":
                    values = values - values[0]
                if channel in ("brake", "gear", "drs"):
                    indices = np.clip(
                        np.searchsorted(dist, dist_pts, side="right") - 1,
                        0,
                        len(dist) - 1,
                    )
                    aligned = values[indices].tolist()
                else:
                    aligned = np.interp(dist_pts, dist, values).tolist()
                comparison[f"{channel}{index}"] = aligned
        comparison["speedDelta"] = [
            round(a - b, 3) for a, b in zip(comparison["speed1"], comparison["speed2"])
        ]
        comparison["timeDelta"] = [
            round(a - b, 4) for a, b in zip(comparison["time1"], comparison["time2"])
        ]

        return {
            **_provenance(session),
            "eventName": str(session.event.get("EventName", "")),
            "driver1": {
                "abbreviation": driver1,
                "team": str(lap1.get("Team", "")),
                "lapTime": _format_lap_time(lap1["LapTime"]),
                "lapTimeSeconds": lap1["LapTime"].total_seconds(),
                "compound": str(lap1.get("Compound", "")),
                "telemetry": clean1,
            },
            "driver2": {
                "abbreviation": driver2,
                "team": str(lap2.get("Team", "")),
                "lapTime": _format_lap_time(lap2["LapTime"]),
                "lapTimeSeconds": lap2["LapTime"].total_seconds(),
                "compound": str(lap2.get("Compound", "")),
                "telemetry": clean2,
            },
            "comparison": comparison,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/weather/{year}/{round_number}/{session_type}")
def get_weather(year: int, round_number: int, session_type: str):
    """Return session weather data."""
    try:
        session = load_session(year, round_number, session_type)
        wd = optional_data(session, "weather_data")
        if wd is None or wd.empty:
            return {"weather": None}
        return {
            "weather": {
                "airTemp": number(wd["AirTemp"].mean(), 1),
                "trackTemp": number(wd["TrackTemp"].mean(), 1),
                "humidity": number(wd["Humidity"].mean(), 1),
                "windSpeed": number(wd["WindSpeed"].mean(), 1),
                "rainfall": bool(wd["Rainfall"].dropna().gt(0).any()),
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
