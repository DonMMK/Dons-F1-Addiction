"""One cache configuration and bounded, synchronized FastF1 session loading."""

import json
import os
import threading
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("F1_DATA_DIR", ROOT / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = DATA_DIR / "fastf1"
CACHE_DIR.mkdir(exist_ok=True)
fastf1.Cache.enable_cache(str(CACHE_DIR))
SESSION_LOCK = threading.RLock()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def iso(value):
    if value is None or pd.isna(value):
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return ts.tz_convert("UTC").isoformat()


def number(value, digits=4):
    try:
        value = float(value)
        return round(value, digits) if np.isfinite(value) else None
    except (ValueError, TypeError):
        return None


def seconds(value):
    return number(pd.Timedelta(value).total_seconds()) if pd.notna(value) else None


@lru_cache(maxsize=8)
def _session(year, event, kind, telemetry, bucket):
    session = fastf1.get_session(year, event, kind)
    # Messages supply deleted-lap information used by the empirical comparisons.
    session.load(telemetry=telemetry, weather=True, messages=True)
    return session


def load_session(year, event, kind, telemetry=False):
    # Refresh recent/upcoming sessions every five minutes, also after empty loads.
    import time

    with SESSION_LOCK:
        session = _session(year, event, kind, telemetry, int(time.time() // 300))
        try:
            if session.laps.empty:
                _session.cache_clear()
        except Exception:
            _session.cache_clear()
            raise ValueError(
                "Timing laps were not published or accessible from the upstream provider"
            )
        return session


def finished(session):
    status = getattr(session, "session_status", None)
    return (
        status is not None
        and not status.empty
        and status["Status"].astype(str).iloc[-1] in ("Finished", "Finalised")
    )


def clean_laps(laps):
    """Conservative green-flag sample. Traffic is NOT inferred from lap time."""
    df = laps.copy()
    if df.empty:
        return df
    required = {"LapTime", "IsAccurate", "TrackStatus", "PitInTime", "PitOutTime"}
    if not required.issubset(df.columns):
        return df.iloc[:0]
    mask = (
        df["LapTime"].notna()
        & (df["LapTime"].dt.total_seconds() > 0)
        & df["IsAccurate"].eq(True)
        & df["TrackStatus"].astype(str).eq("1")
        & df["PitInTime"].isna()
        & df["PitOutTime"].isna()
    )
    for column in ("Deleted", "FastF1Generated"):
        if column in df:
            mask &= ~df[column].fillna(False).astype(bool)
    df = df.loc[mask].copy()
    df["seconds"] = df["LapTime"].dt.total_seconds()
    return df.drop_duplicates(["Driver", "LapNumber"])


def json_safe(value):
    """Reject NaN/Infinity before caching or returning calculated payloads."""
    return json.loads(json.dumps(value, allow_nan=False))
