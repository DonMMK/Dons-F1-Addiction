"""Versioned winner model: numeric evidence only, chronological validation.

Artifacts are JSON coefficients (never untrusted pickle). No driver or team IDs
are training features. Training is an explicit offline command, not a public API.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from .data import (
    DATA_DIR,
    clean_laps,
    finished,
    iso,
    load_session,
    number,
    seconds,
    utc_now,
)

MODEL_DIR = DATA_DIR / "models"
FEATURES = [
    "qualifyingGapPercent",
    "qualifyingRankFraction",
    "practiceRelativePacePercent",
    "practiceMissing",
]


def features(year, event, session_type="Q"):
    session = load_session(year, event, session_type, results_only=session_type == "Q")
    cutoff = pd.Timestamp(session.date)
    if cutoff.tzinfo is None:
        cutoff = cutoff.tz_localize("UTC")
    if cutoff >= pd.Timestamp.now(tz="UTC") or not finished(session):
        raise ValueError("Select a completed session with published timing")
    rows = session.results.copy()
    rows = rows.loc[rows["Abbreviation"].notna() & rows["Abbreviation"].ne("")]
    rows = rows.sort_values("Position", na_position="last")
    if rows.empty:
        raise ValueError("No driver results")
    field = len(rows)
    # All Q comparisons use Q1; no Q1/Q3 mix caused by track evolution.
    times = {}
    if session_type == "Q":
        for _, row in rows.iterrows():
            times[str(row["Abbreviation"])] = seconds(row.get("Q1"))
    else:
        clean = clean_laps(session.laps)
        for driver, df in clean.groupby("Driver"):
            times[str(driver)] = number(df["seconds"].min())
    valid = [v for v in times.values() if v is not None and v > 0]
    if not valid:
        raise ValueError("No valid timed laps for prediction features")
    best = min(valid)
    practice, practice_kind = None, None
    # Never load a later practice session into an earlier-session prediction.
    for kind in ("FP3", "FP2", "FP1"):
        try:
            candidate = session.event.get_session(kind)
            start = pd.Timestamp(candidate.date)
            if start.tzinfo is None:
                start = start.tz_localize("UTC")
            if start <= cutoff:
                candidate = load_session(year, event, kind)
                if finished(candidate):
                    practice, practice_kind = candidate, kind
                    break
        except Exception:
            continue
    relative = {}
    if practice is not None:
        clean = clean_laps(practice.laps)
        # Long-run samples; compare relative to compound's field median.
        if not clean.empty:
            clean = clean.groupby(["Driver", "Stint"], group_keys=False).filter(
                lambda group: len(group) >= 3
            )
            if not clean.empty:
                benchmark = clean.groupby("Compound")["seconds"].transform("median")
                clean["relative"] = 100 * (clean["seconds"] / benchmark - 1)
                relative = clean.groupby("Driver")["relative"].median().to_dict()
    entries = []
    for i, (_, row) in enumerate(rows.iterrows()):
        driver = str(row["Abbreviation"])
        lap = times.get(driver)
        entries.append(
            {
                "driver": driver,
                "team": str(row["TeamName"]),
                "values": [
                    (
                        100 * (lap / best - 1)
                        if lap is not None
                        else max(5.0, 100 * (max(valid) / best - 1))
                    ),
                    i / max(field - 1, 1),
                    float(relative.get(driver, 0)),
                    0.0 if driver in relative else 1.0,
                ],
            }
        )
    return (
        session,
        entries,
        {
            "cutoff": cutoff.isoformat(),
            "practiceSession": practice_kind,
            "practiceSource": getattr(practice, "data_source", None),
            "dataWarnings": (
                list(getattr(practice, "data_warnings", []))
                if practice is not None
                else [
                    "No pre-cutoff raw practice data is available. Practice features use the model's explicit missing-data indicator."
                ]
            ),
            "qualifyingSource": getattr(session, "data_source", "FastF1"),
            "featureNames": FEATURES,
            "qualifyingBasis": "Q1" if session_type == "Q" else "practice best lap",
        },
    )


def infer(artifact, entries):
    if artifact["featureNames"] != FEATURES:
        raise ValueError("Model feature schema mismatch; retrain this artifact")
    x = np.array([row["values"] for row in entries], dtype=float)
    score = ((x - np.array(artifact["mean"])) / np.array(artifact["scale"])) @ np.array(
        artifact["coef"]
    ) + artifact["intercept"]
    # Logistic one-vs-rest scores normalized over this event's actual field.
    logits = 1 / (1 + np.exp(-np.clip(score, -40, 40)))
    return logits / logits.sum()


def metrics(events, predictions):
    if not events:
        raise ValueError("No complete events to evaluate")
    brier, loss, hits = [], [], []
    for event, probs in zip(events, predictions):
        y = np.array(
            [1.0 if e["driver"] == event["winner"] else 0.0 for e in event["entries"]]
        )
        brier.append(float(np.sum((probs - y) ** 2)))
        winner_index = int(np.argmax(y))
        loss.append(float(-np.log(max(float(probs[winner_index]), 1e-15))))
        hits.append(int(np.argmax(probs)) == winner_index)
    return {
        "events": len(events),
        "brier": number(np.mean(brier)),
        "logLoss": number(np.mean(loss)),
        "top1Accuracy": number(np.mean(hits)),
    }


def fit(events, c):
    x = np.array([entry["values"] for event in events for entry in event["entries"]])
    y = np.array(
        [
            int(entry["driver"] == event["winner"])
            for event in events
            for entry in event["entries"]
        ]
    )
    scaler = StandardScaler().fit(x)
    model = LogisticRegression(C=c, max_iter=2000, random_state=17).fit(
        scaler.transform(x), y
    )
    return {
        "featureNames": FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "regularizationC": c,
    }


def artifacts():
    MODEL_DIR.mkdir(exist_ok=True)
    result = []
    for path in sorted(MODEL_DIR.glob("v13-*.json")):
        try:
            artifact = json.loads(path.read_text())
            if artifact["id"] == path.stem:
                result.append(artifact)
        except (ValueError, KeyError):
            continue
    return sorted(result, key=lambda r: (r["trainedThrough"], r["createdAt"]))


def train(year_from, year_to, through_round=None, min_events=15):
    import fastf1

    events, skipped = [], []
    for year in range(year_from, year_to + 1):
        from .events import get_schedule

        schedule = get_schedule(year, include_testing=False)
        for _, event in schedule.iterrows():
            rd = int(event["RoundNumber"])
            if year == year_to and through_round is not None and rd > through_round:
                continue
            if (
                pd.Timestamp(event["EventDate"]).date()
                >= datetime.now(timezone.utc).date()
            ):
                continue
            try:
                qualifying, entries, meta = features(year, rd, "Q")
                race = load_session(year, rd, "R", results_only=True)
                if not finished(race):
                    raise ValueError("Race not finished")
                results = race.results.sort_values("Position")
                winner = str(results.iloc[0]["Abbreviation"])
                if winner not in {e["driver"] for e in entries}:
                    raise ValueError("Winner missing from pre-race field")
                # Require label availability after the race, not just its start.
                # A published classification is enough for labels; don't require
                # protected raw laps. Use a conservative next-day availability
                # boundary when exact result publication time is unobserved.
                race_start = pd.Timestamp(race.date)
                if race_start.tzinfo is None:
                    race_start = race_start.tz_localize("UTC")
                label_cutoff = race_start + pd.Timedelta(days=1)
                if label_cutoff > pd.Timestamp.now(tz="UTC"):
                    raise ValueError("Result publication buffer has not elapsed")
                events.append(
                    {
                        "key": f"{year}-{rd}",
                        "year": year,
                        "round": rd,
                        "winner": winner,
                        "entries": entries,
                        "cutoff": meta["cutoff"],
                        "labelCutoff": label_cutoff.isoformat(),
                        "qualifyingSource": meta.get("qualifyingSource"),
                        "practiceSource": meta.get("practiceSource"),
                    }
                )
            except Exception as exc:
                skipped.append({"event": f"{year}-{rd}", "reason": str(exc)})
    events.sort(key=lambda e: e["cutoff"])
    if len(events) < min_events:
        raise ValueError(
            f"Need {min_events} complete races; loaded {len(events)}. Skipped: {skipped}"
        )
    first, second = int(len(events) * 0.6), int(len(events) * 0.8)
    train_events, validation, test = (
        events[:first],
        events[first:second],
        events[second:],
    )
    candidates = []
    for c in (0.1, 1.0, 10.0):
        artifact = fit(train_events, c)
        score = metrics(validation, [infer(artifact, e["entries"]) for e in validation])
        candidates.append((score["logLoss"], c))
    best_c = min(candidates)[1]
    heldout_model = fit(train_events + validation, best_c)
    heldout = metrics(test, [infer(heldout_model, e["entries"]) for e in test])
    uniform = metrics(
        test, [np.ones(len(e["entries"])) / len(e["entries"]) for e in test]
    )
    # Fixed comparator: 50% to first qualifying position, balance to other drivers.
    grid = metrics(
        test,
        [
            np.array([0.5] + [0.5 / (len(e["entries"]) - 1)] * (len(e["entries"]) - 1))
            for e in test
        ],
    )
    prior = artifacts()
    prior_score = None
    if prior and prior[-1]["trainedThrough"] < test[0]["cutoff"]:
        prior_score = metrics(test, [infer(prior[-1], e["entries"]) for e in test])
    artifact = fit(events, best_c)
    manifest = {
        "events": [e["key"] for e in events],
        "cutoff": events[-1]["labelCutoff"],
        "features": FEATURES,
        "c": best_c,
        "algorithmVersion": 2,
        "timingPolicy": "OpenF1 screened historical laps or FastF1 validated cache/archive",
        "datasetHash": hashlib.sha256(
            json.dumps(events, sort_keys=True).encode()
        ).hexdigest(),
    }
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()[
        :12
    ]
    artifact.update(
        id=f"v13-{digest}",
        name="Empirical winner model",
        version=13,
        createdAt=utc_now(),
        trainedThrough=max(e["labelCutoff"] for e in events),
        trainingEvents=len(events),
        trainingEventKeys=manifest["events"],
        heldoutEventKeys=[e["key"] for e in test],
        metrics=heldout,
        baselines={"uniform": uniform, "qualifyingLeader50Percent": grid},
        previousComparable=prior_score,
        improvesGridLogLoss=heldout["logLoss"] < grid["logLoss"],
        improvements=[
            "Learned numeric coefficients; no driver names or team tiers",
            "Whole-race chronological 60/20/20 split; regularization chosen only on validation",
            "Untouched test scores reported before final refit on all included races",
        ],
        limitations=[
            "Small observational sample; improvement is not guaranteed",
            "Practice fuel, traffic and setup are unobserved",
            "Test scores describe the held-out fit, not the final refit",
        ],
        skipped=skipped,
    )
    MODEL_DIR.mkdir(exist_ok=True)
    path = MODEL_DIR / f'{artifact["id"]}.json'
    # One immutable iteration per training manifest; reruns reuse its existing audit record.
    if path.exists():
        return json.loads(path.read_text())
    temp = MODEL_DIR / f".{artifact['id']}-{uuid.uuid4().hex}.tmp"
    temp.write_text(json.dumps(artifact, indent=2, allow_nan=False))
    try:
        # Link creation is atomic and cannot replace an existing iteration.
        os.link(temp, path)
    except FileExistsError:
        return json.loads(path.read_text())
    finally:
        temp.unlink(missing_ok=True)
    return artifact
