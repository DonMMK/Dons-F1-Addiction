"""Free historical laps and lazy per-lap telemetry, in the dashboard's schema.

This implements only the FastF1-like operations used by this application. It
does not claim to recreate FastF1's accuracy flags or qualifying phase timing.
"""

from functools import lru_cache

import fastf1
from fastf1.core import Lap, Laps
import numpy as np
import pandas as pd

from .loading_errors import SessionDataError
from .openf1_client import OpenF1Client
from .openf1_quality import control_in_window, numeric, screen_laps, timestamp
from .results import load_results_session
from . import events

SESSION_NAMES = {
    "FP1": "Practice 1",
    "FP2": "Practice 2",
    "FP3": "Practice 3",
    "Q": "Qualifying",
    "R": "Race",
    "S": "Sprint",
    "SQ": "Sprint Qualifying",
    "SS": "Sprint Qualifying",
}
QUALITY_NOTE = (
    "OpenF1 screening differs from FastF1 IsAccurate: positive lap/sector times "
    "must agree within 0.02s; opening, pit, reported deleted and race-control "
    "hazard laps are excluded. Unknown coverage is excluded. Approximate lap "
    "boundaries, unreported incidents/deletions and traffic remain limitations. "
    "Replay selects the fastest remaining screened lap, which may differ from the official fastest lap."
)
TELEMETRY_NOTE = (
    "OpenF1 car positions are approximate (~3.7 Hz), not surveyed GPS. Position "
    "samples are matched within 0.5s of recorded car data. Distance is estimated "
    "by integrating speed, and lap start timestamps are approximate; replay and "
    "distance-aligned time deltas are illustrative. Brake is normalized to on/off. "
    "Missing DRS values (including 2026 aero data) are shown as gaps, not zero."
)


@lru_cache(maxsize=4)
def client(cache_dir):
    return OpenF1Client(cache_dir)


def add_public_race_observations(session, cache_dir):
    """Attach public gap/pit observations to a native timing-cache session."""
    if getattr(session, "data_provider", None) == "openf1" or hasattr(
        session, "intervals"
    ):
        return
    from fastf1.core import Session

    if not isinstance(session, Session) or session.name != "Race":
        return
    session.intervals = pd.DataFrame()
    try:
        api = client(str(cache_dir))
        info = resolve_session(api, pd.Timestamp(session.date).year, session, "R")
        params = {"session_key": info["session_key"]}
        session.intervals = pd.DataFrame(api.get("intervals", params))
        session.pit_data = pd.DataFrame(
            _optional(api, "pit", params, session.data_warnings) or []
        )
    except SessionDataError as exc:
        session.data_warnings.append(
            f"Public interval coverage unavailable: {exc.detail}"
        )


def resolve_session(api, year, template, kind):
    if year < 2023:
        raise SessionDataError(
            "openf1_year_unsupported",
            "OpenF1 historical timing starts in 2023. Earlier seasons require an existing FastF1 cache or optional archive access.",
            422,
        )
    name = SESSION_NAMES.get(kind)
    if name is None:
        raise SessionDataError(
            "openf1_session_unsupported", "Unsupported historical session type.", 422
        )
    start = timestamp(template.date)
    if pd.isna(start):
        raise SessionDataError(
            "session_date_unavailable",
            "No reliable session start date is available.",
            502,
        )
    if start > pd.Timestamp.now(tz="UTC"):
        raise SessionDataError(
            "session_not_started", "This session has not started yet.", 425, 60
        )
    query = {"year": year, "session_name": name}
    country = template.event.get("Country")
    if country and pd.notna(country):
        query["country_name"] = str(country)
    sessions = api.get("sessions", query, ttl=3600)
    candidates = [
        r
        for r in sessions
        if r.get("session_name") == name
        and abs(timestamp(r.get("date_start")) - start) < pd.Timedelta(hours=12)
    ]
    if len(candidates) != 1:
        raise SessionDataError(
            "openf1_session_unavailable",
            "OpenF1 has no unique matching session. It may not be published yet; no nearby race has been substituted.",
            425,
            60,
        )
    info = candidates[0]
    if info.get("is_cancelled"):
        raise SessionDataError("session_cancelled", "This session was cancelled.", 422)
    end = timestamp(info.get("date_end"))
    if pd.isna(end) or end + pd.Timedelta(minutes=30) >= pd.Timestamp.now(tz="UTC"):
        raise SessionDataError(
            "openf1_historical_pending",
            "Free OpenF1 data is available outside the live window. Retry at least 30 minutes after the session ends.",
            425,
            60,
        )
    return info


class HistoricalLap(Lap):
    def get_telemetry(self, **kwargs):
        return self.session.telemetry(self)


class HistoricalLaps(Laps):
    @property
    def _constructor_sliced_horizontal(self):
        return HistoricalLap

    def pick_accurate(self):
        # A compatibility selector, not an assertion of FastF1 IsAccurate.
        return self.loc[self["OpenF1Valid"]]

    def pick_track_status(self, status, how="equals"):
        if status == "1" and how == "equals":
            return self.loc[self["OpenF1Screened"]]
        return super().pick_track_status(status, how)

    def pick_fastest(self, only_by_time=False):
        sample = self.loc[self["OpenF1Eligible"] & self["LapTime"].notna()]
        return None if sample.empty else sample.loc[sample["LapTime"].idxmin()]


class HistoricalSession:
    data_provider = "openf1"
    data_source = "OpenF1 historical timing (public, 2023+)"

    def __init__(self, api, template, info):
        self.api, self.info = api, info
        self.event = template.event
        self.name = info["session_name"]
        # Existing legacy adapters compare naive UTC FastF1 session dates.
        self.date = timestamp(info["date_start"]).tz_localize(None)
        self.data_warnings = [QUALITY_NOTE]
        self.completed = False
        self.qualifying_classification = False
        self.classification_source = None

    @property
    def drivers(self):
        return self.results["DriverNumber"].astype(str).tolist()

    def get_driver(self, identifier):
        rows = self.results.loc[
            self.results["DriverNumber"].eq(str(identifier))
            | self.results["Abbreviation"].eq(str(identifier).upper())
        ]
        if rows.empty:
            raise ValueError("Driver not in this session")
        return rows.iloc[0]

    def telemetry(self, lap, *, speed_only=False):
        start = timestamp(lap["LapStartDate"])
        duration = lap["LapTime"].total_seconds()
        # Never download an entire session's high-frequency data for a replay.
        params = {
            "session_key": self.info["session_key"],
            "driver_number": int(lap["DriverNumber"]),
            "date>": (start - pd.Timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S.%f"),
            "date<": (start + pd.Timedelta(seconds=duration + 1)).strftime(
                "%Y-%m-%dT%H:%M:%S.%f"
            ),
        }
        car = self.api.get("car_data", params)
        pos = self.api.get("location", params)
        return merge_telemetry(car, pos, start, duration, speed_only=speed_only)


def merge_telemetry(car, positions, start, duration, *, speed_only=False):
    def frame(rows, mapping):
        df = pd.DataFrame(rows)
        if df.empty or not {"date", *(key for key in mapping if key != "drs")}.issubset(
            df.columns
        ):
            raise SessionDataError(
                "openf1_telemetry_unavailable",
                "Recorded car/position channels are missing for this lap.",
                425,
                60,
            )
        if "drs" in mapping and "drs" not in df:
            df["drs"] = np.nan
        df = df.rename(columns={"date": "Date", **mapping})
        df["Date"] = pd.to_datetime(
            df["Date"], utc=True, errors="coerce", format="mixed"
        )
        for column in mapping.values():
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = (
            df.loc[:, ["Date", *mapping.values()]]
            .replace([np.inf, -np.inf], np.nan)
            .dropna(subset=["Date", *(v for v in mapping.values() if v != "DRS")])
        )
        return df.sort_values("Date").drop_duplicates("Date")

    a = frame(
        car,
        (
            {"speed": "Speed"}
            if speed_only
            else {
                "speed": "Speed",
                "throttle": "Throttle",
                "brake": "Brake",
                "n_gear": "nGear",
                "drs": "DRS",
            }
        ),
    )
    b = frame(positions, {"x": "X", "y": "Y"})
    a = a.loc[a["Date"].between(start, start + pd.Timedelta(seconds=duration))]
    tel = pd.merge_asof(
        a, b, on="Date", direction="nearest", tolerance=pd.Timedelta(seconds=0.5)
    ).dropna(
        subset=["Date", "Speed", "X", "Y"]
        + ([] if speed_only else ["Throttle", "Brake", "nGear"])
    )
    if len(tel) < max(20, duration * 2) or len(tel) < 0.95 * len(a):
        raise SessionDataError(
            "openf1_telemetry_incomplete",
            "This lap has insufficient overlapping recorded car and position samples.",
            425,
            60,
        )
    elapsed = (tel["Date"] - start).dt.total_seconds().to_numpy()
    if elapsed[0] > 1.5 or duration - elapsed[-1] > 1.5 or np.diff(elapsed).max() > 2:
        raise SessionDataError(
            "openf1_telemetry_incomplete",
            "This lap has a telemetry gap; missing movement has not been reconstructed.",
            425,
            60,
        )
    speed = tel["Speed"].to_numpy(dtype=float) / 3.6
    if (speed < 0).any() or (
        not speed_only and not tel["Throttle"].between(0, 100).all()
    ):
        raise SessionDataError(
            "openf1_telemetry_invalid", "OpenF1 returned invalid telemetry values.", 502
        )
    tel = tel.copy()
    if not speed_only:
        tel["Brake"] = tel["Brake"].gt(0).astype(int)
    tel["Time"] = pd.to_timedelta(elapsed, unit="s")
    tel["Distance"] = np.r_[
        0, np.cumsum((speed[:-1] + speed[1:]) * 0.5 * np.diff(elapsed))
    ]
    return tel.reset_index(drop=True)


def _optional(api, endpoint, params, warnings):
    try:
        return api.get(endpoint, params)
    except SessionDataError as exc:
        warnings.append(f"{endpoint} unavailable: {exc.detail}")
        return None


def _roster(drivers):
    frame = pd.DataFrame(drivers).rename(
        columns={
            "driver_number": "DriverNumber",
            "name_acronym": "Abbreviation",
            "team_name": "TeamName",
            "full_name": "FullName",
        }
    )
    required = {"DriverNumber", "Abbreviation", "TeamName"}
    if frame.empty or not required.issubset(frame.columns):
        raise SessionDataError(
            "openf1_roster_unavailable",
            "OpenF1's driver roster is not available.",
            425,
            60,
        )
    frame = frame.dropna(subset=list(required)).copy()
    frame["DriverNumber"] = frame["DriverNumber"].astype(int).astype(str)
    frame["Abbreviation"] = frame["Abbreviation"].astype(str).str.upper()
    frame["FullName"] = frame.get("FullName", frame["Abbreviation"])
    return frame.drop_duplicates("DriverNumber").set_index("DriverNumber", drop=False)


def _laps(rows, roster, stints, pits, session, controls):
    frame = pd.DataFrame(rows).rename(
        columns={
            "driver_number": "DriverNumber",
            "lap_number": "LapNumber",
            "date_start": "LapStartDate",
            "lap_duration": "LapTime",
            "duration_sector_1": "Sector1Time",
            "duration_sector_2": "Sector2Time",
            "duration_sector_3": "Sector3Time",
        }
    )
    required = {"DriverNumber", "LapNumber", "LapStartDate", "LapTime"}
    if frame.empty or not required.issubset(frame.columns):
        raise SessionDataError(
            "openf1_laps_unavailable",
            "OpenF1 has not published usable lap timing for this session.",
            425,
            60,
        )
    frame["DriverNumber"] = pd.to_numeric(frame["DriverNumber"], errors="coerce")
    frame["LapNumber"] = pd.to_numeric(frame["LapNumber"], errors="coerce")
    frame = frame.dropna(subset=["DriverNumber", "LapNumber"]).copy()
    frame["DriverNumber"] = frame["DriverNumber"].astype(int).astype(str)
    frame = frame.loc[frame["DriverNumber"].isin(roster.index)].copy()
    # Duplicate or fractional lap identities cannot safely be paired.
    frame = frame.loc[frame["LapNumber"].gt(0) & frame["LapNumber"].mod(1).eq(0)]
    frame = frame.drop_duplicates(["DriverNumber", "LapNumber"], keep=False)
    frame["LapStartDate"] = pd.to_datetime(
        frame["LapStartDate"], utc=True, errors="coerce", format="mixed"
    )
    start, end = timestamp(session.info["date_start"]), timestamp(
        session.info["date_end"]
    )
    frame = frame.loc[
        frame["LapStartDate"].between(
            start - pd.Timedelta(minutes=30), end + pd.Timedelta(hours=6)
        )
    ].copy()
    for column in ("LapTime", "Sector1Time", "Sector2Time", "Sector3Time"):
        values = pd.to_numeric(
            frame.get(column, pd.Series(np.nan, index=frame.index)), errors="coerce"
        )
        frame[column] = pd.to_timedelta(values.where(np.isfinite(values)), unit="s")
    frame["Driver"] = frame["DriverNumber"].map(roster["Abbreviation"])
    frame["Team"] = frame["DriverNumber"].map(roster["TeamName"])
    frame["Compound"], frame["TyreLife"], frame["Stint"] = None, np.nan, np.nan
    ambiguous_stint = pd.Series(False, index=frame.index)
    # Missing accuracy/track flags remain unknown, never fabricated FastF1 flags.
    frame["IsAccurate"] = pd.Series(pd.NA, index=frame.index, dtype="boolean")
    frame["TrackStatus"] = "UNKNOWN"
    for column in ("PitInTime", "PitOutTime"):
        frame[column] = pd.Series(pd.NaT, index=frame.index, dtype="timedelta64[ns]")
    frame["OpenF1PitOutKnown"] = frame.get(
        "is_pit_out_lap", pd.Series(None, index=frame.index)
    ).map(lambda v: isinstance(v, (bool, np.bool_)))
    out = frame.get("is_pit_out_lap", pd.Series(None, index=frame.index)).eq(True)
    frame.loc[out, "PitOutTime"] = pd.Timedelta(0)
    for p in pits or []:
        driver, lap = p.get("driver_number"), numeric(p.get("lap_number"))
        if driver is not None and np.isfinite(lap):
            # Exclude both sides of the stop even when only pit lap is supplied.
            selected = frame["DriverNumber"].eq(str(driver))
            frame.loc[selected & frame["LapNumber"].eq(lap), "PitInTime"] = (
                pd.Timedelta(0)
            )
            frame.loc[selected & frame["LapNumber"].eq(lap + 1), "PitOutTime"] = (
                pd.Timedelta(0)
            )
    for s in stints or []:
        driver = s.get("driver_number")
        lo, hi = numeric(s.get("lap_start")), numeric(s.get("lap_end"))
        if driver is None or not np.isfinite(lo) or not np.isfinite(hi):
            continue
        selected = frame["DriverNumber"].eq(str(driver)) & frame["LapNumber"].between(
            lo, hi
        )
        # Overlapping upstream stint ranges are ambiguous; exclude from matching.
        overlap = selected & frame["Stint"].notna()
        ambiguous_stint |= overlap
        frame.loc[selected, "Compound"] = s.get("compound")
        frame.loc[selected, "Stint"] = numeric(s.get("stint_number"))
        frame.loc[selected, "TyreLife"] = (
            numeric(s.get("tyre_age_at_start"))
            + frame.loc[selected, "LapNumber"]
            - lo
            + 1
        )
    frame.loc[ambiguous_stint, "Compound"] = None
    frame.loc[ambiguous_stint, ["Stint", "TyreLife"]] = np.nan
    frame.loc[
        ~frame["Compound"].isin(["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]),
        "Compound",
    ] = None
    frame.loc[frame["TyreLife"].lt(1) | frame["TyreLife"].mod(1).ne(0), "TyreLife"] = (
        np.nan
    )
    frame["Time"] = (frame["LapStartDate"] - start) + frame["LapTime"]
    frame["LapStartTime"] = frame["LapStartDate"] - start
    frame = screen_laps(frame, controls, end, pit_available=pits is not None)
    return HistoricalLaps(frame.reset_index(drop=True), session=session)


def load_session(year, event, kind, cache_dir, template=None):
    template = template or events.get_session(year, event, kind)
    api = client(str(cache_dir))
    info = resolve_session(api, year, template, kind)
    session = HistoricalSession(api, template, info)
    params = {"session_key": info["session_key"]}
    session.results = _roster(api.get("drivers", params))
    rows = api.get("laps", params)
    if not rows:
        raise SessionDataError(
            "openf1_laps_unavailable",
            "OpenF1 lap timing is not published yet.",
            425,
            60,
        )
    warnings = session.data_warnings
    stints = _optional(api, "stints", params, warnings)
    pits = _optional(api, "pit", params, warnings)
    session.pit_data = pd.DataFrame(pits or [])
    session.intervals = pd.DataFrame(
        (_optional(api, "intervals", params, warnings) or []) if kind == "R" else []
    )
    controls = _optional(api, "race_control", params, warnings)
    controls = control_in_window(
        controls or [], timestamp(info["date_start"]), timestamp(info["date_end"])
    )
    session.race_control_messages = pd.DataFrame(controls)
    finishes = [
        timestamp(r["date"])
        for r in controls
        if r.get("category") == "SessionStatus"
        and r.get("message") in ("SESSION FINISHED", "SESSION ENDED")
        and timestamp(r["date"]) >= timestamp(info["date_start"])
    ]
    if finishes and max(finishes) + pd.Timedelta(minutes=30) >= pd.Timestamp.now(
        tz="UTC"
    ):
        raise SessionDataError(
            "openf1_historical_pending",
            "The delayed session ended recently; retry 30 minutes after its actual finish.",
            425,
            60,
        )
    session.completed = any(
        r.get("category") == "SessionStatus"
        and r.get("message") in ("SESSION FINISHED", "SESSION ENDED")
        and timestamp(r["date"]) >= timestamp(info["date_start"])
        for r in controls
    )
    for column in ("Q1", "Q2", "Q3"):
        session.results[column] = pd.Series(
            pd.NaT, index=session.results.index, dtype="timedelta64[ns]"
        )
    session.results["Position"] = np.nan
    public = None
    if kind in ("Q", "R", "S"):
        try:
            public = load_results_session(year, event, kind)
        except SessionDataError as exc:
            warnings.append(
                f"Published Jolpica classification unavailable: {exc.detail}"
            )
    if public is not None:
        for column in public.results.columns:
            if column not in ("DriverNumber", "Abbreviation", "TeamName", "FullName"):
                session.results[column] = session.results["DriverNumber"].map(
                    public.results.set_index("DriverNumber")[column]
                )
        session.completed = True
        session.qualifying_classification = kind == "Q"
        session.classification_source = public.data_source
    else:
        classification = _optional(api, "session_result", params, warnings)
        if classification:
            positions = {
                str(r.get("driver_number")): numeric(r.get("position"))
                for r in classification
            }
            session.results["Position"] = session.results["DriverNumber"].map(positions)
            session.completed = True
            session.classification_source = "OpenF1 published session result"
    session.results = session.results.sort_values("Position", na_position="last")
    session.laps = _laps(rows, session.results, stints, pits, session, controls)
    if session.laps.empty or not session.laps["LapTime"].notna().any():
        raise SessionDataError(
            "openf1_laps_unavailable",
            "No finite recorded laps are available from OpenF1.",
            425,
            60,
        )
    if not stints:
        warnings.append(
            "Tyre stints unavailable: compound/age comparisons are omitted."
        )
    if not controls:
        warnings.append(
            "Race-control coverage unavailable: screened pace samples are omitted."
        )
    warnings.append(
        "SC/VSC laps remain excluded until an explicit track-wide GREEN message; uncertain restarts can reduce samples."
    )
    warnings.append(
        f"OpenF1 screening retained {int(session.laps['OpenF1Eligible'].sum())} of {len(session.laps)} recorded laps."
    )
    weather = _optional(api, "weather", params, warnings)
    session.weather_data = pd.DataFrame(weather or []).rename(
        columns={
            "air_temperature": "AirTemp",
            "track_temperature": "TrackTemp",
            "humidity": "Humidity",
            "wind_speed": "WindSpeed",
            "rainfall": "Rainfall",
        }
    )
    if "date" in session.weather_data:
        dates = pd.to_datetime(
            session.weather_data["date"], utc=True, errors="coerce", format="mixed"
        )
        observed_end = max([timestamp(info["date_end"]), *finishes])
        session.weather_data = session.weather_data.loc[
            dates.between(timestamp(info["date_start"]), observed_end)
        ].copy()
    else:
        session.weather_data = session.weather_data.iloc[:0].copy()
    for column in ("AirTemp", "TrackTemp", "Humidity", "WindSpeed", "Rainfall"):
        if column not in session.weather_data:
            session.weather_data[column] = np.nan
        session.weather_data[column] = pd.to_numeric(
            session.weather_data[column], errors="coerce"
        )
    if "date" in session.weather_data:
        session.weather_data["Date"] = pd.to_datetime(
            session.weather_data["date"], utc=True, errors="coerce", format="mixed"
        )
    return session
