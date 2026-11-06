"""One cache configuration and bounded, synchronized FastF1 session loading."""

import json
import os
import threading
import time
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import fastf1
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("F1_DATA_DIR", ROOT / "var"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
from . import f1_access
from . import openf1
from . import events
from .loading_errors import SessionDataError
from .results import load_results_session

CACHE_DIR = f1_access.configure_cache(ROOT, DATA_DIR)
f1_access.install_server_policy()
LOG = logging.getLogger(__name__)
_FAILURES = {}
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


def optional_data(session, name):
    try:
        return getattr(session, name, None)
    except Exception:
        return None


def _valid(session, telemetry=False):
    laps = optional_data(session, "laps")
    if (
        laps is None
        or laps.empty
        or "LapTime" not in laps
        or not laps["LapTime"].notna().any()
    ):
        return False
    if telemetry:
        for channel in ("car_data", "pos_data"):
            stream = optional_data(session, channel)
            if not stream or not any(
                frame is not None and not frame.empty for frame in stream.values()
            ):
                return False
    return True


def _try_load(session, telemetry):
    try:
        session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
    except SystemExit as exc:
        # FastF1 may call exit() on an unusable parsed cache. Keep the API alive.
        raise SessionDataError(
            "archive_cache_unusable",
            "FastF1 could not refresh an incompatible cached session. Authenticate and retry; existing cache files have been preserved.",
            502,
        ) from exc


@lru_cache(maxsize=8)
def _session(year, event, kind, telemetry, bucket, auth_fingerprint):
    f1_access.check_version()
    session = fastf1.get_session(year, event, kind)
    start = pd.Timestamp(session.date)
    if start.tzinfo is None:
        start = start.tz_localize("UTC")
    if start > pd.Timestamp.now(tz="UTC"):
        raise SessionDataError(
            "session_not_started", "This session has not started yet.", 425, 60
        )
    # Read existing parsed/HTTP caches without changing any other thread's mode
    # or triggering authentication. Failed/partial objects never enter this LRU.
    if f1_access.has_cached_timing(session, CACHE_DIR):
        try:
            with f1_access.cache_only():
                _try_load(session, telemetry)
            if _valid(session, telemetry):
                return _annotate(session)
        except (Exception, SystemExit):
            pass
    f1_access.ensure_authenticated()
    session = fastf1.get_session(year, event, kind)
    f1_access.probe_archive(session)
    _try_load(session, telemetry)
    if not _valid(session, telemetry):
        raise SessionDataError(
            "timing_data_incomplete",
            "The archive responded but the required lap timing or position/car data did not load. Retry later or run python -m backend.check_data with --timing for diagnostics.",
            502,
            30,
        )
    return _annotate(session)


def _annotate(session):
    session.data_source = "FastF1 timing archive / cache"
    session.data_warnings = []
    for key, label in (
        ("weather_data", "Weather"),
        ("race_control_messages", "Race-control messages"),
    ):
        frame = optional_data(session, key)
        if frame is None or frame.empty:
            session.data_warnings.append(
                f"{label} unavailable; lap timing remains usable. Missing channels are not reconstructed."
            )
    return session


def timing_provider():
    provider = os.environ.get("F1_TIMING_PROVIDER", "auto").strip().lower()
    if provider not in ("auto", "openf1", "fastf1"):
        raise SessionDataError(
            "timing_provider_invalid",
            "F1_TIMING_PROVIDER must be auto, openf1, or fastf1.",
            503,
        )
    return provider


@lru_cache(maxsize=8)
def _public_session(year, event, kind, provider, bucket):
    template = events.get_session(year, event, kind)
    if provider == "auto" and f1_access.has_cached_timing(template, CACHE_DIR):
        try:
            with f1_access.cache_only():
                _try_load(template, False)
            if _valid(template):
                return _annotate(template)
        except (Exception, SystemExit):
            pass
    return openf1.load_session(year, event, kind, DATA_DIR / "openf1", template)


def load_session(year, event, kind, telemetry=False, *, results_only=False):
    if results_only:
        return load_results_session(year, event, kind)
    provider = timing_provider()
    state = f1_access.auth_status()
    # CLI login after an error invalidates the short failure cache immediately.
    token_expiry = None
    if state["authenticated"]:
        token_expiry = f1_access._auth_module().token_manager.get_stored().expires_at
    fingerprint = (
        state["authenticated"],
        state["credentialsConfigured"],
        token_expiry,
        fastf1.__version__,
    )
    key = (year, event, kind, telemetry, fingerprint, provider)
    with SESSION_LOCK:
        failed = _FAILURES.get(key)
        if failed and failed[0] > time.monotonic():
            raise failed[1]
        try:
            bucket = int(time.time() // 300)
            if provider == "fastf1":
                result = _session(year, event, kind, telemetry, bucket, fingerprint)
            else:
                try:
                    result = _public_session(year, event, kind, provider, bucket)
                    # Cached native sessions might lack the requested telemetry.
                    if (
                        telemetry
                        and getattr(result, "data_provider", None) != "openf1"
                        and not _valid(result, True)
                    ):
                        result = openf1.load_session(
                            year, event, kind, DATA_DIR / "openf1"
                        )
                except SessionDataError:
                    if provider != "auto" or not (
                        state["authenticated"] or state["credentialsConfigured"]
                    ):
                        raise
                    result = _session(year, event, kind, telemetry, bucket, fingerprint)
            _FAILURES.pop(key, None)
            return result
        except SessionDataError as exc:
            if len(_FAILURES) > 64:
                _FAILURES.clear()
            _FAILURES[key] = (time.monotonic() + 15, exc)
            raise
        except Exception as exc:
            LOG.warning("Session timing load failed (%s)", type(exc).__name__)
            error = SessionDataError(
                "timing_load_failed",
                "The timing provider could not load this session. Run python -m backend.check_data with --timing for diagnostics.",
                502,
                15,
            )
            _FAILURES[key] = (time.monotonic() + 15, error)
            raise error from exc


def finished(session):
    if getattr(session, "data_provider", None) == "openf1":
        return session.completed
    if getattr(session, "published_results", False):
        return True
    status = optional_data(session, "session_status")
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
    if "OpenF1Eligible" in df.columns:
        df = df.loc[df["OpenF1Eligible"].eq(True)].copy()
        df["seconds"] = df["LapTime"].dt.total_seconds()
        return df.drop_duplicates(["Driver", "LapNumber"])
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
