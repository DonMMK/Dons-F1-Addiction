"""Observed package pace, NOT a causal decomposition into car and driver.

Matched comparisons form a graph. Scores and ranks are local to each connected
component; a disconnected field is never presented as a complete ranking.
"""

from itertools import combinations

import numpy as np
import pandas as pd

from .data import clean_laps, number, optional_data

POLICY = {
    "minimumMatchedWindows": 8,
    "minimumBlocks": 3,
    "blockWindows": 3,
    "minimumDriverWindows": 5,
    "tyreAgeTolerance": 1,
    "maximumClockGapSeconds": 90,
    "maximumTemperatureGapC": 2,
    "trafficGapSeconds": 1.5,
    "weatherMaximumAgeSeconds": 90,
    "bootstrapDraws": 200,
}


def weather_frame(session):
    frame = optional_data(session, "weather_data")
    if frame is None or frame.empty:
        return pd.DataFrame()
    frame = frame.copy()
    if "Date" not in frame:
        if "date" in frame:
            frame["Date"] = frame["date"]
        elif "Time" in frame and getattr(session, "t0_date", None) is not None:
            origin = pd.to_datetime(session.t0_date, utc=True)
            frame["Date"] = origin + pd.to_timedelta(frame["Time"])
        else:
            return pd.DataFrame()
    frame["Date"] = pd.to_datetime(
        frame["Date"], utc=True, errors="coerce", format="mixed"
    )
    for column in ("TrackTemp", "AirTemp", "WindSpeed", "Humidity", "Rainfall"):
        frame[column] = pd.to_numeric(
            frame.get(column, pd.Series(np.nan, index=frame.index)), errors="coerce"
        ).replace([np.inf, -np.inf], np.nan)
    return frame.dropna(subset=["Date"]).sort_values("Date").drop_duplicates("Date")


def weather_report(session):
    frame = weather_frame(session)
    return {
        "samples": len(frame),
        "summary": (
            {
                c: {
                    "min": number(frame[c].min()),
                    "median": number(frame[c].median()),
                    "max": number(frame[c].max()),
                }
                for c in ("TrackTemp", "AirTemp", "WindSpeed", "Humidity")
            }
            if not frame.empty
            else {}
        ),
        "timeline": [
            {
                "date": r.Date.isoformat(),
                "trackTemp": number(r.TrackTemp),
                "airTemp": number(r.AirTemp),
                "windSpeed": number(r.WindSpeed),
                "rainReported": None if pd.isna(r.Rainfall) else bool(r.Rainfall > 0),
            }
            for r in frame.itertuples()
        ],
        "note": "Rainfall is a rain sensor report, not a measurement of surface grip or standing water. Temperature associations do not establish which car design caused an advantage.",
    }


def _traffic(session):
    frame = optional_data(session, "intervals")
    if (
        frame is None
        or frame.empty
        or not {"driver_number", "date", "interval", "gap_to_leader"}.issubset(
            frame.columns
        )
    ):
        return {}
    frame = frame.copy()
    frame["Date"] = pd.to_datetime(
        frame["date"], utc=True, errors="coerce", format="mixed"
    )
    frame["gap"] = pd.to_numeric(frame["interval"], errors="coerce").astype(float)
    # A numeric zero gap to leader identifies the leader's otherwise null interval.
    leader = pd.to_numeric(frame["gap_to_leader"], errors="coerce").eq(0)
    frame.loc[leader, "gap"] = np.inf
    return {
        str(n): f.dropna(subset=["Date"]).sort_values("Date")
        for n, f in frame.groupby("driver_number")
    }


def condition_laps(session, condition="slick"):
    """Quality, weather and condition screening shared by both pace views."""
    laps = clean_laps(session.laps)
    coverage = {
        "recorded": len(session.laps),
        "qualityScreened": len(laps),
        "weatherMatched": 0,
        "trafficScreened": 0,
        "used": 0,
    }
    required = {"LapStartDate", "DriverNumber", "Team", "Compound", "TyreLife", "Stint"}
    weather = weather_frame(session)
    if laps.empty or not required.issubset(laps.columns) or weather.empty:
        return pd.DataFrame(), coverage
    laps = laps.dropna(subset=list(required)).copy()
    laps["Date"] = (
        pd.to_datetime(laps["LapStartDate"], utc=True, errors="coerce", format="mixed")
        + laps["LapTime"] / 2
    )
    laps = laps.dropna(subset=["Date"]).sort_values("Date")
    laps = pd.merge_asof(
        pd.DataFrame(laps),
        weather[["Date", "TrackTemp", "Rainfall"]],
        on="Date",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=90),
    )
    laps = laps.dropna(subset=["TrackTemp", "Rainfall"])
    coverage["weatherMatched"] = len(laps)
    if condition == "slick":
        laps = laps.loc[laps["Compound"].isin(["SOFT", "MEDIUM", "HARD"])]
    elif condition == "wet":
        laps = laps.loc[laps["Compound"].isin(["INTERMEDIATE", "WET"])]
    elif condition == "cool":
        laps = laps.loc[laps["TrackTemp"].lt(30)]
    elif condition == "warm":
        laps = laps.loc[laps["TrackTemp"].ge(40)]
    return laps, coverage


def eligible_laps(session, condition="slick"):
    laps, coverage = condition_laps(session, condition)
    if laps.empty:
        return laps, coverage
    practice = session.name.startswith("Practice")
    traffic = _traffic(session)
    keep = []
    for r in laps.itertuples():
        if practice:
            # No public interval coverage for practice. Report this omission;
            # never present practice samples as verified clear-air race pace.
            keep.append(True)
            continue
        samples = traffic.get(str(r.DriverNumber))
        if samples is None:
            keep.append(False)
            continue
        start = pd.to_datetime(r.LapStartDate, utc=True)
        end = start + r.LapTime
        samples = samples.loc[samples["Date"].between(start, end)]
        known = samples["gap"].notna()
        continuous = (
            len(samples) >= max(3, r.seconds / 8)
            and known.all()
            and samples["Date"].iloc[0] <= start + pd.Timedelta(seconds=10)
            and samples["Date"].iloc[-1] >= end - pd.Timedelta(seconds=10)
            and samples["Date"].diff().dt.total_seconds().dropna().le(10).all()
        )
        keep.append(bool(continuous and samples["gap"].gt(1.5).all()))
    laps = laps.loc[keep].copy()
    coverage["trafficScreened"] = 0 if practice else len(laps)
    if practice:
        start = pd.to_datetime(session.date, utc=True)
        laps["Window"] = ((laps["Date"] - start).dt.total_seconds() // 180).astype(int)
        # Only observed multi-lap runs contribute to practice summaries.
        laps = laps.groupby(["Driver", "Stint"], group_keys=False).filter(
            lambda g: len(g) >= 3
        )
        laps["medianDistance"] = (
            laps["seconds"]
            - laps.groupby(["Driver", "Window"])["seconds"].transform("median")
        ).abs()
        laps = laps.sort_values("medianDistance").drop_duplicates(["Driver", "Window"])
    else:
        laps["Window"] = laps["LapNumber"].astype(int)
    coverage["used"] = len(laps)
    return laps, coverage


def comparisons(laps):
    pairs = []
    if laps.empty:
        return pairs
    for (window, compound), group in laps.groupby(["Window", "Compound"]):
        for (_, a), (_, b) in combinations(group.iterrows(), 2):
            if a["Driver"] == b["Driver"] or abs(a["TyreLife"] - b["TyreLife"]) > 1:
                continue
            if (
                abs((a["Date"] - b["Date"]).total_seconds()) > 90
                or abs(a["TrackTemp"] - b["TrackTemp"]) > 2
                or a["Rainfall"] != b["Rainfall"]
            ):
                continue
            # Orient by identifier solely for reproducible signs, never bonuses.
            if str(a["Driver"]) > str(b["Driver"]):
                a, b = b, a
            pairs.append(
                {
                    "window": int(window),
                    "compound": str(compound),
                    "a": str(a["Driver"]),
                    "b": str(b["Driver"]),
                    "teamA": str(a["Team"]),
                    "teamB": str(b["Team"]),
                    "delta": float(a["seconds"] - b["seconds"]),
                    **{
                        f"s{i}": (
                            number(
                                (
                                    a.get(f"Sector{i}Time") - b.get(f"Sector{i}Time")
                                ).total_seconds()
                            )
                            if pd.notna(a.get(f"Sector{i}Time"))
                            and pd.notna(b.get(f"Sector{i}Time"))
                            else None
                        )
                        for i in (1, 2, 3)
                    },
                }
            )
    return pairs


def _fit(nodes, edges, draws=None, sector="delta"):
    matrix, values = [], []
    for (a, b), rows in edges.items():
        sample = [
            r[sector]
            for r in rows
            if r[sector] is not None
            for _ in range(1 if draws is None else draws.get(r["window"] // 3, 0))
        ]
        if not sample:
            continue
        row = np.zeros(len(nodes))
        row[nodes.index(a)] = 1
        row[nodes.index(b)] = -1
        matrix.append(row)
        values.append(np.median(sample))
    matrix.append(np.ones(len(nodes)))
    values.append(0)
    matrix = np.array(matrix)
    if np.linalg.matrix_rank(matrix) < len(nodes):
        return None
    return np.linalg.lstsq(matrix, values, rcond=None)[0]


def _rank_summary(values, bootstrap, index):
    from scipy.stats import rankdata

    enough = len(bootstrap) >= 100
    lo = (
        rankdata(np.round(bootstrap, 3), method="min", axis=1)[:, index]
        if enough
        else None
    )
    hi = (
        rankdata(np.round(bootstrap, 3), method="max", axis=1)[:, index]
        if enough
        else None
    )
    return {
        "rank": int(rankdata(np.round(values, 3), method="min")[index]),
        "scoreSeconds": number(values[index]),
        "interval95": (
            [number(v) for v in np.quantile(bootstrap[:, index], [0.025, 0.975])]
            if enough
            else None
        ),
        "rankRange95": (
            [
                int(np.floor(np.quantile(lo, 0.025))),
                int(np.ceil(np.quantile(hi, 0.975))),
            ]
            if enough
            else None
        ),
    }


def ranking(pairs, roster):
    if not pairs:
        return {"rows": [], "pairwise": [], "components": 0}, {
            "rows": [],
            "pairwise": [],
            "components": 0,
        }
    df = pd.DataFrame(pairs)
    edges = {}
    for (a, b), group in df.groupby(["a", "b"]):
        windows = (
            group.groupby("window")[["delta", "s1", "s2", "s3"]].mean().reset_index()
        )
        if len(windows) >= 8 and (windows["window"] // 3).nunique() >= 3:
            edges[(a, b)] = windows.replace({np.nan: None}).to_dict("records")
    eligible = set(n for edge in edges for n in edge)
    components = []
    while eligible:
        component, frontier = set(), {min(eligible)}
        while frontier:
            node = frontier.pop()
            component.add(node)
            for a, b in edges:
                if node in (a, b):
                    frontier.update({a, b} - component)
        eligible -= component
        components.append(sorted(component))
    rows, pairwise, team_rows = [], [], []
    rng = np.random.default_rng(51)
    team_components = 0
    for component_id, nodes in enumerate(components, 1):
        current = {k: v for k, v in edges.items() if set(k).issubset(nodes)}
        score = _fit(nodes, current)
        blocks = sorted({r["window"] // 3 for v in current.values() for r in v})
        draws = []
        for _ in range(200):
            chosen, counts = np.unique(
                rng.choice(blocks, size=len(blocks)), return_counts=True
            )
            fit = _fit(nodes, current, dict(zip(chosen, counts)))
            if fit is not None:
                draws.append(fit)
        bootstrap = np.array(draws)
        sector_values = [_fit(nodes, current, sector=f"s{i}") for i in (1, 2, 3)]
        residual = float(
            np.sqrt(
                np.mean(
                    [
                        (
                            score[nodes.index(a)]
                            - score[nodes.index(b)]
                            - np.median([r["delta"] for r in v])
                        )
                        ** 2
                        for (a, b), v in current.items()
                    ]
                )
            )
        )
        for index, node in enumerate(nodes):
            rows.append(
                {
                    "name": node,
                    "component": component_id,
                    **_rank_summary(score, bootstrap, index),
                    "windows": len(
                        {
                            r["window"]
                            for (a, b), v in current.items()
                            if node in (a, b)
                            for r in v
                        }
                    ),
                    "rivals": len(
                        {
                            other
                            for a, b in current
                            if node in (a, b)
                            for other in (a, b)
                        }
                        - {node}
                    ),
                    "drivers": [node],
                    "fitRmsSeconds": number(residual),
                    "sectors": [
                        number(v[index]) if v is not None else None
                        for v in sector_values
                    ],
                }
            )
        for (a, b), sample in current.items():
            pairwise.append(
                {
                    "first": a,
                    "second": b,
                    "deltaSeconds": number(np.median([r["delta"] for r in sample])),
                    "windows": len(sample),
                    "component": component_id,
                }
            )
        # Equal-car weighting: average BOTH driver estimates on the SAME graph
        # reference. A team's best driver never stands in for its second car.
        teams = sorted(
            t
            for t, drivers in roster.items()
            if len(drivers) == 2 and set(drivers).issubset(nodes)
        )
        if len(teams) < 2:
            continue
        team_components += 1
        columns = [[nodes.index(d) for d in roster[t]] for t in teams]
        scores = np.array([score[c].mean() for c in columns])
        scores -= scores.mean()
        samples = (
            np.column_stack([bootstrap[:, c].mean(axis=1) for c in columns])
            if len(draws)
            else np.empty((0, len(teams)))
        )
        if len(samples):
            samples -= samples.mean(axis=1, keepdims=True)
        reference = int(np.argmin(scores))
        for i, team in enumerate(teams):
            sector = [
                np.array([v[c].mean() for c in columns]) if v is not None else None
                for v in sector_values
            ]
            team_rows.append(
                {
                    "name": team,
                    "component": component_id,
                    **_rank_summary(scores, samples, i),
                    "referenceTeam": teams[reference],
                    "gapToReferenceSeconds": number(scores[i] - scores[reference]),
                    # Use the same bootstrap draw for both teams: subtracting
                    # two marginal intervals would discard their covariance.
                    "gapInterval95": (
                        [
                            number(v)
                            for v in np.quantile(
                                samples[:, i] - samples[:, reference], [0.025, 0.975]
                            )
                        ]
                        if len(samples) >= 100
                        else None
                    ),
                    "drivers": roster[team],
                    "rivals": len(teams) - 1,
                    "windows": len(
                        {
                            p["window"]
                            for p in pairs
                            if p["a"] in roster[team] or p["b"] in roster[team]
                        }
                    ),
                    "fitRmsSeconds": number(residual),
                    "sectors": [
                        number(v[i] - v.mean()) if v is not None else None
                        for v in sector
                    ],
                }
            )
    order = lambda r: (r["component"], r["rank"], r["name"])
    return (
        {
            "rows": sorted(rows, key=order),
            "pairwise": pairwise,
            "components": len(components),
        },
        {
            "rows": sorted(team_rows, key=order),
            "pairwise": [],
            "components": team_components,
        },
    )


def analyse(session, condition="slick"):
    from .data import DATA_DIR
    from .openf1 import add_public_race_observations

    add_public_race_observations(session, DATA_DIR / "openf1")
    laps, coverage = eligible_laps(session, condition)
    pairs = comparisons(laps)
    roster = {
        str(t): sorted(g["Abbreviation"].dropna().astype(str).unique())
        for t, g in session.results.groupby("TeamName")
    }
    driver_pace, team_pace = ranking(pairs, roster)
    result = {
        "condition": condition,
        "session": session.name,
        "coverage": coverage,
        "normalisationLapSeconds": (
            number(laps["seconds"].median()) if not laps.empty else None
        ),
        "warnings": getattr(session, "data_warnings", []),
        "policy": POLICY,
        "teamPace": team_pace,
        "driverPace": driver_pace,
        "unrankedTeams": [
            t for t in roster if t not in {r["name"] for r in team_pace["rows"]}
        ],
        "status": "observed" if team_pace["rows"] else "insufficient_data",
        "method": "Same race lap (or 3-minute practice window), compound, tyre age ±1, clock time ±90s, track temperature ±2°C and same rain report. Race samples require continuous observed gap >1.5s; unknown traffic is excluded. Pairwise median differences are fitted with equal edge weight and a zero-mean constraint per connected component. Exploratory 95% intervals resample shared 3-window blocks; team scores equally average both drivers on the same connected reference. Ranks are conditional estimates, not proof of a uniquely fastest car.",
        "limitations": [
            "Car and driver effects are not identifiable separately from this weekend.",
            "Team scores equally average both driver estimates in the same connected comparison group; a missing second car prevents a team rank.",
            "Unobserved fuel loads, damage, energy deployment and actual upgrade fitment remain confounders.",
            "Practice has unknown fuel and traffic; its ranks are a long-run signal, not a race-car verdict.",
            "Slick/wet refers to tyres fitted, not measured track grip. Cool is track <30°C; warm is ≥40°C.",
            "Disconnected comparison groups cannot be ranked against each other; overlapping intervals remain inconclusive.",
        ],
    }
    if session.name == "Race":
        from .pace_bridge import analyse as coverage_estimate

        try:
            result["coverageEstimate"] = coverage_estimate(session, condition, result)
        except Exception:
            import logging

            logging.getLogger(__name__).exception(
                "Broader pace estimate failed; retaining strict evidence"
            )
            result["warnings"] = [
                *result["warnings"],
                "Adjusted race-pace estimate could not be prepared; strict evidence is retained.",
            ]
    return result
