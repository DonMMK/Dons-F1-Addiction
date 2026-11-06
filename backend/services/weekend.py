"""Descriptive comparisons, without named-driver bonuses or causal claims."""

from itertools import combinations

import numpy as np
import pandas as pd

from .data import clean_laps, iso, load_session, number, seconds

LIMITS = [
    "Same team does not guarantee identical upgrades, setup, damage or engine modes.",
    "Fuel mass, setup, tyre carcass temperatures and physical tyre wear are not public timing channels.",
    "Same-lap matching reduces fuel-burn and weather timing differences; fuel loads can still differ.",
    "Traffic, management, damage and strategy can remain in green-flag laps. Results are associations, not driver-skill scores.",
    "Compound labels are weekend-relative; SOFT at different circuits need not be the same Pirelli specification.",
]


def matched_laps(laps, first, second, age_tolerance=1):
    clean = clean_laps(laps)
    columns = ["LapNumber", "Compound", "TyreLife", "seconds", "Stint"]
    if not set(columns).issubset(clean.columns):
        return pd.DataFrame()
    a = clean.loc[clean["Driver"].eq(first), columns].dropna()
    b = clean.loc[clean["Driver"].eq(second), columns].dropna()
    both = a.merge(
        b, on=["LapNumber", "Compound"], suffixes=("A", "B"), validate="one_to_one"
    )
    both = both.loc[
        (both["TyreLifeA"] - both["TyreLifeB"]).abs() <= age_tolerance
    ].copy()
    both["delta"] = both["secondsA"] - both["secondsB"]
    return both.sort_values("LapNumber")


def interval(pairs):
    """Moving-block bootstrap within contiguous matched stint-pair segments."""
    if len(pairs) < 8:
        return None
    groups, current, previous = [], [], None
    for _, row in pairs.iterrows():
        key = (row["Compound"], row["StintA"], row["StintB"])
        if previous is not None and (
            key != previous[0] or row["LapNumber"] != previous[1] + 1
        ):
            groups.append(np.array(current))
            current = []
        current.append(row["delta"])
        previous = (key, row["LapNumber"])
    if current:
        groups.append(np.array(current))
    rng = np.random.default_rng(17)
    values = []
    for _ in range(600):
        draw = []
        for group in groups:
            starts = rng.integers(0, len(group), size=(len(group) + 2) // 3)
            block = np.concatenate(
                [group[(np.arange(3) + s) % len(group)] for s in starts]
            )[: len(group)]
            draw.extend(block)
        values.append(np.median(draw))
    return [number(x) for x in np.quantile(values, [0.025, 0.975])]


def qualifying_gap(session, first, second):
    try:
        stages = session.laps.split_qualifying_sessions()
    except (ValueError, AttributeError):
        return {
            "segment": None,
            "deltaSeconds": None,
            "reason": "Qualifying segments unavailable",
        }
    for index in (2, 1, 0):
        if stages[index] is None:
            continue
        clean = clean_laps(stages[index])
        a = clean.loc[clean["Driver"].eq(first), "seconds"]
        b = clean.loc[clean["Driver"].eq(second), "seconds"]
        if len(a) and len(b):
            return {
                "segment": f"Q{index+1}",
                "deltaSeconds": number(a.min() - b.min()),
                "firstSeconds": number(a.min()),
                "secondSeconds": number(b.min()),
                "reason": "Fastest valid laps in deepest shared segment; track evolution remains a confounder",
            }
    return {
        "segment": None,
        "deltaSeconds": None,
        "reason": "No shared segment with valid timed laps",
    }


def degradation(laps, driver):
    """Fit lap time ~ race lap + tyre age per compound only if identifiable."""
    clean = clean_laps(laps)
    result = []
    for compound, df in clean.loc[clean["Driver"].eq(driver)].groupby("Compound"):
        df = df.dropna(subset=["TyreLife", "LapNumber", "Stint", "seconds"])
        item = {
            "compound": str(compound),
            "laps": len(df),
            "slopeSecondsPerTyreLap": None,
            "reason": "Requires 15 valid laps and two stints on this compound",
        }
        if len(df) >= 15 and df["Stint"].nunique() >= 2:
            x = df[["LapNumber", "TyreLife"]].to_numpy(dtype=float)
            scale = x.std(axis=0)
            if (scale == 0).any():
                result.append(item)
                continue
            z = np.column_stack([np.ones(len(df)), (x - x.mean(axis=0)) / scale])
            if np.linalg.matrix_rank(z) < 3 or np.linalg.cond(z) > 30:
                item["reason"] = (
                    "Tyre age and race lap cannot be separated in this sample"
                )
            else:
                fit = np.linalg.lstsq(z, df["seconds"].to_numpy(), rcond=None)[0]
                item.update(
                    slopeSecondsPerTyreLap=number(fit[2] / scale[1]),
                    reason="Adjusted lap-time trend, not measured physical tyre wear; traffic, weather and stint effects remain",
                )
        result.append(item)
    return result


def field_pace(race, qualifying):
    """Observed peer-relative pace; peer sets vary, so this is not a car ranking."""
    clean = clean_laps(race.laps).dropna(subset=["TyreLife", "Compound"])
    samples = {}
    for _, group in clean.groupby(["LapNumber", "Compound"]):
        for _, lap in group.iterrows():
            peers = group.loc[
                group["Driver"].ne(lap["Driver"])
                & (group["TyreLife"] - lap["TyreLife"]).abs().le(1)
            ]
            if peers["Driver"].nunique() < 2:
                continue
            benchmark = peers["seconds"].median()
            samples.setdefault(str(lap["Driver"]), []).append(
                100 * (lap["seconds"] / benchmark - 1)
            )
    q_positions = (
        {}
        if qualifying is None
        else {
            str(row["Abbreviation"]): number(row["Position"], 0)
            for _, row in qualifying.results.iterrows()
        }
    )
    result = []
    for _, row in race.results.iterrows():
        driver = str(row["Abbreviation"])
        values = samples.get(driver, [])
        result.append(
            {
                "driver": driver,
                "team": str(row["TeamName"]),
                "qualifyingPosition": q_positions.get(driver),
                "finishPosition": number(row["Position"], 0),
                "matchedLaps": len(values),
                "relativePacePercent": (
                    number(np.median(values)) if len(values) >= 5 else None
                ),
            }
        )
    return result


def weekend(year, round_number):
    sessions, errors = {}, []
    for kind in ("Q", "R"):
        try:
            sessions[kind] = load_session(year, round_number, kind)
        except Exception:
            errors.append(f"{kind} data unavailable or not published yet")
    if not sessions:
        raise ValueError("No qualifying or race timing data available for this weekend")
    source = sessions.get("R") or sessions.get("Q")
    race = sessions.get("R")
    quali = sessions.get("Q")
    roster = {}
    for session in sessions.values():
        for _, row in session.results.iterrows():
            team, driver = str(row["TeamName"]), str(row["Abbreviation"])
            if driver and driver != "nan":
                roster.setdefault(team, set()).add(driver)
    teams = []
    for team, drivers in sorted(roster.items()):
        for first, second in combinations(sorted(drivers), 2):
            pairs = (
                matched_laps(race.laps, first, second)
                if race is not None
                else pd.DataFrame()
            )
            q = (
                qualifying_gap(quali, first, second)
                if quali is not None
                else {
                    "segment": None,
                    "deltaSeconds": None,
                    "reason": "Qualifying unavailable",
                }
            )
            delta = number(pairs["delta"].median()) if len(pairs) else None
            ci = interval(pairs) if len(pairs) else None
            reversal = (
                q["deltaSeconds"] is not None
                and delta is not None
                and q["deltaSeconds"] * delta < 0
            )
            teams.append(
                {
                    "team": team,
                    "first": first,
                    "second": second,
                    "qualifying": q,
                    "raceDeltaSeconds": delta,
                    "matchedLaps": len(pairs),
                    "interval95": ci,
                    "paceReversal": bool(reversal),
                    "samples": [
                        {
                            "lap": int(r.LapNumber),
                            "first": number(r.secondsA),
                            "second": number(r.secondsB),
                            "delta": number(r.delta),
                            "compound": str(r.Compound),
                            "ageA": int(r.TyreLifeA),
                            "ageB": int(r.TyreLifeB),
                        }
                        for r in pairs.itertuples()
                    ],
                    "tyreTrends": {
                        d: degradation(race.laps, d) if race is not None else []
                        for d in (first, second)
                    },
                }
            )
    weather = None
    wd = getattr(source, "weather_data", None)
    if wd is not None and not wd.empty:
        weather = {
            key: number(wd[key].mean())
            for key in ("AirTemp", "TrackTemp", "Humidity", "WindSpeed")
        }
        weather["rainfall"] = bool(wd["Rainfall"].any())
    return {
        "year": year,
        "round": round_number,
        "eventName": str(source.event["EventName"]),
        "teams": teams,
        "weather": weather,
        "fieldPace": field_pace(race, quali) if race is not None else [],
        "warnings": errors,
        "limitations": LIMITS,
        "method": "A minus B; negative means A faster. Race pairs: same lap, same compound, tyre age within one lap; accurate, non-deleted, non-generated, green-flag and no pit laps. Exploratory 95% block-bootstrap interval needs 8 pairs.",
        "unavailable": [
            "Fuel mass (kg)",
            "Setup settings",
            "Physical tyre wear",
            "Brake pressure",
            "Aero loads",
        ],
    }
