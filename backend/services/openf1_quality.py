"""Conservative OpenF1 screening, deliberately distinct from FastF1 accuracy.

Race-control screening is not a complete track-status or deleted-lap feed.
Unknown status, missing sectors, and missing pit coverage fail closed.
"""

import re

import numpy as np
import pandas as pd


def timestamp(value):
    return pd.to_datetime(value, utc=True, errors="coerce")


def numeric(value):
    try:
        value = float(value)
        return value if np.isfinite(value) else np.nan
    except (TypeError, ValueError):
        return np.nan


def control_in_window(rows, start, end):
    # Some upstream responses include messages from another day/session.
    return sorted(
        [
            r
            for r in rows
            if start - pd.Timedelta(hours=2)
            <= timestamp(r.get("date"))
            <= end + pd.Timedelta(hours=6)
        ],
        key=lambda r: timestamp(r["date"]),
    )


def screened_intervals(messages, end):
    """Intervals observed running without an outstanding hazard message.

    Sector CLEAR cannot clear a safety car or red flag. SC IN THIS LAP / LIGHTS
    OFF is not a green restart. Some usable laps will intentionally be excluded.
    """
    known, stopped, safety, sectors, track_flag = False, False, False, set(), False
    intervals, since = [], None
    for r in messages:
        date = timestamp(r.get("date"))
        message = str(r.get("message") or "").upper()
        flag = str(r.get("flag") or "").upper()
        category = str(r.get("category") or "")
        scope = str(r.get("scope") or "").upper()
        if since is not None:
            intervals.append((since, date))
            since = None
        if category == "SessionStatus":
            if message == "SESSION STARTED":
                known, stopped = True, False
            elif message in (
                "SESSION ABORTED",
                "SESSION SUSPENDED",
                "SESSION FINISHED",
                "SESSION ENDED",
            ):
                stopped = True
        if category == "SafetyCar" and "DEPLOYED" in message:
            safety = True
        if flag == "RED":
            stopped = True
        elif flag in ("YELLOW", "DOUBLE YELLOW"):
            if scope == "SECTOR" and r.get("sector") is not None:
                sectors.add(str(r["sector"]))
            else:
                track_flag = True
        elif flag in ("GREEN", "CLEAR"):
            if scope == "SECTOR" and r.get("sector") is not None:
                sectors.discard(str(r["sector"]))
            elif scope == "TRACK":
                track_flag = False
                if flag == "GREEN":
                    known, stopped, safety = True, False, False
                else:
                    sectors.clear()
        if known and not (stopped or safety or sectors or track_flag):
            since = date
    if since is not None:
        intervals.append((since, end + pd.Timedelta(hours=6)))
    # Merge adjacent good intervals; informational messages shouldn't split laps.
    merged = []
    for a, b in intervals:
        if merged and merged[-1][1] == a:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def deleted_laps(messages, laps):
    deleted, unknown_drivers = set(), set()
    for row in messages:
        message = str(row.get("message") or "").upper()
        if "DELETED" not in message:
            continue
        car = re.search(r"\bCAR\s+(\d+)\b", message)
        driver = str(car.group(1)) if car else row.get("driver_number")
        if driver is None:
            # A deletion which cannot be assigned invalidates the sample,
            # rather than silently accepting potentially deleted laps.
            unknown_drivers.update(laps["DriverNumber"].unique())
            continue
        driver = str(driver)
        lap = re.search(r"\bLAP\s+(\d+)\b", message)
        if lap:
            # The structured lap_number is often the leader's lap at message
            # publication, not the affected driver's deleted lap.
            deleted.add((driver, int(lap.group(1))))
            continue
        clock = re.search(r"\bTIME\s+(\d+):(\d{2}\.\d+)\b", message)
        if clock:
            seconds = int(clock.group(1)) * 60 + float(clock.group(2))
            match = laps.loc[
                laps["DriverNumber"].eq(driver)
                & (laps["LapTime"].dt.total_seconds() - seconds).abs().lt(0.001)
            ]
            if len(match) == 1:
                deleted.add((driver, int(match.iloc[0]["LapNumber"])))
                continue
        unknown_drivers.add(driver)
    return deleted, unknown_drivers


def screen_laps(laps, messages, end, pit_available):
    intervals = screened_intervals(messages, end)
    deleted, unknown_drivers = deleted_laps(messages, laps)
    valid, green = [], []
    for row in laps.itertuples():
        start, finish = row.LapStartDate, row.LapStartDate + row.LapTime
        # Pad approximate lap boundaries to exclude nearby hazard transitions.
        screened = any(
            a <= start - pd.Timedelta(seconds=1)
            and finish + pd.Timedelta(seconds=1) <= b
            for a, b in intervals
        )
        green.append(screened)
        sectors = [row.Sector1Time, row.Sector2Time, row.Sector3Time]
        consistent = all(pd.notna(s) and s > pd.Timedelta(0) for s in sectors)
        consistent = (
            consistent
            and pd.notna(row.LapTime)
            and abs((sum(sectors, pd.Timedelta(0)) - row.LapTime).total_seconds())
            <= 0.02
        )
        valid.append(
            bool(
                pit_available
                and consistent
                and pd.notna(start)
                and row.LapNumber > 1
                and row.OpenF1PitOutKnown
                and pd.isna(row.PitInTime)
                and pd.isna(row.PitOutTime)
                and row.DriverNumber not in unknown_drivers
                and (row.DriverNumber, int(row.LapNumber)) not in deleted
            )
        )
    laps["OpenF1Valid"] = valid
    laps["OpenF1Screened"] = green
    laps["OpenF1Eligible"] = laps["OpenF1Valid"] & laps["OpenF1Screened"]
    return laps
