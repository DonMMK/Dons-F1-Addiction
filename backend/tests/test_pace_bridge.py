"""Coverage without prior rankings: confounding, masking and held-out checks."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

from backend.services import pace_bridge as bridge
from backend.services import performance
from backend.tests.test_performance_grid import snapshot
from backend.tests.test_weekend_analysis import race_fixture


def controlled_laps():
    rng = np.random.default_rng(331)
    rows = []
    for i in range(8):
        driver = f"D{i}"
        offset = [-1.0, -0.5, 0.25, 1.25][i // 2] + (0.12 if i % 2 else -0.12)
        for lap in range(1, 55):
            age = (lap + i * 4) % (15 + i) + 1
            compound = ("MEDIUM", "HARD", "SOFT")[(lap // (15 + i) + i) % 3]
            close = float(rng.random() < (0.8 if i == 0 else 0.25))
            unknown = float(not close and rng.random() < 0.1)
            seconds = (
                90
                + offset
                - 0.035 * lap
                + 0.03 * age
                + 0.0005 * age**2
                + {"MEDIUM": 0.3, "HARD": 0.65, "SOFT": 0}[compound]
                + 0.7 * close
                + 0.2 * unknown
                + rng.normal(0, 0.025)
            )
            rows.append(
                dict(
                    Driver=driver,
                    Team=f"T{i//2}",
                    Window=lap,
                    LapNumber=lap,
                    Block=lap // 3,
                    Compound=compound,
                    TyreLife=age,
                    seconds=seconds,
                    TrackTemp=30 + 0.01 * lap,
                    Rainfall=0,
                    CloseTraffic=close,
                    UnknownTraffic=unknown,
                )
            )
    return pd.DataFrame(rows)


class Bridge(unittest.TestCase):
    def setUp(self):
        self.limits = threadpool_limits(limits=1)
        self.addCleanup(self.limits.restore_original_limits)

    def test_recovers_controlled_offsets_despite_different_traffic_exposure(self):
        frame = controlled_laps()
        original = frame.seconds.copy()
        model = bridge.fit(frame, draws=200)
        effects = dict(zip(model["drivers"], model["effects"]))
        self.assertAlmostEqual(effects["D0"] - effects["D4"], -1.25, delta=0.035)
        self.assertAlmostEqual(effects["D0"] - effects["D1"], -0.24, delta=0.035)
        pd.testing.assert_series_equal(frame.seconds, original)
        check = bridge.validation(frame)
        self.assertGreater(check["heldOutWindows"], 30)
        self.assertLess(check["pairDifferenceMaeSeconds"], 0.06)
        self.assertLess(
            check["pairDifferenceMaeSeconds"], check["zeroDifferenceMaeSeconds"]
        )

    def test_fully_confounded_driver_and_compound_does_not_create_rank(self):
        frame = controlled_laps()
        frame["Compound"] = frame.Driver
        self.assertIsNone(bridge.fit(frame))

    def test_disconnected_timing_does_not_create_global_rank(self):
        frame = controlled_laps()
        disconnected = frame.Driver.isin(["D0", "D1", "D2", "D3"])
        frame.loc[disconnected, "Window"] += 100
        self.assertIsNone(bridge.fit(frame))

    def report(self, frame, extra_missing=False):
        roster = (
            controlled_laps()[["Driver", "Team"]]
            .drop_duplicates()
            .rename(columns={"Driver": "Abbreviation", "Team": "TeamName"})
        )
        if extra_missing:
            roster = pd.concat(
                [
                    roster,
                    pd.DataFrame(
                        [
                            {"TeamName": "No observations", "Abbreviation": "X0"},
                            {"TeamName": "No observations", "Abbreviation": "X1"},
                        ]
                    ),
                ]
            )
        session = SimpleNamespace(name="Race", results=roster)
        coverage = dict(
            recorded=432,
            qualityScreened=len(frame),
            weatherMatched=len(frame),
            trafficScreened=0,
            used=0,
        )
        strict = {"teamPace": {"rows": []}, "driverPace": {"rows": []}}
        with patch.object(
            bridge, "observations", return_value=(frame, coverage)
        ), patch.object(
            bridge, "eligible_laps", return_value=(pd.DataFrame(), coverage)
        ):
            return bridge.analyse(session, "slick", strict)

    def test_masked_car_gets_proxy_and_no_observation_team_stays_visible(self):
        frame = controlled_laps().loc[lambda f: f.Driver.ne("D7")]
        result = self.report(frame, extra_missing=True)
        rows = {r["name"]: r for r in result["teamPace"]["rows"]}
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows["T3"]["evidenceTier"], "single_car")
        self.assertEqual(rows["T3"]["drivers"], ["D6"])
        self.assertEqual(rows["T3"]["expectedDrivers"], ["D6", "D7"])
        self.assertEqual(result["unrankedTeams"], ["No observations"])
        self.assertEqual(len(result["diagnostics"]), 5)
        self.assertGreater(
            rows["T3"]["gapInterval95"][1] - rows["T3"]["gapInterval95"][0], 0.15
        )

    def test_sparse_driver_not_silently_used_as_equal_second_car(self):
        frame = controlled_laps().loc[lambda f: f.Driver.ne("D7") | f.Window.le(4)]
        rows = {r["name"]: r for r in self.report(frame)["teamPace"]["rows"]}
        self.assertEqual(rows["T3"]["drivers"], ["D6"])
        self.assertEqual(rows["T3"]["evidenceTier"], "single_car")

    def test_names_results_and_roster_order_do_not_supply_pace_prior(self):
        frame = controlled_laps()
        original = self.report(frame)["teamPace"]["rows"]
        mapping = {f"D{i}": f"Z{7-i}" for i in range(8)}
        a = bridge.fit(frame)
        renamed = frame.assign(Driver=frame.Driver.map(mapping), Team="Arbitrary")
        b = bridge.fit(renamed.sample(frac=1, random_state=4))
        av, bv = dict(zip(a["drivers"], a["effects"])), dict(
            zip(b["drivers"], b["effects"])
        )
        for name in av:
            self.assertAlmostEqual(av[name], bv[mapping[name]], places=7)
        self.assertEqual([r["name"] for r in original], ["T0", "T1", "T2", "T3"])

    def test_unknown_traffic_is_a_control_not_clear_air(self):
        session = race_fixture()
        session.intervals = pd.DataFrame()
        frame, _ = bridge.observations(session, "slick")
        self.assertTrue(frame.UnknownTraffic.eq(1).all())
        self.assertTrue(frame.CloseTraffic.eq(0).all())
        frame, _ = bridge.eligible_laps(session, "slick")
        self.assertTrue(frame.empty)

    def test_weather_condition_does_not_borrow_other_condition_laps(self):
        frame, _ = bridge.observations(race_fixture(), "wet")
        self.assertTrue(frame.empty)

    def test_optional_model_failure_retains_strict_weekend_evidence(self):
        from backend.services import pace_evidence

        with patch.object(
            bridge, "analyse", side_effect=ValueError("fit failure")
        ), patch(
            "backend.services.openf1.add_public_race_observations"
        ), self.assertLogs(
            "backend.services.pace_evidence", level="ERROR"
        ):
            report = pace_evidence.analyse(race_fixture())
        self.assertTrue(report["teamPace"]["rows"])
        self.assertNotIn("coverageEstimate", report)
        self.assertIn("strict evidence is retained", report["warnings"][-1])

    def test_selected_board_keeps_strict_estimates_separate(self):
        value = snapshot()
        adjusted = self.report(controlled_laps())
        value["pace"]["coverageEstimate"] = adjusted
        value["colours"] = {}
        board = performance.build_board(value)
        self.assertEqual(board["view"], "adjusted")
        self.assertEqual(len(board["groups"][0]["rows"]), 4)
        self.assertEqual(board["strictBoard"]["view"], "strict")
        self.assertEqual(board["strictBoard"]["groups"][0]["rows"][0]["team"], "A")

    def test_tier_change_suppresses_apparent_progress(self):
        previous, current = snapshot(1), snapshot(2)
        estimate = self.report(controlled_laps())
        import copy

        previous["pace"]["coverageEstimate"] = copy.deepcopy(estimate)
        current["pace"]["coverageEstimate"] = estimate
        old = previous["pace"]["coverageEstimate"]["teamPace"]["rows"][1]
        old["drivers"] = old["drivers"][:1]
        old["evidenceTier"] = "single_car"
        board = performance.build_board(current, previous)
        row = next(r for r in board["groups"][0]["rows"] if r["team"] == old["name"])
        self.assertIsNone(row["deltaGapPercentagePoints"])
        self.assertTrue(
            all(r["rankChange"] is None for r in board["groups"][0]["rows"])
        )


if __name__ == "__main__":
    unittest.main()
