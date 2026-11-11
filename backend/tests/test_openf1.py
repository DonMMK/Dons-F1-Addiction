"""Public provider, conservative quality, replay and transport regressions."""

import copy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import data, events, f1_access, openf1, prediction_store
from backend.services import weekend as analysis
from backend.services.loading_errors import SessionDataError
from backend.services.openf1_client import OpenF1Client
from backend.services.openf1_quality import screened_intervals

START = pd.Timestamp("2025-06-01T12:00:00Z")


def fixture(kind="R"):
    info = dict(
        session_key=100,
        session_name=openf1.SESSION_NAMES[kind],
        date_start=START.isoformat(),
        date_end=(START + pd.Timedelta(hours=1)).isoformat(),
    )
    drivers = [
        dict(driver_number=n, name_acronym=code, team_name="Team", full_name=code)
        for n, code in ((1, "AAA"), (2, "BBB"))
    ]
    laps, stints = [], []
    for n in (1, 2):
        for lap in range(1, 19):
            duration = 80 + (n - 1) * 0.2
            laps.append(
                dict(
                    driver_number=n,
                    lap_number=lap,
                    date_start=(
                        START + pd.Timedelta(seconds=(lap - 1) * 90)
                    ).isoformat(),
                    lap_duration=duration,
                    duration_sector_1=30,
                    duration_sector_2=30,
                    duration_sector_3=duration - 60,
                    is_pit_out_lap=lap == 1,
                )
            )
        stints.append(
            dict(
                driver_number=n,
                lap_start=1,
                lap_end=18,
                stint_number=1,
                compound="MEDIUM",
                tyre_age_at_start=3,
            )
        )
    controls = [
        dict(
            category="SessionStatus", message="SESSION STARTED", date=START.isoformat()
        ),
        dict(
            category="SessionStatus",
            message="SESSION FINISHED",
            date=(START + pd.Timedelta(hours=1)).isoformat(),
        ),
    ]
    return {
        "sessions": [info],
        "drivers": drivers,
        "laps": laps,
        "stints": stints,
        "pit": [],
        "intervals": [],
        "race_control": controls,
        "weather": [
            dict(
                air_temperature=25,
                track_temperature=35,
                humidity=50,
                wind_speed=2,
                rainfall=0,
            )
        ],
        "session_result": [
            dict(driver_number=1, position=1),
            dict(driver_number=2, position=2),
        ],
    }


def template(kind="R"):
    return SimpleNamespace(
        date=START.tz_localize(None),
        name=openf1.SESSION_NAMES[kind],
        event={"RoundNumber": 1, "EventName": "Test Grand Prix"},
    )


class HistoricalProvider(unittest.TestCase):
    def setUp(self):
        self.payload = fixture()
        self.api = Mock()
        self.api.get.side_effect = lambda endpoint, params, **kw: copy.deepcopy(
            self.payload[endpoint]
        )
        self.patches = [
            patch.object(openf1, "client", return_value=self.api),
            patch.object(
                openf1,
                "load_results_session",
                side_effect=SessionDataError("test", "Unavailable"),
            ),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def load(self, kind="R"):
        return openf1.load_session(2025, 1, kind, Path("unused"), template(kind))

    def test_real_laps_normalized_without_fabricated_fastf1_accuracy(self):
        session = self.load()
        self.assertTrue(data.finished(session))
        self.assertEqual(session.drivers, ["1", "2"])
        self.assertTrue(session.laps["IsAccurate"].isna().all())
        self.assertTrue(session.laps["TrackStatus"].eq("UNKNOWN").all())
        self.assertEqual(len(data.clean_laps(session.laps)), 34)
        row = session.laps.pick_drivers("AAA").iloc[1]
        self.assertEqual(row["TyreLife"], 5)  # 3 old + first completed + second
        self.assertEqual(session.get_driver("BBB")["DriverNumber"], "2")
        pairs = analysis.matched_laps(session.laps, "AAA", "BBB")
        self.assertEqual(len(pairs), 17)
        self.assertAlmostEqual(float(pairs["delta"].median()), -0.2)

    def test_legacy_lap_selectors_and_lazy_lap_telemetry_keep_session(self):
        session = self.load()
        selected = (
            session.laps.pick_track_status("1")
            .pick_accurate()
            .pick_wo_box()
            .pick_driver("1")
        )
        lap = selected.pick_fastest()
        self.assertIs(lap.session, session)
        self.assertEqual(lap["Driver"], "AAA")
        with patch.object(
            session, "telemetry", return_value=pd.DataFrame({"Speed": [1]})
        ) as tel:
            self.assertEqual(len(lap.get_telemetry()), 1)
        tel.assert_called_once()

    def test_deleted_message_uses_affected_lap_not_leaders_current_lap(self):
        self.payload["race_control"].append(
            dict(
                category="Other",
                lap_number=12,
                date=(START + pd.Timedelta(minutes=20)).isoformat(),
                message="CAR 1 (AAA) TIME 1:20.000 DELETED - TRACK LIMITS AT TURN 12 LAP 4 12:05:00",
            )
        )
        laps = data.clean_laps(self.load().laps)
        self.assertNotIn(4, laps.loc[laps["Driver"].eq("AAA"), "LapNumber"].tolist())
        self.assertIn(12, laps.loc[laps["Driver"].eq("AAA"), "LapNumber"].tolist())

    def test_unassignable_deletion_fails_closed(self):
        self.payload["race_control"].append(
            dict(
                category="Other",
                date=(START + pd.Timedelta(minutes=20)).isoformat(),
                message="LAP TIME DELETED",
            )
        )
        self.assertTrue(data.clean_laps(self.load().laps).empty)

    def test_missing_pit_or_control_coverage_does_not_make_clean_laps(self):
        original = self.api.get.side_effect
        for endpoint in ("pit", "race_control"):

            def fetch(name, params, **kw):
                if name == endpoint:
                    raise SessionDataError("missing", "Missing")
                return original(name, params, **kw)

            self.api.get.side_effect = fetch
            self.assertTrue(data.clean_laps(self.load().laps).empty)
        self.api.get.side_effect = original

    def test_missing_stints_omits_matches_and_no_synthetic_age(self):
        self.payload["stints"] = []
        session = self.load()
        self.assertTrue(session.laps["TyreLife"].isna().all())
        self.assertTrue(analysis.matched_laps(session.laps, "AAA", "BBB").empty)

    def test_in_and_out_laps_and_inconsistent_sectors_excluded(self):
        self.payload["pit"] = [dict(driver_number=1, lap_number=8)]
        self.payload["laps"][4]["duration_sector_3"] = 5
        laps = data.clean_laps(self.load().laps)
        sample = laps.loc[laps["Driver"].eq("AAA"), "LapNumber"].tolist()
        for invalid in (1, 5, 8, 9):
            self.assertNotIn(invalid, sample)

    def test_duplicate_laps_are_excluded_instead_of_selecting_faster_copy(self):
        self.payload["laps"].append(copy.deepcopy(self.payload["laps"][3]))
        laps = self.load().laps
        self.assertFalse(
            ((laps["DriverNumber"] == "1") & (laps["LapNumber"] == 4)).any()
        )

    def test_stale_previous_day_messages_are_not_in_this_session(self):
        self.payload["race_control"].append(
            dict(
                date=(START - pd.Timedelta(days=1)).isoformat(),
                category="Other",
                message="LAP TIME DELETED",
            )
        )
        self.assertEqual(len(data.clean_laps(self.load().laps)), 34)

    def test_unknown_qualifying_phase_is_not_guessed(self):
        self.payload["sessions"][0]["session_name"] = "Qualifying"
        report = analysis.qualifying_gap(self.load("Q"), "AAA", "BBB")
        self.assertIsNone(report["segment"])

    def test_live_cancelled_ambiguous_and_old_sessions_report_specific_errors(self):
        for mutate, code in [
            (
                lambda r: r.update(
                    date_end=(
                        pd.Timestamp.now(tz="UTC") - pd.Timedelta(minutes=10)
                    ).isoformat()
                ),
                "openf1_historical_pending",
            ),
            (lambda r: r.update(is_cancelled=True), "session_cancelled"),
        ]:
            previous = copy.deepcopy(self.payload)
            mutate(self.payload["sessions"][0])
            with self.assertRaises(SessionDataError) as caught:
                self.load()
            self.assertEqual(caught.exception.code, code)
            self.payload = previous
        self.payload["sessions"].append(copy.deepcopy(self.payload["sessions"][0]))
        with self.assertRaises(SessionDataError) as caught:
            self.load()
        self.assertEqual(caught.exception.code, "openf1_session_unavailable")
        with self.assertRaises(SessionDataError) as caught:
            openf1.resolve_session(self.api, 2020, template(), "R")
        self.assertEqual(caught.exception.code, "openf1_year_unsupported")

    def test_yellow_overlaps_excluded_and_sector_clear_cannot_end_safety_car(self):
        messages = [
            dict(
                category="SessionStatus",
                message="SESSION STARTED",
                date=START.isoformat(),
            ),
            dict(
                category="SafetyCar",
                message="SAFETY CAR DEPLOYED",
                date=(START + pd.Timedelta(seconds=100)).isoformat(),
            ),
            dict(
                flag="CLEAR",
                scope="Sector",
                sector=1,
                date=(START + pd.Timedelta(seconds=200)).isoformat(),
            ),
            dict(
                flag="CLEAR",
                scope="Track",
                date=(START + pd.Timedelta(seconds=250)).isoformat(),
            ),
            dict(
                flag="GREEN",
                scope="Track",
                date=(START + pd.Timedelta(seconds=300)).isoformat(),
            ),
        ]
        intervals = screened_intervals(messages, START + pd.Timedelta(hours=1))
        self.assertEqual(intervals[0], (START, START + pd.Timedelta(seconds=100)))
        self.assertEqual(intervals[1][0], START + pd.Timedelta(seconds=300))
        self.payload["race_control"] += [
            dict(
                flag="YELLOW",
                scope="Sector",
                sector=1,
                date=(START + pd.Timedelta(seconds=460)).isoformat(),
            ),
            dict(
                flag="CLEAR",
                scope="Sector",
                sector=1,
                date=(START + pd.Timedelta(seconds=470)).isoformat(),
            ),
        ]
        self.assertNotIn(6, data.clean_laps(self.load().laps)["LapNumber"].tolist())

    def test_default_provider_uses_openf1_without_archive_auth(self):
        data._public_session.cache_clear()
        data._FAILURES.clear()
        with patch.dict("os.environ", {"F1_TIMING_PROVIDER": "auto"}), patch.object(
            events, "get_session", return_value=template()
        ), patch.object(
            f1_access, "has_cached_timing", return_value=False
        ), patch.object(
            f1_access,
            "auth_status",
            return_value={"authenticated": False, "credentialsConfigured": False},
        ), patch.object(
            f1_access, "ensure_authenticated"
        ) as auth:
            session = data.load_session(2025, 1, "R")
        self.assertEqual(session.data_provider, "openf1")
        auth.assert_not_called()
        data._public_session.cache_clear()

    def test_weekend_and_practice_prediction_routes_accept_public_sessions(self):
        session = self.load()
        with patch.object(analysis, "load_session", return_value=session):
            response = TestClient(app).get("/api/weekend/2025/1")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["teams"][0]["matchedLaps"], 17)
        self.assertIn("OpenF1", response.json()["dataSources"]["R"])
        with tempfile.TemporaryDirectory() as temp, patch.object(
            prediction_store, "DATA_DIR", Path(temp)
        ), patch("backend.routers.prediction.load_session", return_value=session):
            response = TestClient(app).post(
                "/api/prediction/run",
                json={"year": 2025, "gp": "Test", "session": "FP2", "model": "v12"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any("OpenF1" in w for w in response.json()["warnings"]))


def telemetry_rows(duration=80):
    car, pos = [], []
    for i, elapsed in enumerate(np.arange(0, duration + 0.01, 0.25)):
        date = (START + pd.Timedelta(seconds=float(elapsed))).isoformat()
        car.append(
            dict(
                date=date,
                speed=180,
                throttle=70,
                brake=100 if i % 2 else 0,
                n_gear=5,
                drs=12,
            )
        )
        pos.append(
            dict(
                date=date,
                x=float(np.cos(elapsed / duration * 2 * np.pi) * 1000),
                y=float(np.sin(elapsed / duration * 2 * np.pi) * 1000),
            )
        )
    return car, pos


class Replay(unittest.TestCase):
    def test_speed_map_does_not_depend_on_unrelated_control_channel_validity(self):
        car, pos = telemetry_rows()
        for row in car:
            row["throttle"] = 104
        tel = openf1.merge_telemetry(car, pos, START, 80, speed_only=True)
        self.assertEqual(len(tel), 321)
        self.assertNotIn("Throttle", tel.columns)
        with self.assertRaises(SessionDataError):
            openf1.merge_telemetry(car, pos, START, 80)

    def test_binary_brake_and_speed_integrated_distance(self):
        car, pos = telemetry_rows()
        tel = openf1.merge_telemetry(car, pos, START, 80)
        self.assertEqual(set(tel["Brake"]), {0, 1})
        self.assertAlmostEqual(float(tel.iloc[-1]["Distance"]), 4000)
        self.assertTrue(np.isfinite(tel[["X", "Y", "Speed", "Distance"]]).all().all())

    def test_missing_gear_or_long_position_gap_is_reported(self):
        car, pos = telemetry_rows()
        for r in car:
            r.pop("n_gear")
        with self.assertRaises(SessionDataError):
            openf1.merge_telemetry(car, pos, START, 80)
        car, pos = telemetry_rows()
        with self.assertRaises(SessionDataError) as caught:
            openf1.merge_telemetry(car, pos[30:], START, 80)
        self.assertEqual(caught.exception.code, "openf1_telemetry_incomplete")

    def test_only_selected_driver_lap_window_is_downloaded(self):
        session = openf1.HistoricalSession(Mock(), template(), fixture()["sessions"][0])
        session.api.get.side_effect = telemetry_rows()
        lap = {
            "LapStartDate": START,
            "LapTime": pd.Timedelta(seconds=80),
            "DriverNumber": "1",
        }
        self.assertEqual(len(session.telemetry(lap)), 321)
        for call in session.api.get.call_args_list:
            self.assertEqual(call.args[1]["driver_number"], 1)
            self.assertIn("date>", call.args[1])
            self.assertIn("date<", call.args[1])
            self.assertNotIn("+00:00", call.args[1]["date>"])

    def test_missing_2026_drs_does_not_discard_real_car_or_position_samples(self):
        from backend.routers.ghost_car import _telemetry_to_dict

        car, pos = telemetry_rows()
        for row in car:
            row["drs"] = None
        tel = openf1.merge_telemetry(car, pos, START, 80)
        payload = _telemetry_to_dict(tel)
        self.assertEqual(len(payload["speed"]), 321)
        self.assertEqual(payload["drs"], [None] * 321)


class Transport(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.api = OpenF1Client(Path(self.temp.name))

    def response(self, status=200, body=None, headers=None):
        return SimpleNamespace(
            status_code=status, headers=headers or {}, json=lambda: body
        )

    def test_disk_cache_reused_by_new_client_without_network(self):
        with patch(
            "requests.get", return_value=self.response(body=[{"lap_number": 2}])
        ) as get:
            first = self.api.get("laps", {"session_key": 1})
            second = OpenF1Client(Path(self.temp.name)).get("laps", {"session_key": 1})
        self.assertEqual(first, second)
        get.assert_called_once()

    def test_rate_limit_backoff_shared_across_clients_and_cached_data_still_works(self):
        with patch(
            "requests.get",
            return_value=self.response(429, headers={"Retry-After": "60"}),
        ) as get:
            with self.assertRaises(SessionDataError) as caught:
                self.api.get("laps", {"session_key": 1})
            self.assertEqual(caught.exception.headers["Retry-After"], "60")
            with self.assertRaises(SessionDataError):
                OpenF1Client(Path(self.temp.name)).get("stints", {"session_key": 1})
        get.assert_called_once()

    def test_invalid_json_shape_not_cached_and_live_denial_not_disguised_as_404(self):
        with patch.object(self.api, "_reserve"), patch(
            "requests.get", return_value=self.response(body={"error": "bad"})
        ):
            with self.assertRaises(SessionDataError) as caught:
                self.api.get("laps", {})
            self.assertEqual(caught.exception.code, "openf1_invalid_response")
        with patch.object(self.api, "_reserve"), patch(
            "requests.get", return_value=self.response(401)
        ):
            with self.assertRaises(SessionDataError) as caught:
                self.api.get("laps", {})
            self.assertEqual(caught.exception.code, "openf1_access_unavailable")

    def test_public_metadata_never_tries_protected_f1timing_backend(self):
        with patch.object(
            events.fastf1, "get_session", side_effect=[ValueError(), template()]
        ) as get:
            events.get_session(2025, 1, "R")
        self.assertEqual(
            [c.kwargs["backend"] for c in get.call_args_list], ["fastf1", "ergast"]
        )


if __name__ == "__main__":
    unittest.main()
