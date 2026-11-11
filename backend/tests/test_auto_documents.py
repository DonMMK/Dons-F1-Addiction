"""Runtime discovery, durable retries and cache safety without upstream calls."""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests
from fastapi.testclient import TestClient

from backend.app import app
from backend.services import fia_documents as auto, weekend_sources as sources

URL = "https://www.fia.com/system/files/future-upgrades.pdf"
NAME = "Future Grand Prix"


def snapshot(status="indexed"):
    return {
        "year": 2027,
        "round": 1,
        "eventName": NAME,
        "checkedAt": "2027-03-09T00:00:00Z",
        "sourceUrl": URL,
        "documents": [{"title": "Car Presentation Submissions", "url": URL}],
        "documentHash": "known",
        "teams": [
            {
                "team": "Nebula Racing",
                "status": "declared_none",
                "components": [],
                "pages": [2],
            }
        ],
        "submissionStatus": status,
    }


class Discovery(unittest.TestCase):
    def catalogue(self, document=True):
        season = sources.INDEX + "/season/season-2027-9999"
        event = season + "/event/Future%20Grand%20Prix"
        pages = {
            sources.INDEX: f'<select><option value="{season}">SEASON 2027</option></select>'.encode(),
            season: b'<select><option value="/documents/event/Future%20Grand%20Prix">Future Grand Prix</option></select>',
            event: (
                '<li><div class="event-title">Future Grand Prix</div>'
                + (
                    '<div class="document-row"><a href="'
                    + URL
                    + '"><div class="title">Car Presentation Submissions</div><div class="published">Published today</div></a></div>'
                    if document
                    else ""
                )
                + "</li>"
            ).encode(),
        }
        return pages, event

    def test_future_season_and_event_ids_discovered_not_fixed(self):
        pages, event = self.catalogue()
        index, documents = sources.discover(2027, NAME, fetch=pages.__getitem__)
        self.assertEqual(index, event)
        self.assertEqual(documents[0]["url"], URL)
        self.assertEqual(documents[0]["published"], "Published today")

    def test_undiscovered_year_does_not_use_current_season(self):
        pages, _ = self.catalogue()
        with self.assertRaisesRegex(ValueError, "season 2028"):
            sources.discover(2028, NAME, fetch=pages.__getitem__)

    def test_wrong_event_page_rejected(self):
        pages, event = self.catalogue()
        pages[event] = pages[event].replace(
            b'class="event-title">Future Grand Prix',
            b'class="event-title">Other Grand Prix',
        )
        with self.assertRaisesRegex(ValueError, "uniquely match"):
            sources.discover(2027, NAME, fetch=pages.__getitem__)

    def test_absent_submission_is_pending_not_zero_upgrades(self):
        pages, _ = self.catalogue(document=False)
        value = sources.refresh(2027, 1, NAME, fetch=pages.__getitem__, save=False)
        self.assertEqual(value["submissionStatus"], "not_published")
        self.assertEqual(value["teams"], [])

    def test_new_constructor_name_from_roster_requires_no_alias_change(self):
        pages = [
            SimpleNamespace(extract_text=lambda **kw: "2027 Future Grand Prix"),
            SimpleNamespace(
                extract_text=lambda **kw: "Car Presentation\nNebula Racing\nUpdated component              Primary reason\nNo updates"
            ),
        ]
        with patch.object(
            sources, "PdfReader", return_value=SimpleNamespace(pages=pages)
        ):
            value = sources.parse_submission(b"pdf", 2027, NAME, URL, ["Nebula Racing"])
        self.assertEqual(value[0]["team"], "Nebula Racing")
        self.assertEqual(value[0]["status"], "declared_none")

    def test_same_hash_and_roster_reuses_validated_parse(self):
        import hashlib

        previous = {
            **snapshot(),
            "documentHash": hashlib.sha256(b"pdf").hexdigest(),
            "parserVersion": 2,
            "roster": ["Nebula Racing"],
        }
        with patch.object(
            sources, "discover", return_value=(sources.INDEX, previous["documents"])
        ), patch.object(sources, "parse_submission") as parse:
            result = sources.refresh(
                2027,
                1,
                NAME,
                roster=["Nebula Racing"],
                fetch=lambda _: b"pdf",
                previous=previous,
                save=False,
            )
        parse.assert_not_called()
        self.assertEqual(result["teams"], previous["teams"])

    def test_ambiguous_current_team_header_is_not_assigned_arbitrarily(self):
        pages = [
            SimpleNamespace(extract_text=lambda **kw: "2027 Future Grand Prix"),
            SimpleNamespace(
                extract_text=lambda **kw: "Car Presentation\nNebula Racing and Comet Racing\nNo updates"
            ),
        ]
        with patch.object(
            sources, "PdfReader", return_value=SimpleNamespace(pages=pages)
        ):
            result = sources.parse_submission(
                b"pdf", 2027, NAME, URL, ["Nebula Racing", "Comet Racing"]
            )
        self.assertEqual(result, [])


class Runtime(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2027, 3, 10, tzinfo=timezone.utc).timestamp()
        self.clock = lambda: self.now
        self.indexer = auto.FiaDocumentIndexer(
            self.root / "weekend_evidence", clock=self.clock
        )
        self.patch_dir = patch.object(sources, "DATA_DIR", self.root)
        self.patch_dir.start()

    def tearDown(self):
        self.indexer.stop()
        self.patch_dir.stop()
        self.temp.cleanup()

    def queue(self):
        self.indexer.request(2027, 1, NAME, ["Nebula Racing"])

    def use_result(self, result):
        def refresh(*args, **kwargs):
            kwargs["on_documents"](result["documents"])
            return result

        return patch.object(sources, "refresh", side_effect=refresh)

    def test_first_run_indexes_then_repeated_requests_do_not_reset_ttl(self):
        self.queue()
        with self.use_result(snapshot()) as refresh:
            self.indexer.run_once()
            self.assertTrue((self.root / "weekend_evidence/2027-1.json").exists())
            self.queue()
            with patch.object(self.indexer, "scan_season", return_value=1):
                self.indexer.run_once()  # queued season scan
            self.assertFalse(self.indexer.run_once())
            self.assertEqual(refresh.call_count, 1)
        state = self.indexer.status(2027, 1)
        self.assertEqual(state["state"], "indexed")
        self.assertEqual(state["documents"][0]["url"], URL)
        self.assertIsNotNone(state["lastSuccessAt"])

    def test_missing_documents_are_rechecked_and_survive_restart(self):
        self.queue()
        with self.use_result({**snapshot("not_published"), "teams": []}):
            self.indexer.run_once()
        restarted = auto.FiaDocumentIndexer(
            self.root / "weekend_evidence", clock=self.clock
        )
        self.assertEqual(restarted.status(2027, 1)["state"], "not_published")
        self.now += 3601
        with self.use_result(snapshot()):
            restarted.run_once()
        self.assertEqual(restarted.status(2027, 1)["state"], "indexed")

    def test_parser_or_network_failure_preserves_previous_snapshot(self):
        sources.save_snapshot(snapshot())
        path = self.root / "weekend_evidence/2027-1.json"
        previous = path.read_bytes()
        for result in (
            snapshot("needs_review"),
            {**snapshot("not_published"), "teams": []},
        ):
            self.queue()
            self.now += 4000
            with self.use_result(result):
                self.indexer.run_once()
            self.assertEqual(path.read_bytes(), previous)
        self.now += 4000
        with patch.object(sources, "refresh", side_effect=requests.ConnectionError()):
            self.indexer.run_once()
        self.assertEqual(path.read_bytes(), previous)
        self.assertEqual(self.indexer.status(2027, 1)["state"], "error")

    def test_cross_worker_lease_is_exclusive_and_recovers_after_crash(self):
        self.queue()
        other = auto.FiaDocumentIndexer(
            self.root / "weekend_evidence", clock=self.clock
        )
        first = self.indexer.claim()
        second = other.claim()
        self.assertEqual(first["kind"], "event")
        self.assertEqual(second["kind"], "season")
        self.assertIsNone(other.claim())
        self.now += 601
        recovered = other.claim()
        self.assertEqual(recovered["kind"], "event")
        self.assertNotEqual(recovered["token"], first["token"])

    def test_retry_after_blocks_all_fia_work_without_losing_cache(self):
        self.queue()
        response = requests.Response()
        response.status_code = 429
        response.headers["Retry-After"] = "7200"
        with patch.object(
            sources, "refresh", side_effect=requests.HTTPError(response=response)
        ):
            self.indexer.run_once()
        self.assertEqual(self.indexer.status(2027, 1)["state"], "error")
        self.assertIsNone(self.indexer.claim())
        self.assertEqual(
            pd.Timestamp(self.indexer.status(2027, 1)["nextCheckAt"]).timestamp(),
            self.now + 7200,
        )

    def test_fia_http_bytes_cached_without_repeated_downloads(self):
        with patch.object(sources, "download", return_value=b"pdf") as download:
            self.assertEqual(self.indexer.fetch(URL), b"pdf")
            self.assertEqual(self.indexer.fetch(URL), b"pdf")
            self.assertEqual(download.call_count, 1)
            self.now += 3601
            self.indexer.fetch(URL)
            self.assertEqual(download.call_count, 2)

    def test_schedule_scan_uses_year_and_date_not_fixed_round_list(self):
        schedule = pd.DataFrame(
            [
                dict(RoundNumber=1, EventName=NAME, EventDate="2027-03-07"),
                dict(
                    RoundNumber=2, EventName="Next Grand Prix", EventDate="2027-03-14"
                ),
                dict(
                    RoundNumber=3, EventName="Later Grand Prix", EventDate="2027-04-30"
                ),
                dict(RoundNumber=4, EventName="Wrong year", EventDate="2026-03-01"),
            ]
        )
        constructors = pd.DataFrame({"constructorName": ["Nebula Racing"]})
        with patch.object(
            auto.events, "get_schedule", return_value=schedule
        ), patch.object(
            auto,
            "Ergast",
            return_value=SimpleNamespace(
                get_constructor_info=lambda **kw: constructors
            ),
        ):
            self.assertEqual(self.indexer.scan_season(2027), 2)
        self.assertEqual(
            self.indexer.event_payload(2027, 2)["roster"], ["Nebula Racing"]
        )
        self.assertEqual(self.indexer.event_payload(2027, 3), {})

    def test_api_is_cached_and_nonblocking_during_discovery(self):
        with patch.object(auto, "get_indexer", return_value=self.indexer), patch(
            "backend.routers.documents.get_indexer", return_value=self.indexer
        ), patch.object(
            sources, "download", side_effect=AssertionError("No HTTP on API requests")
        ):
            response = TestClient(app).get("/api/documents/2027/1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["refresh"]["state"], "queued")
        self.assertEqual(response.json()["teams"], [])
        json.dumps(response.json(), allow_nan=False)

    def test_disabled_indexer_does_not_queue_network_work(self):
        disabled = auto.FiaDocumentIndexer(self.root / "disabled", enabled=False)
        disabled.request(2027, 1, NAME)
        self.assertIsNone(disabled.claim())
        self.assertEqual(disabled.status(2027, 1)["state"], "disabled")

    def test_year_rollover_and_january_catchup_need_no_source_change(self):
        self.now = datetime(2028, 1, 2, tzinfo=timezone.utc).timestamp()

        def tick():
            self.indexer.stop_event.set()
            return False

        with patch.object(
            self.indexer, "request", wraps=self.indexer.request
        ) as requested, patch.object(self.indexer, "run_once", side_effect=tick):
            self.indexer._loop()
        self.assertEqual([c.args for c in requested.call_args_list], [(2028,), (2027,)])

    def test_background_scan_keeps_the_actual_weekend_roster(self):
        self.queue()
        self.indexer.enqueue(
            "event",
            2027,
            1,
            {"eventName": NAME, "roster": ["Sponsor Nebula Racing"]},
            priority=1,
        )
        self.assertEqual(
            self.indexer.event_payload(2027, 1)["roster"], ["Nebula Racing"]
        )

    def test_application_lifespan_starts_and_stops_the_worker(self):
        indexer = SimpleNamespace(start=Mock(), stop=Mock())
        pace = SimpleNamespace(start=Mock(), stop=Mock())
        with patch.object(auto, "get_indexer", return_value=indexer), patch(
            "backend.services.performance.get_performance", return_value=pace
        ):
            with TestClient(app) as client:
                self.assertEqual(client.get("/api/health").status_code, 200)
                indexer.start.assert_called_once()
                pace.start.assert_called_once()
            indexer.stop.assert_called_once()
            pace.stop.assert_called_once()


if __name__ == "__main__":
    unittest.main()
