"""Recorded speed-zone comparison, explicitly not official corner geometry."""

import numpy as np
import pandas as pd
from scipy.signal import find_peaks

from .data import clean_laps, load_session, number
from .loading_errors import SessionDataError


def lap_options(year, round_number, kind, driver):
    session = load_session(year, round_number, kind)
    laps = clean_laps(session.laps.pick_drivers(driver)).sort_values("LapNumber")
    return {
        "driver": driver,
        "laps": [
            {
                "lap": int(r["LapNumber"]),
                "seconds": number(r["seconds"]),
                "compound": (
                    r.get("Compound") if isinstance(r.get("Compound"), str) else None
                ),
                "age": number(r.get("TyreLife")),
            }
            for _, r in laps.iterrows()
        ],
        "note": "Quality-screened timed laps. Telemetry coverage is checked when a comparison is requested.",
    }


def speed_map(year, round_number, kind, first, second, lap_a=None, lap_b=None):
    session = load_session(year, round_number, kind, telemetry=True)
    selected = []
    for driver, requested in ((first, lap_a), (second, lap_b)):
        laps = clean_laps(session.laps.pick_drivers(driver))
        if laps.empty:
            raise SessionDataError(
                "track_lap_unavailable",
                f"No screened recorded lap is available for {driver}.",
                425,
                60,
            )
        if requested is not None:
            laps = laps.loc[laps["LapNumber"].eq(requested)]
            if laps.empty:
                raise SessionDataError(
                    "selected_lap_unavailable",
                    f"Lap {requested} for {driver} is not a quality-screened recorded lap. Choose another lap.",
                    422,
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
        tel.drop(
            tel.index[~np.isfinite(tel[["Distance", "Speed", "X", "Y"]]).all(axis=1)],
            inplace=True,
        )
        # Distance must increase before elapsed-time interpolation is meaningful.
        tel.drop(
            tel.index[tel["Distance"].le(tel["Distance"].cummax().shift())],
            inplace=True,
        )
        if len(tel) < 20 or tel["Distance"].max() <= tel["Distance"].min():
            raise SessionDataError(
                "track_samples_unavailable",
                "Insufficient monotonic recorded distance samples.",
                425,
                60,
            )
        tel["fraction"] = (tel["Distance"] - tel["Distance"].min()) / (
            tel["Distance"].max() - tel["Distance"].min()
        )
        tel["elapsed"] = (
            tel["Time"].dt.total_seconds() - tel["Time"].dt.total_seconds().iloc[0]
        )
        if tel["elapsed"].diff().max() > 2.5:
            raise SessionDataError(
                "track_samples_unavailable",
                "Telemetry has gaps over 2.5 seconds; a dominance map would be misleading.",
                425,
                60,
            )
    edges = np.linspace(0, 1, 26)
    times_a = np.interp(edges, a["fraction"], a["elapsed"])
    times_b = np.interp(edges, b["fraction"], b["elapsed"])
    deltas = np.diff(times_a) - np.diff(times_b)
    mini_sectors = [
        {
            "index": i + 1,
            "start": number(edges[i]),
            "end": number(edges[i + 1]),
            "deltaSeconds": number(delta),
            "winner": first if delta < -0.02 else second if delta > 0.02 else None,
        }
        for i, delta in enumerate(deltas)
    ]
    fractions = np.linspace(0, 1, 251)
    trace_rows = a.iloc[:: max(1, len(a) // 500)]
    if trace_rows.index[-1] != a.index[-1]:
        trace_rows = pd.concat([trace_rows, a.iloc[[-1]]])
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
    return {
        "source": source,
        "first": first,
        "second": second,
        "lapTimeA": number(lap["LapTime"].total_seconds()),
        "lapTimeB": number(other_lap["LapTime"].total_seconds()),
        "lapA": number(lap.get("LapNumber")),
        "lapB": number(other_lap.get("LapNumber")),
        "observedDurationA": number(a["elapsed"].iloc[-1]),
        "observedDurationB": number(b["elapsed"].iloc[-1]),
        "miniSectors": mini_sectors,
        "comparison": [
            {
                "fraction": number(f),
                "speedA": number(np.interp(f, a["fraction"], a["Speed"])),
                "speedB": number(np.interp(f, b["fraction"], b["Speed"])),
                "deltaSeconds": number(
                    np.interp(f, a["fraction"], a["elapsed"])
                    - np.interp(f, b["fraction"], b["elapsed"])
                ),
            }
            for f in fractions
        ],
        "trace": [
            {"x": number(r.X), "y": number(r.Y), "fraction": number(r.fraction)}
            for r in trace_rows.itertuples()
        ],
        "zones": zones,
        "method": "Selected quality-screened laps, or fastest screened lap by default. Dominance uses interpolated elapsed time across 25 equal normalised-distance bins; differences within ±0.02 s per bin are neutral. These are estimated mini-sectors, not official timing sectors. Speed minima use 5-sample median smoothing, ≥25 km/h prominence and ≥2.5 seconds spacing; bands: slow <120, medium 120–200, fast ≥200 km/h. Driver B's minimum is sampled within ±2% normalised distance. Detected zones are not FIA turn numbers.",
        "limitations": "Recorded XY, sampling and integrated distance are approximate. Bins cover each trace's observed span, which can omit lap boundaries; their sum need not equal the official lap-time difference. Different lines, tyres, track evolution, fuel and tow remain confounders. Colours describe these selected laps, not car capability or driver skill. Higher minimum corner speed can trade against entry or exit time; it is not proof of more downforce or a faster car.",
    }
