"""Published classifications via Jolpica, independent of protected timing streams."""

from dataclasses import dataclass, field
from functools import lru_cache
import time

import fastf1
from fastf1.ergast import Ergast
import pandas as pd

from .loading_errors import SessionDataError
from . import events


@dataclass
class ResultsSession:
    event: object
    date: object
    name: str
    results: pd.DataFrame
    published_results: bool = True
    data_source: str = "Jolpica-F1 published classification"
    data_warnings: list = field(default_factory=list)


@lru_cache(maxsize=64)
def _load(year, event_key, kind, bucket):
    template = events.get_session(year, event_key, kind)
    now = pd.Timestamp.now(tz="UTC")
    start = pd.Timestamp(template.date)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    if start > now:
        raise SessionDataError(
            "session_not_started", "This session has not started yet.", 425, 60
        )
    client = Ergast()
    method = {
        "Q": client.get_qualifying_results,
        "R": client.get_race_results,
        "S": client.get_sprint_results,
    }.get(kind)
    if method is None:
        raise SessionDataError(
            "classification_not_supported",
            "This session needs raw timing data rather than a public classification.",
            422,
        )
    try:
        response = method(
            season=year, round=int(template.event["RoundNumber"]), limit=100
        )
    except Exception as exc:
        raise SessionDataError(
            "classification_provider_error",
            "Published results could not be loaded from Jolpica. Retry shortly.",
            502,
            20,
        ) from exc
    if not response.content or response.content[0].empty:
        raise SessionDataError(
            "classification_not_published",
            "The session classification has not been published by Jolpica yet.",
            425,
            60,
        )
    frame = (
        response.content[0]
        .copy()
        .rename(
            columns={
                "number": "DriverNumber",
                "driverCode": "Abbreviation",
                "givenName": "FirstName",
                "familyName": "LastName",
                "constructorName": "TeamName",
                "position": "Position",
                "grid": "GridPosition",
                "status": "Status",
                "points": "Points",
                "laps": "Laps",
                "totalRaceTime": "Time",
            }
        )
    )
    required = {"DriverNumber", "Abbreviation", "TeamName", "Position"}
    if not required.issubset(frame.columns):
        raise SessionDataError(
            "classification_incomplete",
            "Published results are missing required driver or position fields.",
            502,
        )
    frame["DriverNumber"] = frame["DriverNumber"].astype(str)
    frame["FullName"] = frame.get("FirstName", "") + " " + frame.get("LastName", "")
    for column in ("Q1", "Q2", "Q3"):
        frame[column] = (
            pd.to_timedelta(frame[column].astype(object), errors="coerce")
            if column in frame
            else pd.Series(pd.NaT, index=frame.index, dtype="timedelta64[ns]")
        )
    frame["Position"] = pd.to_numeric(frame["Position"], errors="coerce")
    frame = frame.dropna(subset=["Position", "Abbreviation"]).sort_values("Position")
    if frame.empty:
        raise SessionDataError(
            "classification_incomplete",
            "No classified driver positions are available.",
            425,
            60,
        )
    if kind == "Q" and not frame[["Q1", "Q2", "Q3"]].notna().any().any():
        raise SessionDataError(
            "qualifying_times_unavailable",
            "Qualifying positions are published but timed laps are not available yet.",
            425,
            60,
        )
    return ResultsSession(
        template.event,
        template.date,
        template.name,
        frame.set_index("DriverNumber", drop=False),
    )


def load_results_session(year, event, kind):
    return _load(year, event, kind, int(time.time() // 300))
