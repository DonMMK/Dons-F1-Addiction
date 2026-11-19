"""Regression coverage for partial FastF1 loads and October 2026 archive auth."""

import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import fastf1
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import data, f1_access, results
from backend.services.loading_errors import SessionDataError
from backend.services import weekend as analysis
from backend.routers import prediction


def template():
    return SimpleNamespace(
        date=pd.Timestamp("2026-10-31"),
        name="Qualifying",
        api_path="/static/2026/test/qualifying/",
        event={"RoundNumber": 19, "EventName": "Mexico City Grand Prix"},
    )


def lap_session():
    return SimpleNamespace(
        laps=pd.DataFrame({"LapTime": pd.to_timedelta(["80s", "81s"])}),
        weather_data=pd.DataFrame(),
        race_control_messages=pd.DataFrame(),
    )


def public_response():
    frame = pd.DataFrame(
        [
            dict(
                number=1,
                driverCode="AAA",
                givenName="A",
                familyName="Driver",
                constructorName="Team",
                position=1,
                Q1=pd.Timedelta(seconds=80),
                Q2=pd.NaT,
                Q3=pd.NaT,
            ),
            dict(
                number=2,
                driverCode="BBB",
                givenName="B",
                familyName="Driver",
                constructorName="Team",
                position=2,
                Q1=pd.Timedelta(seconds=80.2),
                Q2=pd.NaT,
                Q3=pd.NaT,
            ),
        ]
    )
    return SimpleNamespace(content=[frame])


class Loader(unittest.TestCase):
    def setUp(self):
        provider = patch.dict("os.environ", {"F1_TIMING_PROVIDER": "fastf1"})
        provider.start()
        self.addCleanup(provider.stop)
        data._session.cache_clear()
        data._FAILURES.clear()
        cache_probe = patch.object(f1_access, "has_cached_timing", return_value=True)
        cache_probe.start()
        self.addCleanup(cache_probe.stop)

    def test_old_fastf1_version_gives_upgrade_action(self):
        with patch.object(fastf1, "__version__", "3.7.0"):
            with self.assertRaises(SessionDataError) as caught:
                f1_access.check_version()
        self.assertEqual(caught.exception.code, "fastf1_upgrade_required")

    def test_partial_driver_list_is_not_successful_timing(self):
        partial = SimpleNamespace(
            laps=pd.DataFrame({"LapTime": [pd.NaT]}),
            results=pd.DataFrame({"DriverNumber": range(22)}),
        )
        with patch.object(fastf1, "get_session", return_value=template()), patch.object(
            data, "_try_load"
        ), patch.object(
            f1_access,
            "ensure_authenticated",
            side_effect=SessionDataError("archive_auth_required", "Login required"),
        ):
            with self.assertRaises(SessionDataError) as caught:
                data._session(2026, 19, "Q", False, 1, None)
        self.assertEqual(caught.exception.code, "archive_auth_required")
        self.assertEqual(data._session.cache_info().currsize, 0)
        self.assertFalse(data._valid(partial))

    def test_good_cache_load_does_not_require_auth(self):
        session = lap_session()
        session.date = pd.Timestamp("2025-01-01")
        with patch.object(fastf1, "get_session", return_value=session), patch.object(
            data, "_try_load"
        ), patch.object(f1_access, "ensure_authenticated") as auth:
            loaded = data._session(2025, 1, "Q", False, 1, None)
        auth.assert_not_called()
        self.assertEqual(len(loaded.laps), 2)
        self.assertEqual(len(loaded.data_warnings), 2)

    def test_network_load_is_validated_and_cached_only_after_success(self):
        first = template()
        second = lap_session()
        second.date = pd.Timestamp("2025-01-01")
        with patch.object(
            fastf1, "get_session", side_effect=[first, second]
        ), patch.object(data, "_try_load"), patch.object(
            f1_access, "ensure_authenticated"
        ) as auth, patch.object(
            f1_access, "probe_archive"
        ) as probe:
            loaded = data._session(2026, 19, "Q", False, 1, None)
        self.assertIs(loaded, second)
        auth.assert_called_once()
        probe.assert_called_once_with(second)

    def test_cold_cache_does_not_run_every_parser_before_auth_error(self):
        with patch.object(
            f1_access, "has_cached_timing", return_value=False
        ), patch.object(fastf1, "get_session", return_value=template()), patch.object(
            data, "_try_load"
        ) as parsers, patch.object(
            f1_access,
            "ensure_authenticated",
            side_effect=SessionDataError("archive_auth_required", "Login"),
        ):
            with self.assertRaises(SessionDataError):
                data._session(2026, 19, "Q", False, 1, None)
        parsers.assert_not_called()

    def test_missing_optional_weather_property_is_safe(self):
        class Session:
            @property
            def weather_data(self):
                raise RuntimeError("DataNotLoaded")

        self.assertIsNone(data.optional_data(Session(), "weather_data"))

    def test_telemetry_requires_both_position_and_car_channels(self):
        session = lap_session()
        session.car_data = {"1": pd.DataFrame({"Speed": [100]})}
        self.assertFalse(data._valid(session, True))
        session.pos_data = {"1": pd.DataFrame({"X": [100]})}
        self.assertTrue(data._valid(session, True))

    def test_system_exit_from_fastf1_cannot_kill_api_worker(self):
        session = SimpleNamespace(load=Mock(side_effect=SystemExit()))
        with self.assertRaises(SessionDataError) as caught:
            data._try_load(session, False)
        self.assertEqual(caught.exception.code, "archive_cache_unusable")

    def test_upstream_error_is_not_converted_to_422(self):
        error = SessionDataError("archive_auth_required", "Run auth command")
        with patch.object(prediction, "load_session", side_effect=error):
            response = TestClient(app).post(
                "/api/prediction/run",
                json={
                    "year": 2026,
                    "gp": "Mexico City Grand Prix",
                    "session": "FP2",
                    "model": "v12",
                },
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["x-f1-data-error"], "archive_auth_required")
        self.assertEqual(response.json()["detail"], "Run auth command")

    def test_failure_memo_does_not_keep_partial_session(self):
        with patch.object(
            f1_access,
            "auth_status",
            return_value={"authenticated": False, "credentialsConfigured": False},
        ), patch.object(
            data,
            "_session",
            side_effect=SessionDataError("archive_auth_required", "Login"),
        ) as loader:
            for _ in range(2):
                with self.assertRaises(SessionDataError):
                    data.load_session(2026, 19, "Q")
        loader.assert_called_once()


class ArchiveAccess(unittest.TestCase):
    def test_probe_distinguishes_auth_missing_and_rate_limit(self):
        cases = {
            401: ("archive_auth_rejected", 503),
            403: ("archive_access_denied", 503),
            404: ("session_not_published", 425),
            429: ("archive_rate_limited", 503),
            500: ("archive_upstream_error", 502),
        }
        for status, (code, http_status) in cases.items():
            with patch.object(
                fastf1.Cache,
                "requests_get",
                return_value=SimpleNamespace(status_code=status),
            ):
                with self.assertRaises(SessionDataError) as caught:
                    f1_access.probe_archive(template())
            self.assertEqual(caught.exception.code, code)
            self.assertEqual(caught.exception.status_code, http_status)

    def test_no_browser_or_password_prompt_in_api_requests(self):
        from fastf1.internals import f1account
        from fastf1.exceptions import F1AuthError

        with patch.object(f1account.token_manager, "_default_auth_func"), patch.dict(
            "os.environ", {}, clear=True
        ):
            f1_access.install_server_policy()
            with self.assertRaises(F1AuthError):
                f1account.token_manager._default_auth_func()

    def test_cache_only_is_scoped_and_does_not_affect_other_threads(self):
        with patch.object(
            fastf1.Cache, "_request", return_value=SimpleNamespace(status_code=200)
        ) as request:
            with f1_access.cache_only():
                fastf1.Cache.requests_get("https://example.com")
                worker = threading.Thread(
                    target=lambda: fastf1.Cache.requests_get("https://example.com")
                )
                worker.start()
                worker.join()
            fastf1.Cache.requests_get("https://example.com")
        calls = request.call_args_list
        self.assertTrue(calls[0].kwargs["only_if_cached"])
        self.assertNotIn("only_if_cached", calls[1].kwargs)
        self.assertNotIn("only_if_cached", calls[2].kwargs)

    def test_existing_parsed_caches_are_merged_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(
            "os.environ", {}, clear=True
        ), patch.object(fastf1.Cache, "configure"):
            root = Path(temp)
            existing = root / "f1_cache" / "2026" / "event"
            existing.mkdir(parents=True)
            (existing / "timing.ff1pkl").write_bytes(b"good-cache")
            other = root / "formula1-ghost-car" / ".fastf1_cache" / "2026" / "event"
            other.mkdir(parents=True)
            (other / "timing.ff1pkl").write_bytes(b"do-not-overwrite")
            (other / "car.ff1pkl").write_bytes(b"car-cache")
            target = f1_access.configure_cache(root, root / "var")
            self.assertEqual(target, root / "f1_cache")
            self.assertEqual(
                (target / "2026/event/timing.ff1pkl").read_bytes(), b"good-cache"
            )
            self.assertEqual(
                (target / "2026/event/car.ff1pkl").read_bytes(), b"car-cache"
            )
            self.assertTrue((other / "car.ff1pkl").exists())

    def test_status_never_exposes_token_or_account(self):
        fake = SimpleNamespace(
            token_manager=SimpleNamespace(
                get_stored=lambda: SimpleNamespace(
                    value="SENSITIVE", is_valid=lambda: True
                )
            )
        )
        with patch.object(f1_access, "_auth_module", return_value=fake):
            state = f1_access.auth_status()
        self.assertTrue(state["authenticated"])
        self.assertNotIn("SENSITIVE", str(state))
        self.assertEqual(
            set(state), {"authenticated", "credentialsConfigured", "loginCommand"}
        )


class PublicResults(unittest.TestCase):
    def setUp(self):
        results._load.cache_clear()

    def load(self):
        stub = template()
        stub.load = Mock(side_effect=AssertionError("Raw API must not be used"))
        client = Mock()
        client.get_qualifying_results.return_value = public_response()
        with patch.object(fastf1, "get_session", return_value=stub), patch.object(
            results, "Ergast", return_value=client
        ):
            session = results.load_results_session(2026, 19, "Q")
        stub.load.assert_not_called()
        return session

    def test_published_results_need_no_raw_session_status_or_laps(self):
        session = self.load()
        self.assertTrue(data.finished(session))
        self.assertEqual(len(session.results), 2)
        self.assertFalse(hasattr(session, "laps"))
        gap = analysis.qualifying_gap(session, "AAA", "BBB")
        self.assertEqual(gap["segment"], "Q1")
        self.assertAlmostEqual(gap["deltaSeconds"], -0.2)

    def test_weekend_can_show_published_quali_while_race_timing_is_unavailable(self):
        session = self.load()
        error = SessionDataError("archive_auth_required", "Authenticate")
        with patch.object(
            analysis, "load_session", side_effect=[error, session, error]
        ):
            report = analysis.weekend(2026, 19)
        self.assertEqual(len(report["teams"]), 1)
        self.assertIsNone(report["teams"][0]["raceDeltaSeconds"])
        self.assertEqual(report["teams"][0]["matchedLaps"], 0)
        self.assertEqual(
            report["dataSources"]["Q"], "Jolpica-F1 published classification"
        )
        self.assertTrue(any("Authenticate" in w for w in report["warnings"]))

    def test_public_results_still_work_on_older_runtime(self):
        with patch.object(fastf1, "__version__", "3.7.0"):
            self.assertEqual(len(self.load().results), 2)

    def test_no_data_reports_not_published(self):
        client = Mock()
        client.get_qualifying_results.return_value = SimpleNamespace(content=[])
        with patch.object(fastf1, "get_session", return_value=template()), patch.object(
            results, "Ergast", return_value=client
        ):
            with self.assertRaises(SessionDataError) as caught:
                results.load_results_session(2026, 19, "Q")
        self.assertEqual(caught.exception.status_code, 425)

    def test_upstream_failures_do_not_become_weekend_404(self):
        with patch(
            "backend.routers.weekend.weekend",
            side_effect=SessionDataError(
                "archive_network_error", "Network unavailable", 502
            ),
        ):
            response = TestClient(app).get("/api/weekend/2026/19")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["detail"], "Network unavailable")


if __name__ == "__main__":
    unittest.main()
