"""Observed stint spans and screened lap times, with no invented fuel loads."""

import numpy as np
import pandas as pd

from .data import clean_laps, load_session, number, optional_data
from .loading_errors import SessionDataError

COMPOUNDS = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}


def strategy_report(session):
    raw = pd.DataFrame(session.laps).copy()
    if raw.empty or not {"Driver", "LapNumber"}.issubset(raw.columns):
        raise SessionDataError(
            "strategy_unavailable", "Race laps are not published yet.", 425, 60
        )
    raw["LapNumber"] = pd.to_numeric(raw["LapNumber"], errors="coerce")
    raw = raw.loc[
        raw["Driver"].notna() & raw["LapNumber"].gt(0) & raw["LapNumber"].mod(1).eq(0)
    ]
    raw = raw.drop_duplicates(["Driver", "LapNumber"], keep=False)
    if raw.empty:
        raise SessionDataError(
            "strategy_unavailable", "No unambiguous race laps are available.", 425, 60
        )
    screened = clean_laps(raw)
    results = pd.DataFrame(optional_data(session, "results"))
    drivers = []
    for driver, laps in raw.groupby("Driver", sort=True):
        laps = laps.sort_values("LapNumber")
        spans, previous = [], None
        for _, lap in laps.iterrows():
            compound = lap.get("Compound")
            compound = (
                compound
                if isinstance(compound, str) and compound in COMPOUNDS
                else "UNKNOWN"
            )
            stint = number(lap.get("Stint"))
            current = (stint, compound)
            lap_number = int(lap["LapNumber"])
            # A gap in observations stays a gap, even within the same stint.
            if (
                previous != current
                or not spans
                or lap_number != spans[-1]["endLap"] + 1
            ):
                spans.append(
                    {
                        "startLap": lap_number,
                        "endLap": lap_number,
                        "stint": stint,
                        "compound": compound,
                    }
                )
            else:
                spans[-1]["endLap"] = lap_number
            previous = current
        points = []
        for _, lap in screened.loc[screened["Driver"].eq(driver)].iterrows():
            age, stint, duration = (
                number(lap.get("TyreLife")),
                number(lap.get("Stint")),
                number(lap.get("seconds")),
            )
            compound = lap.get("Compound")
            if (
                age is None
                or age < 1
                or stint is None
                or duration is None
                or duration <= 0
                or not isinstance(compound, str)
                or compound not in COMPOUNDS
            ):
                continue
            points.append(
                {
                    "lap": int(lap["LapNumber"]),
                    "age": age,
                    "stint": stint,
                    "compound": compound,
                    "seconds": duration,
                }
            )
        result = (
            results.loc[results["Abbreviation"].eq(driver)]
            if "Abbreviation" in results
            else pd.DataFrame()
        )
        finish = number(result.iloc[0].get("Position")) if not result.empty else None
        team = (
            laps["Team"].dropna().iloc[0]
            if "Team" in laps and laps["Team"].notna().any()
            else "Unknown team"
        )
        drivers.append(
            {
                "driver": str(driver),
                "team": str(team),
                "finish": finish,
                "spans": spans,
                "points": points,
            }
        )
    drivers.sort(
        key=lambda d: (d["finish"] if d["finish"] is not None else np.inf, d["driver"])
    )
    return {
        "source": getattr(session, "data_source", "FastF1 recorded timing"),
        "maxLap": int(raw["LapNumber"].max()),
        "drivers": drivers,
        "coverage": {
            "observed": len(raw),
            "screened": len(screened),
            "tyrePoints": sum(len(d["points"]) for d in drivers),
        },
        "warnings": getattr(session, "data_warnings", []),
        "method": "Bars join consecutive observed lap records with the same reported compound and stint. Missing laps remain blank; unknown compounds are grey. Bars include pit and neutralised laps. Tyre plots use only quality-screened timed laps with reported compound, stint and tyre age; this screen does not establish clear air or constant weather.",
        "limitations": "Fuel mass and physical tyre wear are not observed. Optional fuel-burn normalisation is a user assumption in seconds per race lap, not measured fuel. Weather, traffic, management and tyre warm-up still affect the trend. Same compound labels across different weekends need not mean the same tyre specification.",
    }


def load_strategy(year, round_number):
    return strategy_report(load_session(year, round_number, "R"))
