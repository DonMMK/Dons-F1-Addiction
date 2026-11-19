"""Offline regression tests: no upstream downloads or private data required."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app
from backend.routers import prediction, standings
from backend.services import empirical_model as ml, prediction_store as store
from backend.services.data import clean_laps
from backend.services.ical import parse_ics
from backend.services.weekend import (
    matched_laps,
    interval,
    degradation,
    qualifying_gap,
    field_pace,
)


def laps():
    rows = []
    for lap in range(1, 19):
        for driver, offset in [("AAA", 0.0), ("BBB", 0.4)]:
            rows.append(
                dict(
                    Driver=driver,
                    LapNumber=lap,
                    Compound="MEDIUM",
                    TyreLife=lap,
                    Stint=1,
                    LapTime=pd.Timedelta(seconds=80 + offset + lap * 0.01),
                    IsAccurate=True,
                    TrackStatus="1",
                    PitInTime=pd.NaT,
                    PitOutTime=pd.NaT,
                    Deleted=False,
                    FastF1Generated=False,
                )
            )
    return pd.DataFrame(rows)


def fake_events(count=30):
    result = []
    for i in range(count):
        entries = [
            {"driver": d, "values": [float(k), k / 3, k * 0.1, 0.0]}
            for k, d in enumerate(("AAA", "BBB", "CCC", "DDD"))
        ]
        result.append(
            {"key": str(i), "entries": entries, "winner": "AAA" if i % 4 else "BBB"}
        )
    return result


class Teammates(unittest.TestCase):
    def test_clean_excludes_pits_flags_deleted_and_synthesized(self):
        df = laps()
        df["PitInTime"] = pd.Series(pd.NaT, index=df.index, dtype="timedelta64[ns]")
        df.loc[0, "PitInTime"] = pd.Timedelta(seconds=1)
        df.loc[1, "TrackStatus"] = "14"
        df.loc[2, "Deleted"] = True
        df.loc[3, "FastF1Generated"] = True
        df.loc[4, "IsAccurate"] = False
        self.assertEqual(len(clean_laps(df)), len(df) - 5)

    def test_same_lap_compound_and_age_only(self):
        df = laps()
        df.loc[(df.Driver == "BBB") & (df.LapNumber == 2), "Compound"] = "HARD"
        df.loc[(df.Driver == "BBB") & (df.LapNumber == 3), "TyreLife"] = 20
        pairs = matched_laps(df, "AAA", "BBB")
        self.assertEqual(len(pairs), 16)
        self.assertAlmostEqual(pairs.delta.median(), -0.4)
        self.assertNotIn(2, pairs.LapNumber.tolist())
        self.assertNotIn(3, pairs.LapNumber.tolist())

    def test_interval_and_small_sample(self):
        pairs = matched_laps(laps(), "AAA", "BBB")
        self.assertIsNone(interval(pairs.head(7)))
        low, high = interval(pairs)
        self.assertAlmostEqual(low, -0.4)
        self.assertAlmostEqual(high, -0.4)

    def test_age_race_lap_collinearity_never_claims_wear(self):
        self.assertIsNone(degradation(laps(), "AAA")[0]["slopeSecondsPerTyreLap"])

    def test_field_pace_matches_compound_and_age_without_identity_bonuses(self):
        df = laps()
        third = df[df.Driver.eq("AAA")].copy()
        third["Driver"] = "CCC"
        third["LapTime"] += pd.Timedelta(seconds=0.8)
        df = pd.concat([df, third], ignore_index=True)
        results = pd.DataFrame(
            [
                {"Abbreviation": d, "TeamName": "Team", "Position": i + 1}
                for i, d in enumerate(["AAA", "BBB", "CCC"])
            ]
        )
        race = SimpleNamespace(laps=df, results=results)
        report = field_pace(race, SimpleNamespace(results=results))
        self.assertLess(report[0]["relativePacePercent"], 0)
        self.assertGreater(report[2]["relativePacePercent"], 0)
        self.assertEqual(report[0]["matchedLaps"], 18)
        self.assertIsNone(
            field_pace(SimpleNamespace(laps=laps(), results=results), None)[0][
                "relativePacePercent"
            ]
        )

    def test_qualifying_uses_shared_segment(self):
        q1 = laps()
        q2 = laps().query("Driver=='AAA'")
        q3 = q2
        session = SimpleNamespace(
            laps=SimpleNamespace(split_qualifying_sessions=lambda: [q1, q2, q3])
        )
        value = qualifying_gap(session, "AAA", "BBB")
        self.assertEqual(value["segment"], "Q1")
        self.assertAlmostEqual(value["deltaSeconds"], -0.4)


class Standings(unittest.TestCase):
    def test_movement_and_new_driver(self):
        current = [
            dict(id="a", position=1, points=80),
            dict(id="new", position=2, points=9),
        ]
        previous = [dict(id="a", position=3, points=55)]
        result = standings.changes(current, previous)
        self.assertEqual(result[0]["positionChange"], 2)
        self.assertEqual(result[0]["pointsChange"], 25)
        self.assertIsNone(result[1]["positionChange"])
        self.assertIsNone(result[1]["pointsChange"])

    def test_same_round_for_both_championships(self):
        def response(data, rd):
            return SimpleNamespace(
                content=[pd.DataFrame(data)], description=pd.DataFrame([{"round": rd}])
            )

        driver = dict(
            driverId="a",
            driverCode="AAA",
            givenName="A",
            familyName="Driver",
            constructorNames=["Team"],
            position=1,
            points=100,
            wins=1,
        )
        cons = dict(
            constructorId="t", constructorName="Team", position=1, points=100, wins=1
        )
        client = SimpleNamespace(
            get_driver_standings=lambda **kw: response(
                [driver], 3 if kw["round"] == "last" else kw["round"]
            ),
            get_constructor_standings=lambda **kw: response([cons], kw["round"]),
        )
        standings.snapshot.cache_clear()
        with patch.object(standings, "Ergast", return_value=client):
            result = standings.snapshot(2025, None, 0)
        self.assertEqual(result["round"], 3)
        self.assertEqual(result["previousRound"], 2)
        self.assertEqual(result["constructors"][0]["pointsChange"], 0)
        standings.snapshot.cache_clear()


class Models(unittest.TestCase):
    def test_numeric_version_order_and_exact_ids(self):
        self.assertEqual(
            list(prediction._discover_versions()), [f"v{i}" for i in range(1, 13)]
        )

    def test_v1_weights_are_normalized(self):
        probs, _, _ = prediction.normalize_counts({"AAA": 50, "BBB": 30, "CCC": 10})
        self.assertAlmostEqual(sum(probs.values()), 1.0)

    def test_v12_tuple(self):
        probs, margins, _ = prediction.normalize_counts(
            ({"AAA": 8, "BBB": 2}, {"0-5": 10})
        )
        self.assertEqual(probs["AAA"], 0.8)
        self.assertEqual(margins, {"0-5": 10})

    def test_invalid_distribution_rejected(self):
        for value in ({"AAA": 0}, {"AAA": np.nan}, {"AAA": -1, "BBB": 3}):
            with self.assertRaises(ValueError):
                prediction.normalize_counts(value)

    def test_timedelta_fix_all_quali_models(self):
        frame = pd.DataFrame({"Abbreviation": ["AAA"], "Q3": pd.to_timedelta(["80s"])})
        for key in ("v10", "v11", "v12"):
            module = prediction._load_module(prediction._discover_versions()[key])
            sim = module.RaceSimulator(frame, "Bahrain")
            self.assertEqual(sim.get_quali_pace("AAA"), 80.0)

    def test_every_legacy_constructor_and_output(self):
        frame = pd.DataFrame(
            {
                "Abbreviation": ["AAA", "BBB"],
                "Q1": pd.to_timedelta(["80s", "81s"]),
                "Q2": pd.to_timedelta(["80s", "81s"]),
                "Q3": pd.to_timedelta(["80s", "81s"]),
                "GridPosition": [1, 2],
                "Position": [1, 2],
            }
        )
        for model, path in prediction._discover_versions().items():
            module = prediction._load_module(path)
            module.Config.MONTE_CARLO_RUNS = 5
            session = SimpleNamespace(
                results=frame,
                event=SimpleNamespace(
                    get_session=lambda _: (_ for _ in ()).throw(
                        ValueError("no practice")
                    )
                ),
            )
            with patch.object(prediction, "_load_module", return_value=module):
                probs, _, _, _, _ = prediction.legacy(
                    prediction.PredictionRequest(year=2025, gp="Bahrain", model=model),
                    session,
                )
            self.assertAlmostEqual(sum(probs.values()), 1.0, msg=model)
            self.assertEqual(set(probs), {"AAA", "BBB"})

    def test_empirical_model_has_no_names_as_features_and_sums_to_one(self):
        model = ml.fit(fake_events(), 1.0)
        self.assertFalse(
            any(
                "driver" in f.lower() or "team" in f.lower()
                for f in model["featureNames"]
            )
        )
        p = ml.infer(model, fake_events()[0]["entries"])
        self.assertAlmostEqual(float(p.sum()), 1.0)
        self.assertTrue(np.isfinite(p).all())

    def test_scores_penalize_confident_wrong_winner(self):
        event = fake_events(1)
        right = ml.metrics(event, [np.array([0.1, 0.7, 0.1, 0.1])])
        wrong = ml.metrics(event, [np.array([0.97, 0.01, 0.01, 0.01])])
        self.assertLess(right["logLoss"], wrong["logLoss"])
        self.assertLess(right["brier"], wrong["brier"])

    def test_future_training_cutoff_rejected_before_inference(self):
        client = TestClient(app)
        session = SimpleNamespace(date=pd.Timestamp("2025-03-01"))
        with patch.object(
            prediction, "load_session", return_value=session
        ), patch.object(prediction, "finished", return_value=True), patch.object(
            prediction,
            "features",
            return_value=(session, [], {"cutoff": "2025-03-01T00:00:00+00:00"}),
        ), patch.object(
            prediction,
            "artifacts",
            return_value=[
                {"id": "v13-test", "trainedThrough": "2026-01-01T00:00:00+00:00"}
            ],
        ):
            res = client.post(
                "/api/prediction/run",
                json={"year": 2025, "gp": "Bahrain", "model": "v13-test"},
            )
        self.assertEqual(res.status_code, 422)
        self.assertIn("after the selected", res.json()["detail"])

    def test_training_has_disjoint_chronological_holdout_and_new_manifest(self):
        schedule = pd.DataFrame(
            [
                {
                    "RoundNumber": i,
                    "EventDate": pd.Timestamp("2024-01-01") + pd.Timedelta(days=i * 7),
                }
                for i in range(1, 21)
            ]
        )

        def feature_stub(year, rd, kind):
            event = fake_events(20)[rd - 1]
            date = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(days=rd * 7)
            return None, event["entries"], {"cutoff": date.isoformat()}

        def race_stub(year, rd, kind, **kwargs):
            event = fake_events(20)[rd - 1]
            date = pd.Timestamp("2024-01-01", tz="UTC") + pd.Timedelta(
                days=rd * 7, hours=24
            )
            return SimpleNamespace(
                date=date,
                results=pd.DataFrame(
                    [{"Position": 1, "Abbreviation": event["winner"]}]
                ),
                laps=pd.DataFrame({"LapStartDate": [date]}),
            )

        with tempfile.TemporaryDirectory() as temp, patch.object(
            ml, "MODEL_DIR", Path(temp)
        ), patch.object(ml, "features", side_effect=feature_stub), patch.object(
            ml, "load_session", side_effect=race_stub
        ), patch.object(
            ml, "finished", return_value=True
        ), patch(
            "fastf1.get_event_schedule", return_value=schedule
        ):
            result = ml.train(2024, 2024)
            self.assertEqual(
                result["heldoutEventKeys"], ["2024-17", "2024-18", "2024-19", "2024-20"]
            )
            self.assertEqual(result["trainingEvents"], 20)
            self.assertEqual(result["metrics"]["events"], 4)
            self.assertEqual(result["baselines"]["uniform"]["events"], 4)
            self.assertEqual(len(list(Path(temp).glob("v13-*.json"))), 1)
            again = ml.train(2024, 2024)
            self.assertEqual(result["id"], again["id"])


class PersistenceAndEvaluation(unittest.TestCase):
    def test_snapshots_survive_new_connections_and_are_immutable(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(
            store, "DATA_DIR", Path(temp)
        ):
            original = {"createdAt": "2025-01-01", "probabilities": {"AAA": 1.0}}
            saved = store.save(original)
            original["probabilities"]["AAA"] = 0.0
            self.assertEqual(store.get(saved["runId"])["probabilities"]["AAA"], 1.0)
            self.assertEqual(len(store.recent()), 1)

    def test_evaluation_scores_saved_probabilities(self):
        run = {
            "year": 2025,
            "round": 1,
            "mode": "pre-race",
            "probabilities": {"AAA": 0.8, "BBB": 0.2},
        }
        race = SimpleNamespace(
            results=pd.DataFrame(
                [
                    {"Position": 1, "Abbreviation": "BBB"},
                    {"Position": 2, "Abbreviation": "AAA"},
                ]
            )
        )
        with patch.object(store, "get", return_value=run), patch.object(
            prediction, "load_session", return_value=race
        ), patch.object(prediction, "finished", return_value=True):
            result = prediction.evaluate("id")
        self.assertFalse(result["correct"])
        self.assertAlmostEqual(result["brier"], 1.28)
        self.assertAlmostEqual(result["logLoss"], 1.6094, places=4)

    def test_unfinished_race_not_scored(self):
        with patch.object(
            store, "get", return_value={"year": 2025, "round": 1}
        ), patch.object(
            prediction, "load_session", return_value=object()
        ), patch.object(
            prediction, "finished", return_value=False
        ):
            self.assertEqual(prediction.evaluate("id")["status"], "pending")


class Calendars(unittest.TestCase):
    def parse(self, body):
        return parse_ics(
            "BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nUID:test\nSUMMARY:Race\n"
            + body
            + "\nEND:VEVENT\nEND:VCALENDAR",
            "wec",
            "https://example.com",
            "2026-11-07",
        )

    def test_utc_session(self):
        row = self.parse("DTSTART:20261108T100000Z")[0]
        self.assertEqual(row["start"], "2026-11-08T10:00:00+00:00")
        self.assertFalse(row["dateOnly"])

    def test_dst_conversion(self):
        row = self.parse("DTSTART;TZID=Australia/Sydney:20261011T110000")[0]
        self.assertEqual(row["start"], "2026-10-11T00:00:00+00:00")

    def test_date_only_not_shifted(self):
        row = self.parse("DTSTART;VALUE=DATE:20261106\nDTEND;VALUE=DATE:20261109")[0]
        self.assertEqual(row["start"], "2026-11-06")
        self.assertEqual(row["end"], "2026-11-09")
        self.assertTrue(row["dateOnly"])

    def test_floating_and_recurring_rejected(self):
        for text in (
            "DTSTART:20261108T100000",
            "DTSTART:20261108T100000Z\nRRULE:FREQ=DAILY",
        ):
            with self.assertRaises(ValueError):
                self.parse(text)

    def test_cancelled_event_omitted(self):
        self.assertEqual(self.parse("DTSTART:20261108T100000Z\nSTATUS:CANCELLED"), [])

    def test_shipped_snapshots_have_explicit_dates_and_https_sources(self):
        path = Path(__file__).resolve().parents[2] / "data" / "motorsport-2026.json"
        data = json.loads(path.read_text())
        self.assertEqual(len({e["id"] for e in data["events"]}), len(data["events"]))
        for event in data["events"]:
            self.assertTrue(event["sourceUrl"].startswith("https://"))
            if not event["dateOnly"]:
                self.assertIsNotNone(pd.Timestamp(event["start"]).tzinfo)


if __name__ == "__main__":
    unittest.main()
