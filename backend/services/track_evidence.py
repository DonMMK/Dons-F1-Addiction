"""Recorded speed-zone comparison, explicitly not official corner geometry."""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from .data import clean_laps, load_session, number
from .loading_errors import SessionDataError


def speed_map(year, round_number, kind, first, second):
    session = load_session(year, round_number, kind, telemetry=True)
    selected = []
    for driver in (first, second):
        laps = clean_laps(session.laps.pick_drivers(driver))
        if laps.empty:
            raise SessionDataError(
                "track_lap_unavailable",
                f"No screened recorded lap is available for {driver}.",
                425,
                60,
            )
        lap = laps.loc[laps["LapTime"].idxmin()]
        recorded = (
            session.telemetry(lap, speed_only=True)
            if getattr(session, "data_provider", None) == "openf1"
            else lap.get_telemetry()
        )
        tel = recorded.sort_values("Time").dropna(
            subset=["Time", "Distance", "Speed", "X", "Y"]
        )
        tel = tel.drop_duplicates("Time")
        if len(tel) < 20 or tel["Distance"].max() <= tel["Distance"].min():
            raise SessionDataError(
                "track_samples_unavailable",
                "Insufficient finite recorded track samples.",
                425,
                60,
            )
        selected.append((lap, tel))
    return compare_speed_zones(
        selected,
        first,
        second,
        getattr(session, "data_source", "FastF1 recorded telemetry"),
    )


def compare_speed_zones(selected, first, second, source):
    (lap, a), (other_lap, b) = selected
    a, b = a.copy(), b.copy()
    for tel in (a, b):
        tel["fraction"] = (tel["Distance"] - tel["Distance"].min()) / (
            tel["Distance"].max() - tel["Distance"].min()
        )
    time = a["Time"].dt.total_seconds()
    cadence = max(float(time.diff().median()), 0.05)
    smooth = a["Speed"].rolling(5, center=True, min_periods=1).median().to_numpy()
    candidates, _ = find_peaks(
        -smooth, prominence=25, distance=max(2, int(2.5 / cadence))
    )
    boundaries = []
    for i in (1, 2):
        values = [lap.get(f"Sector{j}Time") for j in range(1, i + 1)]
        boundaries.append(
            sum(v.total_seconds() for v in values)
            if all(pd.notna(v) for v in values)
            else np.nan
        )
    zones = []
    for index in candidates:
        row = a.iloc[index]
        nearby = b.loc[(b["fraction"] - row["fraction"]).abs().le(0.02)]
        if nearby.empty:
            continue
        speed = float(row["Speed"])
        zones.append(
            {
                "zone": len(zones) + 1,
                "fraction": number(row["fraction"]),
                "x": number(row["X"]),
                "y": number(row["Y"]),
                "band": "slow" if speed < 120 else "medium" if speed < 200 else "fast",
                "sector": (
                    int(np.searchsorted(boundaries, row["Time"].total_seconds())) + 1
                    if np.isfinite(boundaries).all()
                    else None
                ),
                "speedA": number(speed),
                "speedB": number(nearby["Speed"].min()),
                "deltaKmH": number(speed - nearby["Speed"].min()),
            }
        )
    stride = max(1, len(a) // 500)
    return {
        "source": source,
        "first": first,
        "second": second,
        "lapTimeA": number(lap["LapTime"].total_seconds()),
        "lapTimeB": number(other_lap["LapTime"].total_seconds()),
        "trace": [
            {"x": number(r.X), "y": number(r.Y)} for r in a.iloc[::stride].itertuples()
        ],
        "zones": zones,
        "method": "Speed minima on the first driver's screened fastest lap: 5-sample median smoothing, ≥25 km/h prominence, ≥2.5 seconds apart. Slow <120, medium 120–200, fast ≥200 km/h. The second driver's minimum is sampled within ±2% normalized lap distance. Zone labels are detected speed features, not FIA turn numbers or precise apex locations.",
        "limitations": "Recorded XY and integrated distance are approximate. Different lines, tyres, track evolution and fuel remain confounders. Higher minimum corner speed can trade against entry or exit time; it is not proof of more downforce, better driving or a faster car.",
    }
