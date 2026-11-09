"""Strategy and lap comparisons must keep gaps and assumptions visible."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app
from backend.services.strategy_evidence import strategy_report
from backend.services.track_evidence import compare_speed_zones, speed_map, lap_options
from backend.services.loading_errors import SessionDataError


def laps():
    return pd.DataFrame(
        [
            dict(
                Driver=driver,
                Team="Test team",
                LapNumber=i,
                Compound="MEDIUM",
                TyreLife=i,
                Stint=1,
                LapTime=pd.Timedelta(seconds=80 + i / 10),
                IsAccurate=True,
                TrackStatus="1",
                PitInTime=pd.NaT,
                PitOutTime=pd.NaT,
                Deleted=False,
                FastF1Generated=False,
            )
            for driver in ("AAA", "BBB")
            for i in range(1, 11)
        ]
    )


def telemetry(duration=80):
    t = np.linspace(0, duration, 401)
    return pd.DataFrame(
        dict(
            Time=pd.to_timedelta(t, unit="s"),
            Distance=np.linspace(0, 4500, len(t)),
            Speed=210 + 80 * np.cos(t / 4),
            X=1000 * np.cos(t / duration * 2 * np.pi),
            Y=1000 * np.sin(t / duration * 2 * np.pi),
        )
    )


def lap_record(n=1):
    return pd.Series(
        dict(
            LapTime=pd.Timedelta(seconds=80),
            LapNumber=n,
            Sector1Time=pd.Timedelta(seconds=25),
            Sector2Time=pd.Timedelta(seconds=25),
        )
    )


class StrategyTests(unittest.TestCase):
    def report(self, frame):
        return strategy_report(
            SimpleNamespace(laps=frame, results=pd.DataFrame(), data_source="fixture")
        )

    def test_missing_lap_breaks_span_and_unknown_stays_unknown(self):
        frame = laps().loc[lambda f: f.Driver.eq("AAA") & f.LapNumber.ne(4)].copy()
        frame.loc[frame.LapNumber.eq(8), "Compound"] = None
        result = self.report(frame)
        spans = result["drivers"][0]["spans"]
        self.assertEqual(
            [(s["startLap"], s["endLap"]) for s in spans],
            [(1, 3), (5, 7), (8, 8), (9, 10)],
        )
        self.assertEqual(spans[2]["compound"], "UNKNOWN")
        self.assertNotIn(8, [p["lap"] for p in result["drivers"][0]["points"]])
        json.dumps(result, allow_nan=False)

    def test_pit_lap_in_timeline_but_excluded_from_tyre_plot(self):
        frame = laps()
        frame["PitInTime"] = pd.Series(
            pd.NaT, index=frame.index, dtype="timedelta64[ns]"
        )
        frame.loc[frame.LapNumber.eq(5), "PitInTime"] = pd.Timedelta(seconds=1)
        report = self.report(frame)
        self.assertEqual(report["coverage"]["observed"], 20)
        self.assertEqual(report["coverage"]["tyrePoints"], 18)
        self.assertEqual(report["drivers"][0]["spans"][0]["endLap"], 10)

    def test_duplicate_lap_is_removed_without_imputing(self):
        frame = laps().iloc[:10]
        report = self.report(pd.concat([frame, frame.iloc[[3]]], ignore_index=True))
        self.assertEqual(report["coverage"]["observed"], 9)
        self.assertEqual(len(report["drivers"][0]["spans"]), 2)

    def test_missing_tyre_age_not_filled_and_results_order_preserved(self):
        frame = laps()
        frame["TyreLife"] = np.nan
        session = SimpleNamespace(
            laps=frame, results=pd.DataFrame([dict(Abbreviation="BBB", Position=1)])
        )
        report = strategy_report(session)
        self.assertEqual(report["drivers"][0]["driver"], "BBB")
        self.assertEqual(report["coverage"]["tyrePoints"], 0)


class TrackTests(unittest.TestCase):
    def test_same_elapsed_time_neutral_even_when_minimum_speeds_differ(self):
        a, b = telemetry(), telemetry()
        b["Speed"] -= 10
        result = compare_speed_zones(
            [(lap_record(), a), (lap_record(), b)], "AAA", "BBB", "fixture"
        )
        self.assertEqual(len(result["miniSectors"]), 25)
        self.assertTrue(all(s["winner"] is None for s in result["miniSectors"]))
        self.assertTrue(
            all(abs(s["deltaSeconds"]) < 1e-6 for s in result["miniSectors"])
        )

    def test_dominance_sums_to_observed_elapsed_delta(self):
        result = compare_speed_zones(
            [(lap_record(), telemetry(80)), (lap_record(2), telemetry(82))],
            "AAA",
            "BBB",
            "fixture",
        )
        self.assertTrue(all(s["winner"] == "AAA" for s in result["miniSectors"]))
        self.assertAlmostEqual(
            sum(s["deltaSeconds"] for s in result["miniSectors"]), -2, places=3
        )
        self.assertEqual(result["trace"][-1]["fraction"], 1)
        self.assertAlmostEqual(result["comparison"][-1]["deltaSeconds"], -2)
        json.dumps(result, allow_nan=False)

    def test_sparse_telemetry_not_coloured_as_evidence(self):
        frame = telemetry()
        frame = frame.drop(index=range(20, 80))
        with self.assertRaises(SessionDataError):
            compare_speed_zones(
                [(lap_record(), frame), (lap_record(), telemetry())],
                "AAA",
                "BBB",
                "fixture",
            )

    def fake_session(self):
        frame = laps()
        selected = []

        def get(lap, *, speed_only=False):
            selected.append((lap.Driver, int(lap.LapNumber), speed_only))
            return telemetry()

        return (
            SimpleNamespace(
                laps=SimpleNamespace(
                    pick_drivers=lambda d: frame.loc[frame.Driver.eq(d)]
                ),
                telemetry=get,
                data_provider="openf1",
            ),
            selected,
        )

    def test_requested_laps_used_instead_of_fastest(self):
        session, selected = self.fake_session()
        with patch(
            "backend.services.track_evidence.load_session", return_value=session
        ):
            result = speed_map(2026, 20, "R", "AAA", "BBB", 6, 9)
        self.assertEqual(selected, [("AAA", 6, True), ("BBB", 9, True)])
        self.assertEqual((result["lapA"], result["lapB"]), (6, 9))

    def test_invalid_requested_lap_does_not_fall_back(self):
        session, selected = self.fake_session()
        with patch(
            "backend.services.track_evidence.load_session", return_value=session
        ):
            with self.assertRaises(SessionDataError) as caught:
                speed_map(2026, 20, "R", "AAA", "BBB", 99)
        self.assertEqual(caught.exception.status_code, 422)
        self.assertEqual(selected, [])

    def test_lap_options_are_screened_and_no_telemetry_download(self):
        session, selected = self.fake_session()
        with patch(
            "backend.services.track_evidence.load_session", return_value=session
        ):
            options = lap_options(2026, 20, "R", "AAA")
        self.assertEqual(len(options["laps"]), 10)
        self.assertEqual(selected, [])

    def test_api_rejects_zero_lap_and_exposes_typed_delay(self):
        client = TestClient(app)
        response = client.get("/api/weekend/2026/20/track/R/AAA/BBB?lap_a=0")
        self.assertEqual(response.status_code, 422)
        with patch(
            "backend.routers.weekend.load_strategy",
            side_effect=SessionDataError("session_not_started", "Future race", 425, 60),
        ):
            response = client.get("/api/weekend/2026/20/strategy")
        self.assertEqual(response.status_code, 425)
        self.assertEqual(response.headers["Retry-After"], "60")


if __name__ == "__main__":
    unittest.main()
