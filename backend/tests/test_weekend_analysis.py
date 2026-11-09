"""Evidence controls: source coverage, identity invariance and uncertainty."""

import copy
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import pace_evidence as pace
from backend.services import weekend_sources as sources
from backend.services.race_context import execution_report
from backend.services.track_evidence import compare_speed_zones

START = pd.Timestamp("2026-01-01T12:00:00Z")


def race_fixture():
    laps, results, intervals = [], [], []
    for number, (driver, team, offset) in enumerate(
        [
            ("AAA", "A", -1.1),
            ("AAB", "A", -0.9),
            ("BBA", "B", -0.1),
            ("BBB", "B", 0.1),
            ("CCA", "C", 0.9),
            ("CCB", "C", 1.1),
        ],
        1,
    ):
        results.append(
            dict(
                DriverNumber=str(number),
                Abbreviation=driver,
                TeamName=team,
                Position=number,
                GridPosition=7 - number,
                Status="Finished",
            )
        )
        for lap in range(1, 19):
            date = START + pd.Timedelta(seconds=lap * 100)
            duration = 70 + offset + np.sin(lap) * 0.03
            laps.append(
                dict(
                    DriverNumber=str(number),
                    Driver=driver,
                    Team=team,
                    LapNumber=lap,
                    Stint=1,
                    Compound="MEDIUM",
                    TyreLife=lap,
                    LapStartDate=date,
                    LapTime=pd.Timedelta(seconds=duration),
                    Sector1Time=pd.Timedelta(seconds=duration / 3),
                    Sector2Time=pd.Timedelta(seconds=duration / 3),
                    Sector3Time=pd.Timedelta(seconds=duration / 3),
                    IsAccurate=True,
                    TrackStatus="1",
                    PitInTime=pd.NaT,
                    PitOutTime=pd.NaT,
                )
            )
            for seconds in range(0, 76, 4):
                intervals.append(
                    dict(
                        driver_number=number,
                        date=(date + pd.Timedelta(seconds=seconds)).isoformat(),
                        interval=3,
                        gap_to_leader=5,
                    )
                )
    weather = pd.DataFrame(
        [
            dict(
                Date=START + pd.Timedelta(seconds=i),
                TrackTemp=25 if i < 1000 else 45,
                AirTemp=20,
                Rainfall=0,
                WindSpeed=2,
                Humidity=50,
            )
            for i in range(0, 2000, 20)
        ]
    )
    frame = pd.DataFrame(laps)
    for c in ("PitInTime", "PitOutTime"):
        frame[c] = pd.Series(pd.NaT, index=frame.index, dtype="timedelta64[ns]")
    return SimpleNamespace(
        name="Race",
        date=START,
        results=pd.DataFrame(results),
        laps=frame,
        intervals=pd.DataFrame(intervals),
        weather_data=weather,
        pit_data=pd.DataFrame(),
        race_control_messages=pd.DataFrame(),
    )


class PackagePace(unittest.TestCase):
    def test_matched_numeric_evidence_ranks_both_car_average(self):
        result = pace.analyse(race_fixture())
        rows = result["teamPace"]["rows"]
        self.assertEqual([r["name"] for r in rows], ["A", "B", "C"])
        self.assertAlmostEqual(rows[0]["scoreSeconds"], -1, places=3)
        self.assertEqual(len(rows[0]["drivers"]), 2)
        self.assertIsNotNone(rows[0]["interval95"])
        self.assertTrue(all(r["rankRange95"] is not None for r in rows))
        json.dumps(result, allow_nan=False)

    def test_identity_permutation_does_not_change_numeric_advantages(self):
        race = race_fixture()
        original = pace.analyse(race)["teamPace"]["rows"]
        names = {
            "AAA": "VER",
            "AAB": "HAM",
            "BBA": "NOR",
            "BBB": "PIA",
            "CCA": "RUS",
            "CCB": "ANT",
        }
        race.laps["Driver"] = race.laps["Driver"].map(names)
        race.results["Abbreviation"] = race.results["Abbreviation"].map(names)
        renamed = pace.analyse(race)["teamPace"]["rows"]
        for a, b in zip(original, renamed):
            self.assertEqual(a["name"], b["name"])
            self.assertAlmostEqual(a["scoreSeconds"], b["scoreSeconds"], places=6)

    def test_missing_second_car_prevents_team_rank(self):
        race = race_fixture()
        race.laps = race.laps.loc[race.laps["Driver"].ne("AAB")]
        result = pace.analyse(race)
        self.assertIn("A", result["unrankedTeams"])
        self.assertNotIn("A", [r["name"] for r in result["teamPace"]["rows"]])

    def test_missing_weather_or_traffic_never_becomes_clear_air(self):
        for missing in ("weather_data", "intervals"):
            race = race_fixture()
            setattr(race, missing, pd.DataFrame())
            result = pace.analyse(race)
            self.assertEqual(result["status"], "insufficient_data")
            self.assertEqual(result["teamPace"]["rows"], [])

    def test_close_following_or_lapped_unknown_gap_excluded(self):
        race = race_fixture()
        race.intervals.loc[race.intervals["driver_number"].eq(1), "interval"] = 1
        race.intervals["interval"] = race.intervals["interval"].astype(object)
        race.intervals.loc[race.intervals["driver_number"].eq(2), "interval"] = "+1 LAP"
        laps, _ = pace.eligible_laps(race)
        self.assertFalse(laps["Driver"].isin(["AAA", "AAB"]).any())

    def test_temperature_filters_and_unknown_weather_excluded(self):
        race = race_fixture()
        cool, _ = pace.eligible_laps(race, "cool")
        warm, _ = pace.eligible_laps(race, "warm")
        self.assertTrue(cool["TrackTemp"].lt(30).all())
        self.assertTrue(warm["TrackTemp"].ge(40).all())
        self.assertFalse(set(cool["LapNumber"]) & set(warm["LapNumber"]))

    def test_pairing_respects_clock_tyre_age_and_temperature(self):
        laps, _ = pace.eligible_laps(race_fixture())
        subset = laps.loc[laps["Driver"].isin(["AAA", "BBA"])].copy()
        subset.loc[subset["Driver"].eq("BBA"), "TyreLife"] += 3
        self.assertEqual(pace.comparisons(subset), [])
        subset["TyreLife"] = 1
        subset.loc[subset["Driver"].eq("BBA"), "Date"] += pd.Timedelta(minutes=5)
        self.assertEqual(pace.comparisons(subset), [])

    def test_ties_and_disconnected_groups_do_not_create_unique_winner(self):
        pairs = [
            dict(
                a=a,
                b=b,
                teamA=a,
                teamB=b,
                window=i,
                compound="MEDIUM",
                delta=0,
                s1=0,
                s2=0,
                s3=0,
            )
            for a, b in [("AAA", "BBB"), ("CCC", "DDD")]
            for i in range(1, 19)
        ]
        drivers, teams = pace.ranking(pairs, {})
        self.assertEqual(drivers["components"], 2)
        self.assertEqual({r["rank"] for r in drivers["rows"]}, {1})
        self.assertTrue(all(r["rankRange95"] == [1, 2] for r in drivers["rows"]))
        self.assertEqual(teams["rows"], [])

    def test_practice_is_separate_and_explicit_about_unobserved_fuel(self):
        race = race_fixture()
        race.name = "Practice 2"
        race.intervals = pd.DataFrame()
        result = pace.analyse(race)
        self.assertGreater(result["coverage"]["used"], 0)
        self.assertTrue(
            any("unknown fuel and traffic" in l for l in result["limitations"])
        )

    def test_condition_parameter_is_validated(self):
        response = TestClient(app).get("/api/weekend/2026/20?condition=favorite-team")
        self.assertEqual(response.status_code, 422)


class Sources(unittest.TestCase):
    def test_brazil_snapshot_matches_verified_fia_components_and_none(self):
        result = sources.report(
            2026, 20, "São Paulo Grand Prix", ["McLaren", "Mercedes", "Red Bull Racing"]
        )
        mclaren = next(r for r in result["teams"] if r["team"] == "McLaren")
        self.assertEqual(
            {c["component"] for c in mclaren["components"]},
            {"Front Wing", "Rear Wing", "Beam Wing", "Floor Furniture"},
        )
        self.assertEqual(
            next(r for r in result["teams"] if r["team"] == "Mercedes")["status"],
            "declared_none",
        )
        self.assertTrue(all(c["effectSeconds"] is None for c in mclaren["components"]))

    def test_missing_round_is_unknown_and_track_context_is_year_scoped(self):
        result = sources.report(2026, 1, "Australian Grand Prix", ["McLaren"])
        self.assertEqual(result["teams"][0]["status"], "not_indexed")
        self.assertEqual(result["timeline"], [])
        self.assertEqual(
            sources.track_context("Brazilian Grand Prix", 2025)["status"],
            "telemetry_only",
        )

    def test_fia_source_validation_rejects_external_or_internal_urls(self):
        for url in [
            "http://www.fia.com/test",
            "https://127.0.0.1/documents",
            "https://example.com/documents",
            "https://www.fia.com/account",
        ]:
            with self.assertRaises(ValueError):
                sources.fia_url(url)

    def test_changed_pdf_layout_is_unknown_not_zero_upgrades(self):
        pages = [
            SimpleNamespace(extract_text=lambda **kw: "2026 São Paulo Grand Prix"),
            SimpleNamespace(
                extract_text=lambda **kw: "Car Presentation\nMcLaren\nUnexpected layout\nNew front wing"
            ),
        ]
        with patch.object(
            sources, "PdfReader", return_value=SimpleNamespace(pages=pages)
        ):
            result = sources.parse_submission(
                b"fixture",
                2026,
                "São Paulo Grand Prix",
                "https://www.fia.com/system/files/test.pdf",
            )
        self.assertEqual(result[0]["status"], "unparsed")

    def test_wrong_event_pdf_rejected(self):
        with patch.object(
            sources,
            "PdfReader",
            return_value=SimpleNamespace(
                pages=[
                    SimpleNamespace(extract_text=lambda **kw: "2025 Belgian Grand Prix")
                ]
            ),
        ):
            with self.assertRaises(ValueError):
                sources.parse_submission(
                    b"fixture",
                    2026,
                    "São Paulo Grand Prix",
                    "https://www.fia.com/system/files/test.pdf",
                )


class ExecutionAndTrack(unittest.TestCase):
    def test_pit_benchmark_is_not_reported_as_luck_or_race_time_lost(self):
        race = race_fixture()
        race.pit_data = pd.DataFrame(
            [
                dict(driver_number=1, lap_number=10, stop_duration=4, lane_duration=24),
                dict(driver_number=2, lap_number=11, stop_duration=2, lane_duration=22),
            ]
        )
        result = execution_report(race)
        self.assertEqual(result["drivers"][0]["stops"][0]["deltaToSessionMedian"], 1)
        self.assertIn("not counterfactual", result["note"])

    def test_speed_zones_are_detected_features_not_official_turns(self):
        times = np.arange(0, 70, 0.25)
        a = pd.DataFrame(
            dict(
                Time=pd.to_timedelta(times, unit="s"),
                Distance=times * 60,
                Speed=200 + 90 * np.cos(times / 4),
                X=1000 * np.cos(times / 11),
                Y=1000 * np.sin(times / 11),
            )
        )
        b = a.copy()
        b["Speed"] -= 5
        lap = pd.Series(
            dict(
                LapTime=pd.Timedelta(seconds=70),
                Sector1Time=pd.Timedelta(seconds=23),
                Sector2Time=pd.Timedelta(seconds=23),
            )
        )
        result = compare_speed_zones([(lap, a), (lap, b)], "AAA", "BBB", "fixture")
        self.assertGreater(len(result["zones"]), 0)
        self.assertIn("not FIA turn", result["method"])
        self.assertTrue(all(abs(z["deltaKmH"] - 5) < 5 for z in result["zones"]))
        json.dumps(result, allow_nan=False)


if __name__ == "__main__":
    unittest.main()
