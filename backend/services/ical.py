"""CLI import of a downloaded publisher calendar. No arbitrary server URL fetches."""

import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from icalendar import Calendar


def parse_ics(text, series, source_url, verified_at):
    if urlparse(source_url).scheme != "https":
        raise ValueError("Use an HTTPS publisher URL for provenance")
    calendar = Calendar.from_ical(text)
    result = []
    for item in calendar.walk("VEVENT"):
        if item.get("RRULE") or item.get("RECURRENCE-ID"):
            raise ValueError(
                "Recurring calendars must be expanded to individual events before import"
            )
        if str(item.get("STATUS", "")).upper() == "CANCELLED":
            continue
        start = item.decoded("DTSTART")
        end = item.decoded("DTEND", None)
        all_day = isinstance(start, date) and not isinstance(start, datetime)
        if not all_day and (start.tzinfo is None or start.utcoffset() is None):
            raise ValueError(
                "A floating session time has no timezone; add TZID or UTC before importing"
            )
        if all_day:
            end = end or start + timedelta(days=1)
            if isinstance(end, datetime) or end <= start:
                raise ValueError("Invalid all-day end date")
        else:
            if end is not None and (
                not isinstance(end, datetime) or end.tzinfo is None or end <= start
            ):
                raise ValueError("Invalid timed event end")
            start = start.astimezone(timezone.utc)
            end = end.astimezone(timezone.utc) if end else None
        result.append(
            {
                "id": f'{series}:{item.get("UID", start.isoformat())}',
                "series": series,
                "title": str(item.get("SUMMARY", "Session")),
                "event": str(item.get("SUMMARY", "Session")),
                "start": start.isoformat(),
                "end": end.isoformat() if end else None,
                "dateOnly": all_day,
                "location": str(item.get("LOCATION", "")),
                "source": "Imported publisher calendar",
                "sourceUrl": source_url,
                "verifiedAt": verified_at,
                "status": "imported schedule",
            }
        )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Merge a downloaded .ics into a motorsport year snapshot"
    )
    parser.add_argument("file", type=Path)
    parser.add_argument(
        "--series",
        required=True,
        choices=["wec", "imsa", "nls", "gt-europe", "supercars", "n24"],
    )
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--year", required=True, type=int)
    args = parser.parse_args()
    if args.file.stat().st_size > 2_000_000:
        parser.error("Calendar exceeds 2 MB")
    now = datetime.now(timezone.utc).isoformat()
    events = parse_ics(args.file.read_bytes(), args.series, args.source_url, now)
    path = Path(__file__).resolve().parents[2] / "data" / f"motorsport-{args.year}.json"
    content = (
        json.loads(path.read_text()) if path.exists() else {"events": [], "sources": []}
    )
    # Replace this series/year atomically, including removals in the new publisher feed.
    content["events"] = [e for e in content["events"] if e["series"] != args.series] + [
        e for e in events if int(e["start"][:4]) == args.year
    ]
    content["sources"] = [
        s for s in content["sources"] if s["series"] != args.series
    ] + [{"series": args.series, "url": args.source_url, "verifiedAt": now}]
    path.parent.mkdir(exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(content, indent=2))
    temp.replace(path)
    print(
        f"Updated {path} with {len(events)} parsed entries; inspect the diff before committing"
    )


if __name__ == "__main__":
    main()
