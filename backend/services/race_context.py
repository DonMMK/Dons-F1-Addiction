"""Descriptive execution records, without assigning a luck or skill score."""

import re

import pandas as pd

from .data import number, optional_data


def execution_report(session, qualifying=None):
    if session is None:
        return {
            "drivers": [],
            "events": [],
            "note": "Race timing unavailable; no outcome explanation is inferred.",
        }
    pit = optional_data(session, "pit_data")
    if pit is not None and not pit.empty and "date" in pit:
        pit = pit.loc[
            pd.to_datetime(pit["date"], utc=True, errors="coerce", format="mixed")
            >= pd.to_datetime(session.date, utc=True)
        ]
    durations = (
        pd.to_numeric(pit.get("stop_duration"), errors="coerce")
        if pit is not None and "stop_duration" in pit
        else pd.Series(dtype=float)
    )
    benchmark = number(durations.loc[durations.gt(0)].median())
    drivers = []
    qpos = (
        {}
        if qualifying is None
        else dict(
            zip(qualifying.results["Abbreviation"], qualifying.results["Position"])
        )
    )
    for _, row in session.results.iterrows():
        stops = []
        if pit is not None and not pit.empty and "driver_number" in pit:
            for _, p in pit.loc[
                pit["driver_number"].astype(str).eq(str(row["DriverNumber"]))
            ].iterrows():
                duration = number(p.get("stop_duration"))
                if duration is not None and duration <= 0:
                    duration = None
                lane = number(p.get("lane_duration", p.get("pit_duration")))
                if duration is None and (lane is None or lane <= 0):
                    continue
                stops.append(
                    {
                        "lap": number(p.get("lap_number"), 0),
                        "stationarySeconds": duration,
                        "laneSeconds": lane,
                        "deltaToSessionMedian": (
                            number(duration - benchmark)
                            if duration is not None and benchmark is not None
                            else None
                        ),
                    }
                )
        drivers.append(
            {
                "driver": str(row["Abbreviation"]),
                "team": str(row["TeamName"]),
                "qualifying": number(qpos.get(row["Abbreviation"]), 0),
                "grid": number(row.get("GridPosition"), 0),
                "finish": number(row.get("Position"), 0),
                "status": str(row.get("Status", "Not supplied")),
                "points": number(row.get("Points")),
                "stops": stops,
            }
        )
    messages = optional_data(session, "race_control_messages")
    events = []
    if messages is not None:
        for _, row in messages.iterrows():
            message = str(row.get("message", row.get("Message", "")))
            if not re.search(
                r"SAFETY CAR|VSC|PENALTY|COLLISION|SESSION (ABORTED|SUSPENDED|STARTED)|RED FLAG",
                message,
                re.I,
            ):
                continue
            date = row.get("date", row.get("Time"))
            date = (
                pd.to_datetime(date, utc=True, errors="coerce")
                if not isinstance(date, pd.Timedelta)
                else pd.NaT
            )
            events.append(
                {
                    "date": date.isoformat() if pd.notna(date) else None,
                    "message": message[:500],
                    "lap": number(row.get("lap_number", row.get("Lap")), 0),
                }
            )
    return {
        "drivers": drivers,
        "events": events[:200],
        "pitMedianSeconds": benchmark,
        "note": "Stationary pit times and pit-lane duration are different measurements. Their session-median difference is not counterfactual race time lost. Flags, penalties and classification changes provide context; they do not quantify luck or isolate driver craft.",
    }
