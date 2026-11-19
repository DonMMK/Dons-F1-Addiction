"""Broader observed race-pace estimates; never a car-only causal ranking.

Keep the strict matched graph separately. This model uses quality-screened laps
with explicit nuisance controls rather than calling traffic-affected laps clean.
No names, finishing positions, points, qualifying times or prior rankings enter X.
"""

import numpy as np
import pandas as pd
from scipy import linalg
from threadpoolctl import threadpool_limits

from .data import number
from .pace_evidence import _rank_summary, _traffic, condition_laps, eligible_laps

POLICY = {
    "version": 1,
    "minimumDriverLaps": 8,
    "minimumDriverBlocks": 3,
    "blockLaps": 3,
    "draws": 400,
    "validationFolds": 5,
}


def observations(session, condition):
    frame, coverage = condition_laps(session, condition)
    if frame.empty:
        return frame, coverage
    traffic = _traffic(session)
    close, unknown = [], []
    for r in frame.itertuples():
        samples = traffic.get(str(r.DriverNumber))
        start = pd.to_datetime(r.LapStartDate, utc=True)
        end = start + r.LapTime
        if samples is not None:
            samples = samples.loc[samples.Date.between(start, end)]
        continuous = samples is not None and len(samples) >= max(3, r.seconds / 8)
        continuous = continuous and samples.Date.iloc[0] <= start + pd.Timedelta(
            seconds=10
        )
        continuous = continuous and samples.Date.iloc[-1] >= end - pd.Timedelta(
            seconds=10
        )
        continuous = (
            continuous and samples.Date.diff().dt.total_seconds().dropna().le(10).all()
        )
        if not continuous:
            close.append(0.0)
            unknown.append(1.0)
        else:
            # Fractions of observed samples, not an invented time-in-traffic trace.
            close.append(float(samples.gap.le(1.5).mean()))
            unknown.append(float(samples.gap.isna().mean()))
    frame = frame.copy()
    frame["CloseTraffic"] = close
    frame["UnknownTraffic"] = unknown
    frame["Window"] = frame.LapNumber.astype(int)
    frame["Block"] = frame.Window // POLICY["blockLaps"]
    frame = frame.loc[np.isfinite(frame.seconds) & np.isfinite(frame.TyreLife)].copy()
    return frame, coverage


def design(frame, quadratic=True):
    drivers = sorted(frame.Driver.unique())
    # Sum-to-zero driver contrasts: this fixes only the arbitrary common offset.
    h = np.vstack([np.eye(len(drivers) - 1), -np.ones(len(drivers) - 1)])
    d = np.column_stack([frame.Driver.eq(n).to_numpy(float) for n in drivers])
    nuisance = pd.get_dummies(frame.Window, dtype=float).to_numpy()
    compounds = pd.get_dummies(frame.Compound, dtype=float).to_numpy()
    age = frame.TyreLife.to_numpy(float) / 10
    controls = [
        age,
        frame.CloseTraffic.to_numpy(),
        frame.UnknownTraffic.to_numpy(),
        (frame.TrackTemp.to_numpy() - frame.TrackTemp.median()) / 10,
        frame.Rainfall.to_numpy(),
    ]
    if quadratic:
        controls.append(age**2)
    z = np.column_stack([nuisance, compounds, *controls])
    # Remove dependencies WITHIN nuisance controls, preserving their whole span.
    # A driver/tyre/traffic confounding dependency is NOT silently discarded.
    norms = np.linalg.norm(z, axis=0)
    z = z[:, norms > 1e-10] / norms[norms > 1e-10]
    q, r, _ = linalg.qr(z, mode="economic", pivoting=True)
    rank = int(np.sum(np.abs(np.diag(r)) > 1e-8))
    x = np.column_stack([d @ h, q[:, :rank]])
    scales = np.linalg.norm(x, axis=0)
    x /= scales
    singular = linalg.svdvals(x)
    if len(drivers) < 4 or len(frame) < x.shape[1] + 20 or singular[-1] < 1e-6:
        return None
    return x, h, drivers, scales


def fit(frame, quadratic=True, draws=0):
    value = design(frame, quadratic)
    if value is None:
        return None
    x, h, drivers, scales = value
    y = frame.seconds.to_numpy(float, copy=True)
    y -= np.median(y)
    w = np.ones(len(y))
    for _ in range(10):
        root = np.sqrt(w)
        inverse = linalg.pinv(x * root[:, None])
        coef = inverse @ (y * root)
        residual = y - x @ coef
        spread = max(0.05, 1.4826 * np.median(np.abs(residual - np.median(residual))))
        updated = np.minimum(1, 1.345 * spread / np.maximum(np.abs(residual), 1e-10))
        if np.max(np.abs(updated - w)) < 0.001:
            break
        w = updated
    effects = h @ (coef[: len(drivers) - 1] / scales[: len(drivers) - 1])
    samples = np.empty((0, len(drivers)))
    if draws:
        # Shared race-lap blocks keep contemporaneous driver residuals together.
        # Fixed robust weights: exploratory model intervals, not calibrated CIs.
        root = np.sqrt(w)
        inverse = linalg.pinv(x * root[:, None])
        leverage = np.sum((x * root[:, None]) * inverse.T, axis=1)
        adjusted = residual * root / np.sqrt(np.maximum(0.05, 1 - leverage))
        blocks, codes = np.unique(frame.Block, return_inverse=True)
        rng = np.random.default_rng(812)
        signs = rng.choice([-1.0, 1.0], size=(draws, len(blocks)))[:, codes]
        perturbation = (signs * adjusted) @ inverse.T
        samples = (
            effects
            + (perturbation[:, : len(drivers) - 1] / scales[: len(drivers) - 1]) @ h.T
        )
    return {
        "effects": effects,
        "samples": samples,
        "drivers": drivers,
        "residual": residual,
        "fitted": x @ coef,
        "rms": float(np.sqrt(np.mean(residual**2))),
    }


def validation(frame):
    """Held-out block pair differences: no unseen lap intercept is predicted."""
    errors, baseline = [], []
    for fold in range(POLICY["validationFolds"]):
        train = frame.loc[frame.Block.mod(POLICY["validationFolds"]).ne(fold)]
        test = frame.loc[frame.Block.mod(POLICY["validationFolds"]).eq(fold)]
        # Recover the SAME lap model in explicit coordinates for prediction.
        # Unseen lap intercepts cancel in held-out within-lap differences.
        drivers = sorted(train.Driver.unique())
        if set(test.Driver) - set(drivers):
            continue

        def matrix(f):
            return np.column_stack(
                [
                    *[f.Driver.eq(d).to_numpy(float) for d in drivers],
                    *[
                        f.Window.eq(w).to_numpy(float)
                        for w in sorted(train.Window.unique())
                    ],
                    *[
                        f.Compound.eq(c).to_numpy(float)
                        for c in sorted(frame.Compound.unique())[1:]
                    ],
                    f.TyreLife.to_numpy(float) / 10,
                    (f.TyreLife.to_numpy(float) / 10) ** 2,
                    f.CloseTraffic,
                    f.UnknownTraffic,
                    f.TrackTemp / 10,
                    f.Rainfall,
                ]
            )

        # Difference rows remove race-lap fixed effects exactly.
        def differences(f):
            m = matrix(f)
            teams = f.Team.to_numpy()
            seconds = f.seconds.to_numpy(float)
            xx, yy, windows = [], [], []
            for window, indices in f.groupby("Window").indices.items():
                a, b = np.triu_indices(len(indices), 1)
                a, b = np.asarray(indices)[a], np.asarray(indices)[b]
                keep = teams[a] != teams[b]
                a, b = a[keep], b[keep]
                xx.extend(m[a] - m[b])
                yy.extend(seconds[a] - seconds[b])
                windows.extend([window] * len(a))
            return np.asarray(xx), np.asarray(yy), windows

        xv, yv, windows = differences(test)
        model = fit(train, quadratic=True)
        if model is None or not len(yv):
            continue
        xt = matrix(train)
        # Test differences must be identifiable from training differences.
        inverse = linalg.pinv(xt)
        estimable = np.linalg.norm(xv - xv @ inverse @ xt, axis=1) < 1e-6
        if not estimable.any():
            continue
        coef = inverse @ model["fitted"]
        evaluation = pd.DataFrame(
            {"window": windows, "error": np.abs(yv - xv @ coef), "baseline": np.abs(yv)}
        )
        evaluation = evaluation.loc[estimable].groupby("window").median()
        errors.extend(evaluation.error.tolist())
        baseline.extend(evaluation.baseline.tolist())
    return {
        "heldOutWindows": len(errors),
        "pairDifferenceMaeSeconds": number(np.mean(errors)) if errors else None,
        "zeroDifferenceMaeSeconds": number(np.mean(baseline)) if baseline else None,
        "note": "Five held-out race-lap-block folds of the quadratic model; median cross-team pair error per lap, then mean. Tests observed lap differences, not true car pace or future races.",
    }


def analyse(session, condition, strict):
    with threadpool_limits(limits=1):
        return _analyse(session, condition, strict)


def _analyse(session, condition, strict):
    roster = {
        str(t): sorted(g.Abbreviation.dropna().astype(str).unique())
        for t, g in session.results.groupby("TeamName")
    }
    frame, coverage = observations(session, condition)
    strict_laps, _ = eligible_laps(session, condition)
    strict_drivers = {r["name"]: r["component"] for r in strict["driverPace"]["rows"]}
    diagnostics = []
    for team, drivers in roster.items():
        cars = []
        for driver in drivers:
            laps = frame.loc[frame.Driver.eq(driver)] if not frame.empty else frame
            cars.append(
                {
                    "driver": driver,
                    "usableLaps": len(laps),
                    "clearAirLaps": (
                        int(strict_laps.Driver.eq(driver).sum())
                        if not strict_laps.empty
                        else 0
                    ),
                    "strictComponent": strict_drivers.get(driver),
                    "trafficObservedFraction": (
                        number(1 - laps.UnknownTraffic.mean()) if len(laps) else None
                    ),
                }
            )
        components = [c["strictComponent"] for c in cars]
        reason = (
            "Both drivers connected"
            if len(components) == 2
            and None not in components
            and len(set(components)) == 1
            else (
                "Drivers are in separate matched groups"
                if len(components) == 2 and None not in components
                else "At least one driver lacks eight matched windows across three blocks"
            )
        )
        diagnostics.append({"team": team, "drivers": cars, "strictReason": reason})
    result = {
        "condition": condition,
        "session": session.name,
        "view": "adjusted",
        "coverage": {**coverage, "used": 0},
        "normalisationLapSeconds": None,
        "teamPace": {"rows": [], "components": 0},
        "unrankedTeams": sorted(roster),
        "diagnostics": diagnostics,
        "validation": None,
        "warnings": [],
        "policy": POLICY,
        "method": "Robust observed-race-lap model with driver contrasts, race-lap fixed effects, compound, tyre age, observed close-traffic sample fraction, unknown-traffic fraction and weather. Linear/quadratic tyre-age sensitivity; shared three-lap wild residual blocks. Equal weights for both estimated drivers of a team. No results, points, named-team priors or qualifying bonuses.",
        "limitations": [
            "Adjusted observed package pace combines car, driver and strategy; it does not identify the fastest physical car.",
            "Race-lap effects are a shared time proxy, not measured fuel correction. Fuel, setup, damage and energy deployment remain unknown.",
            "Traffic adjustment assumes common associations across drivers; missing intervals are explicitly unknown, never clear air. Sustained management can remain in driver effects.",
            "Intervals are exploratory and conditional on model assumptions, robust weights and this race; they are not calibrated 95% guarantees. Overlapping ranges leave order uncertain.",
            "A single-car proxy uses only the observed driver, with missing-car sensitivity from this race's paired teammate differences. It is not an equal two-car estimate.",
            "No current-race observations means no numerical estimate. Unidentifiable controls or disconnected timing cannot be repaired by assigning a prior ranking.",
        ],
    }
    if frame.empty:
        return result
    counts = frame.groupby("Driver").agg(
        laps=("Window", "nunique"), blocks=("Block", "nunique")
    )
    eligible = counts.index[
        (counts.laps >= POLICY["minimumDriverLaps"])
        & (counts.blocks >= POLICY["minimumDriverBlocks"])
    ]
    frame = frame.loc[frame.Driver.isin(eligible)].copy()
    # A shared lap with at least two cars is required; isolated timing supplies
    # no between-driver information even if a car has many laps.
    while len(frame):
        before = len(frame)
        frame = frame.groupby("Window", group_keys=False).filter(
            lambda g: g.Driver.nunique() >= 2
        )
        counts = frame.groupby("Driver").agg(
            laps=("Window", "nunique"), blocks=("Block", "nunique")
        )
        eligible = counts.index[
            (counts.laps >= POLICY["minimumDriverLaps"])
            & (counts.blocks >= POLICY["minimumDriverBlocks"])
        ]
        frame = frame.loc[frame.Driver.isin(eligible)].copy()
        if len(frame) == before:
            break
    models = (
        [
            m
            for quadratic in (False, True)
            if (m := fit(frame, quadratic, POLICY["draws"] // 2)) is not None
        ]
        if len(frame)
        else []
    )
    if len(models) != 2:
        result["warnings"].append(
            "Adjusted contrasts are not identifiable with both tyre-age specifications; no numerical field ranking was manufactured."
        )
        return result
    names = models[0]["drivers"]
    effects = np.mean([m["effects"] for m in models], axis=0)
    samples = np.vstack([m["samples"] for m in models])
    paired = [ds for ds in roster.values() if len(ds) == 2 and set(ds).issubset(names)]
    teammate_sensitivity = np.array(
        [
            (effects[names.index(ds[0])] - effects[names.index(ds[1])]) / 2
            for ds in paired
        ]
    )
    rows, team_samples, scores = [], [], []
    rng = np.random.default_rng(819)
    strict_teams = {r["name"] for r in strict["teamPace"]["rows"]}
    for team, ds in sorted(roster.items()):
        available = [d for d in ds if d in names]
        if not available:
            continue
        columns = [names.index(d) for d in available]
        draw = samples[:, columns].mean(axis=1)
        proxy = len(ds) != 2 or len(available) != 2
        if proxy:
            if len(teammate_sensitivity) < 3:
                continue
            draw += rng.choice(np.abs(teammate_sensitivity), len(draw)) * rng.choice(
                [-1, 1], len(draw)
            )
        rows.append(
            {
                "name": team,
                "component": 1,
                "drivers": available,
                "expectedDrivers": ds,
                "evidenceTier": "single_car" if proxy else "adjusted_two_car",
                "strictMatched": team in strict_teams,
                "windows": int(
                    frame.loc[frame.Driver.isin(available), "Window"].nunique()
                ),
                "driverLaps": {d: int(frame.Driver.eq(d).sum()) for d in available},
                "rivals": 0,
                "fitRmsSeconds": number(np.mean([m["rms"] for m in models])),
            }
        )
        scores.append(float(effects[columns].mean()))
        team_samples.append(draw)
    if len(rows) < 2:
        return result
    scores = np.asarray(scores)
    draws = np.column_stack(team_samples)
    scores -= scores.mean()
    draws -= draws.mean(axis=1, keepdims=True)
    reference = int(np.argmin(scores))
    for i, row in enumerate(rows):
        row.update(_rank_summary(scores, draws, i))
        row.update(
            {
                "referenceTeam": rows[reference]["name"],
                "rivals": len(rows) - 1,
                "gapInterval95": [
                    number(v)
                    for v in np.quantile(
                        draws[:, i] - draws[:, reference], [0.025, 0.975]
                    )
                ],
            }
        )
    result["teamPace"] = {
        "rows": sorted(rows, key=lambda r: (r["rank"], r["name"])),
        "components": 1,
    }
    result["unrankedTeams"] = sorted(set(roster) - {r["name"] for r in rows})
    result["coverage"]["used"] = len(frame)
    result["normalisationLapSeconds"] = number(frame.seconds.median())
    result["validation"] = validation(frame)
    check = result["validation"]
    if check["pairDifferenceMaeSeconds"] is None:
        result["warnings"].append(
            "Held-out pair validation unavailable; treat the adjusted order as provisional."
        )
    elif check["pairDifferenceMaeSeconds"] >= check["zeroDifferenceMaeSeconds"]:
        result["warnings"].append(
            "Held-out pair error did not improve on a zero-difference baseline; treat the adjusted order as provisional."
        )
    return result
