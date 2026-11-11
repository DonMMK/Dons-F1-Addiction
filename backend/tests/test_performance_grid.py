"""No made-up ranks, cross-group gaps or raw-second cross-circuit improvements."""

import copy
from datetime import datetime, timezone
import json
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import performance as grid, pace_evidence as pace
from backend.tests.test_weekend_analysis import race_fixture


def snapshot(rd=2, baseline=100, offsets=None, components=None):
    offsets = offsets or {"A": -0.4, "B": 0.2, "C": 0.6}
    components = components or {n: 1 for n in offsets}
    rows = []
    for name, score in offsets.items():
        members = [n for n in offsets if components[n] == components[name]]
        rank = 1 + sum(offsets[n] < score for n in members)
        rows.append(
            dict(
                name=name,
                scoreSeconds=score,
                component=components[name],
                rank=rank,
                rankRange95=[rank, rank],
                windows=18,
                rivals=len(members) - 1,
                drivers=[name + "1", name + "2"],
            )
        )
    return {
        "year": 2026,
        "round": rd,
        "condition": "slick",
        "version": grid.VERSION,
        "eventName": f"Event {rd}",
        "source": "Recorded fixture",
        "checkedAt": "2026-03-10T00:00:00Z",
        "colours": {},
        "pace": {
            "normalisationLapSeconds": baseline,
            "condition": "slick",
            "teamPace": {"rows": rows},
            "unrankedTeams": ["Unknown"],
            "coverage": {
                "recorded": 100,
                "qualityScreened": 80,
                "weatherMatched": 70,
                "trafficScreened": 60,
                "used": 60,
            },
            "warnings": [],
            "method": "Matched observations",
            "limitations": ["Car and driver are not separated"],
        },
    }


class Comparisons(unittest.TestCase):
    def test_gaps_use_group_differences_not_arbitrary_zero_mean_offset(self):
        value = snapshot()
        a = grid.build_board(value)
        for row in value["pace"]["teamPace"]["rows"]:
            row["scoreSeconds"] += 500
        b = grid.build_board(value)
        self.assertEqual(
            [r["gapSeconds"] for r in a["groups"][0]["rows"]],
            [r["gapSeconds"] for r in b["groups"][0]["rows"]],
        )
        self.assertEqual(a["groups"][0]["rows"][1]["gapSeconds"], 0.6)

    def test_change_normalises_lap_length_and_keeps_the_same_reference(self):
        previous = snapshot(1, 80, {"A": 0.2, "B": -0.2, "C": 0})
        value = grid.build_board(snapshot(), previous)
        row = next(r for r in value["groups"][0]["rows"] if r["team"] == "B")
        self.assertEqual(value["groups"][0]["referenceTeam"], "A")
        self.assertAlmostEqual(row["previousGapPercentToReference"], -0.5)
        self.assertAlmostEqual(row["previousEquivalentGapSeconds"], -0.5)
        self.assertAlmostEqual(row["deltaGapPercentagePoints"], 1.1)
        self.assertEqual(row["rankChange"], -1)

    def test_disconnected_groups_get_separate_zero_references(self):
        value = grid.build_board(
            snapshot(
                offsets={"A": -100, "B": -99, "C": 100, "D": 102},
                components={"A": 1, "B": 1, "C": 2, "D": 2},
            )
        )
        self.assertEqual(
            [[r["gapSeconds"] for r in g["rows"]] for g in value["groups"]],
            [[0, 1], [0, 2]],
        )

    def test_rank_movement_withheld_when_membership_changes(self):
        previous = snapshot(1, 100, {"A": 0, "B": 1, "D": 2})
        rows = grid.build_board(snapshot(), previous)["groups"][0]["rows"]
        self.assertTrue(all(r["rankChange"] is None for r in rows))
        self.assertIsNotNone(rows[0]["previousRank"])
        self.assertIsNone(
            next(r for r in rows if r["team"] == "C")["deltaGapPercentagePoints"]
        )

    def test_unknown_previous_link_does_not_become_zero_change(self):
        previous = snapshot(1, 100, components={"A": 1, "B": 2, "C": 2})
        row = grid.build_board(snapshot(), previous)["groups"][0]["rows"][1]
        self.assertIsNone(row["deltaGapPercentagePoints"])
        self.assertIsNone(row["previousEquivalentGapSeconds"])

    def test_missing_baseline_keeps_seconds_but_withholds_percent(self):
        value = grid.build_board(snapshot(baseline=None), snapshot(1))
        row = value["groups"][0]["rows"][1]
        self.assertEqual(row["gapSeconds"], 0.6)
        self.assertIsNone(row["gapPercent"])
        self.assertIsNone(row["deltaGapPercentagePoints"])

    def test_different_condition_year_version_or_future_not_compared(self):
        for change in (
            {"condition": "wet"},
            {"year": 2025},
            {"version": "old"},
            {"round": 3},
        ):
            old = {**snapshot(1), **change}
            self.assertIsNone(grid.build_board(snapshot(), old)["previousRound"])

    def test_unranked_team_never_gets_a_plotted_zero(self):
        value = grid.build_board(snapshot())
        self.assertEqual(value["unrankedTeams"], ["Unknown"])
        self.assertNotIn(
            "Unknown", [r["team"] for g in value["groups"] for r in g["rows"]]
        )
        json.dumps(value, allow_nan=False)

    def test_rounded_tie_keeps_the_estimator_reference_for_paired_intervals(self):
        value = snapshot(offsets={"A": 0, "B": 0, "C": 1})
        for row in value["pace"]["teamPace"]["rows"]:
            row.update(
                referenceTeam="B",
                gapInterval95=[0, 0] if row["name"] == "B" else [-0.1, 0.1],
            )
        board = grid.build_board(value)
        self.assertEqual(board["groups"][0]["referenceTeam"], "B")
        self.assertIsNotNone(board["groups"][0]["rows"][0]["gapInterval95"])

    def test_gap_intervals_preserve_paired_bootstrap_covariance(self):
        roster = {"A": ["AAA", "AAB"], "B": ["BBA", "BBB"], "C": ["CCA", "CCB"]}
        pairs = [
            dict(
                a="AAA",
                b=b,
                teamA="A",
                teamB=t,
                window=i,
                compound="MEDIUM",
                delta=0,
                s1=None,
                s2=None,
                s3=None,
            )
            for t, ds in roster.items()
            for b in ds
            if b != "AAA"
            for i in range(18)
        ]
        draw = [0]

        def fit(nodes, edges, draws=None, sector="delta"):
            if sector != "delta":
                return None
            drift = 0 if draws is None else ((draw[0] % 11) - 5) * 0.02
            draw[0] += 1
            return np.array(
                [
                    -2 + drift,
                    -2 + drift,
                    -1 + drift,
                    -1 + drift,
                    3 - 2 * drift,
                    3 - 2 * drift,
                ]
            )

        with patch.object(pace, "_fit", side_effect=fit):
            _, teams = pace.ranking(pairs, roster)
        row = next(r for r in teams["rows"] if r["name"] == "B")
        self.assertEqual(row["gapInterval95"], [1, 1])
        self.assertGreater(row["interval95"][1] - row["interval95"][0], 0.1)

    def test_existing_estimator_supplies_baseline_and_reference_intervals(self):
        session = race_fixture()
        with patch("backend.services.openf1.add_public_race_observations"):
            value = pace.analyse(session)
        self.assertGreater(value["normalisationLapSeconds"], 0)
        self.assertTrue(value["teamPace"]["rows"])
        self.assertTrue(
            all(r["gapInterval95"] is not None for r in value["teamPace"]["rows"])
        )


class Cache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.now = datetime(2026, 3, 11, tzinfo=timezone.utc).timestamp()
        self.service = grid.PerformanceService(self.temp.name, clock=lambda: self.now)

    def tearDown(self):
        self.service.stop()
        self.temp.cleanup()

    def plan(self, rounds=(1, 2), through=None):
        key = self.service.request(2026, "slick", through)
        with self.service.db() as db:
            db.execute(
                "UPDATE jobs SET state='ready',due=?,result=? WHERE key=?",
                (
                    self.now + 600,
                    json.dumps(
                        [{"round": r, "eventName": f"Event {r}"} for r in rounds]
                    ),
                    key,
                ),
            )
        return key

    def test_cache_survives_restart_and_separates_conditions(self):
        self.service.record(snapshot())
        restarted = grid.PerformanceService(self.temp.name, clock=lambda: self.now)
        self.assertIn(2, restarted.snapshots(2026, "slick"))
        self.assertEqual(restarted.snapshots(2026, "wet"), {})

    def test_latest_publication_pending_labels_older_board(self):
        self.plan()
        self.service.record(snapshot(1))
        value = self.service.response(2026)
        self.assertEqual((value["requestedRound"], value["displayedRound"]), (2, 1))
        self.assertTrue(value["update"]["showingEarlierRound"])

    def test_explicit_round_does_not_substitute_an_older_race(self):
        self.plan(through=2)
        self.service.record(snapshot(1))
        value = self.service.response(2026, rd=2)
        self.assertIsNone(value["board"])

    def test_previous_comparison_does_not_skip_an_unindexed_gp(self):
        self.plan((1, 2, 3))
        self.service.record(snapshot(1))
        self.service.record(snapshot(3))
        value = self.service.response(2026)
        self.assertEqual(value["board"]["round"], 3)
        self.assertIsNone(value["board"]["previousRound"])

    def test_request_ttl_not_reset_by_visitors(self):
        key = self.plan()
        for _ in range(5):
            self.service.response(2026)
        self.assertEqual(self.service.job(key)["due"], self.now + 600)

    def test_scan_is_bounded_and_future_race_is_not_queued(self):
        frame = pd.DataFrame(
            [
                dict(
                    RoundNumber=i,
                    EventName=f"Event {i}",
                    EventDate=f"2026-01-{i:02}",
                    Session5="Race",
                    Session5DateUtc=f"2026-01-{i:02}T12:00:00Z",
                )
                for i in range(1, 9)
            ]
            + [
                dict(
                    RoundNumber=9,
                    EventName="Future",
                    EventDate="2026-12-01",
                    Session5="Race",
                    Session5DateUtc="2026-12-01T12:00:00Z",
                )
            ]
        )
        with patch.object(grid.events, "get_schedule", return_value=frame):
            recent = self.service.scan(2026, "slick", None)
        self.assertEqual([r["round"] for r in recent], list(range(3, 9)))
        self.assertIsNone(self.service.job(f"{grid.VERSION}:race:2026:9:slick"))

    def test_not_finished_not_captured_and_failed_refresh_preserves_snapshot(self):
        session = SimpleNamespace(name="Race", data_provider="openf1", completed=False)
        with self.assertRaises(ValueError):
            self.service.capture(2026, 2, session, snapshot()["pace"])
        self.service.record(snapshot())
        key = f"{grid.VERSION}:race:2026:2:slick"
        self.service.enqueue(
            key, {"kind": "race", "year": 2026, "round": 2, "condition": "slick"}, 2
        )
        with patch.object(
            grid,
            "load_session",
            side_effect=HTTPException(
                425, "Awaiting publication", headers={"Retry-After": "900"}
            ),
        ):
            self.service.run_once()
        self.assertEqual(self.service.job(key)["state"], "pending")
        self.assertEqual(self.service.job(key)["due"], self.now + 900)
        self.assertIn(2, self.service.snapshots(2026, "slick"))

    def test_year_end_publication_delay_does_not_change_the_race_season(self):
        self.now = datetime(2027, 1, 1, 12, tzinfo=timezone.utc).timestamp()
        frame = pd.DataFrame(
            [
                dict(
                    RoundNumber=1,
                    EventName="Year end",
                    EventDate="2026-12-31",
                    Session5="Race",
                    Session5DateUtc="2026-12-31T23:00:00Z",
                )
            ]
        )
        with patch.object(grid.events, "get_schedule", return_value=frame):
            result = self.service.scan(2026, "slick", None)
        self.assertEqual(result[0]["eventName"], "Year end")

    def test_obsolete_lease_cannot_replace_current_evidence(self):
        self.service.enqueue("test", {"kind": "race"}, 1)
        with self.service.db() as db:
            db.execute("UPDATE jobs SET token='new',lease=?", (self.now + 900,))
        self.assertFalse(self.service.record(snapshot(), guard=("test", "old")))
        self.assertEqual(self.service.snapshots(2026, "slick"), {})

    def test_endpoint_only_queues_and_reads_local_cache(self):
        with patch(
            "backend.routers.performance.get_performance", return_value=self.service
        ), patch.object(
            grid,
            "load_session",
            side_effect=AssertionError("No timing download on API thread"),
        ):
            response = TestClient(app).get("/api/performance/2026?condition=slick")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["board"])
        self.assertEqual(response.json()["update"]["state"], "queued")

    def test_condition_and_round_validation(self):
        client = TestClient(app)
        self.assertEqual(
            client.get("/api/performance/2026?condition=favorite-team").status_code, 422
        )
        self.assertEqual(client.get("/api/performance/2026?round=0").status_code, 422)


if __name__ == "__main__":
    unittest.main()
