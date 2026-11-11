"""Versioned FIA declarations and attributed track context, never pace bonuses.

FIA catalogues are discovered at runtime. Slow downloads and PDF parsing run
in a background worker; requests can keep serving validated local snapshots.
"""

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import os
import tempfile
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

from .data import ROOT, DATA_DIR

FIA = "https://www.fia.com"
INDEX = FIA + "/documents/championships/fia-formula-one-world-championship-14"
TEAM_ALIASES = {
    "McLaren": ["mclaren"],
    "Mercedes": ["mercedes"],
    "Red Bull Racing": ["oracle red bull", "red bull racing"],
    "Racing Bulls": ["racing bulls", "alphatauri", "rb f1 team"],
    "Ferrari": ["ferrari"],
    "Williams": ["williams"],
    "Aston Martin": ["aston martin"],
    "Haas F1 Team": ["haas"],
    "Audi": ["audi", "sauber"],
    "Alpine": ["alpine", "renault"],
    "Cadillac": ["cadillac"],
}


def normal(value):
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode()
        .lower(),
    ).strip()


def official_event(event_name):
    return {
        "Brazilian Grand Prix": "São Paulo Grand Prix",
        "Barcelona Grand Prix": "Barcelona-Catalunya Grand Prix",
    }.get(event_name, event_name)


def fia_url(value):
    value = urljoin(FIA, value)
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in ("www.fia.com", "fia.com")
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
    ):
        raise ValueError("Only public FIA HTTPS sources are supported")
    if not parsed.path.startswith(
        ("/documents", "/system/files/", "/sites/default/files/")
    ):
        raise ValueError("Unsupported FIA source path")
    return value


def download(url, maximum=8 * 1024 * 1024, before_request=None):
    url = fia_url(url)
    # Check each redirect before following it; source discovery is not a generic proxy.
    for _ in range(4):
        if before_request:
            before_request()
        with requests.get(
            url,
            timeout=(10, 30),
            stream=True,
            allow_redirects=False,
            headers={"User-Agent": "F1EvidenceDashboard/1 (public document indexing)"},
        ) as response:
            if response.is_redirect:
                url = fia_url(urljoin(url, response.headers["Location"]))
                continue
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > maximum:
                    raise ValueError("FIA document exceeds the supported size")
            return bytes(body)
    raise ValueError("Too many source redirects")


def discover(year, event_name, fetch=None):
    fetch = fetch or download
    soup = BeautifulSoup(fetch(INDEX), "html.parser")
    seasons = {
        fia_url(o["value"])
        for o in soup.select("option[value]")
        if re.search(rf"/season/season-{year}-\d+$", o["value"])
    }
    if len(seasons) != 1:
        raise ValueError(
            f"FIA season {year} was not discoverable; no current-season substitution was made"
        )
    season_url = seasons.pop()
    season = BeautifulSoup(fetch(season_url), "html.parser")
    name = official_event(event_name)
    candidates = {
        o.get_text(" ", strip=True)
        for o in season.select("option[value]")
        if "/event/" in o["value"]
        and normal(o.get_text(" ", strip=True)) == normal(name)
    }
    if len(candidates) != 1:
        raise ValueError(
            f"FIA event {name} is not discoverable in the requested season; no other event was substituted"
        )
    # Use the event spelling discovered in the FIA catalogue, never a numeric event ID.
    url = season_url + "/event/" + quote(candidates.pop(), safe="")
    soup = BeautifulSoup(fetch(url), "html.parser")
    documents = []
    sections = [
        h.parent
        for h in soup.select(".event-title")
        if normal(h.get_text(" ", strip=True)) == normal(name)
    ]
    active = [
        section for section in sections if section.select(".document-row a[href]")
    ]
    if len(active) > 1 or (not active and soup.select(".document-row a[href]")):
        raise ValueError(
            "FIA event catalogue does not uniquely match the requested event"
        )
    scope = active[0] if active else soup
    for link in scope.select(".document-row a[href]"):
        heading = link.select_one(".title")
        title = (
            heading.get_text(" ", strip=True)
            if heading
            else link.get_text(" ", strip=True)
        )
        target = fia_url(link["href"])
        if urlparse(target).path.lower().endswith(".pdf"):
            published = link.select_one(".published")
            documents.append(
                {
                    "title": title,
                    "url": target,
                    "published": (
                        published.get_text(" ", strip=True) if published else None
                    ),
                }
            )
    if not documents and soup.select("a[href*='.pdf']"):
        raise ValueError("FIA document layout changed; previous evidence was preserved")
    return url, documents


def parse_submission(content, year, event_name, source_url, roster=None):
    reader = PdfReader(BytesIO(content))
    if len(reader.pages) > 80:
        raise ValueError("Unexpected submission length")
    title = normal(reader.pages[0].extract_text())
    event_tokens = (
        normal(official_event(event_name))
        .replace("sao paulo", "brazil")
        .replace("brazilian", "brazil")
        .split()
    )
    title = title.replace("sao paulo", "brazil").replace("brazilian", "brazil")
    if str(year) not in title or not all(t in title.split() for t in event_tokens):
        raise ValueError(
            "Submission header does not match the requested event and year"
        )
    declarations = {}
    for page_number, page in enumerate(reader.pages, 1):
        text = page.extract_text(extraction_mode="layout") or ""
        header = normal(" ".join(text.splitlines()[:5]))
        teams = [
            team
            for team, aliases in TEAM_ALIASES.items()
            if any(normal(a) in header for a in aliases)
        ]
        matches = [
            team
            for team in roster or []
            if re.search(rf"\b{re.escape(normal(team))}\b", header)
        ]
        if matches:
            # Ambiguous current roster names stay unknown instead of picking one.
            teams = matches
        if len(teams) != 1:
            continue
        team = teams[0]
        entry = declarations.setdefault(
            team, {"team": team, "status": "unparsed", "components": [], "pages": []}
        )
        entry["pages"].append(page_number)
        if re.search(r"\bno\s+(?:updates?|changes?)\b", normal(text)):
            entry["status"] = "declared_none"
            continue
        lines = text.splitlines()
        heading = next(
            (line for line in lines if "Updated" in line and "Primary reason" in line),
            None,
        )
        if heading is None:
            continue
        reason_start = heading.index("Primary reason")
        rows = []
        for line in lines:
            cell = line[:reason_start].strip()
            match = re.match(r"^(\d{1,2})\s+([A-Za-z][A-Za-z /()\-]+)$", cell)
            if match:
                rows.append((int(match[1]), match[2].strip()))
        # Deliberately reject partial/changed layouts instead of guessing a count.
        if rows and [n for n, _ in rows] == list(range(1, len(rows) + 1)):
            entry["status"] = "declared_updates"
            for _, component in rows:
                entry["components"].append(
                    {
                        "component": component,
                        "page": page_number,
                        "sourceUrl": source_url,
                        "effectSeconds": None,
                        "fitment": "Not verified by this declaration",
                    }
                )
    return list(declarations.values())


def save_snapshot(result):
    directory = DATA_DIR / "weekend_evidence"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result['year']}-{result['round']}.json"
    fd, temp = tempfile.mkstemp(prefix=path.stem + "-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(result, stream, indent=2, allow_nan=False)
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def refresh(
    year,
    round_number,
    event_name,
    *,
    roster=None,
    fetch=None,
    save=True,
    previous=None,
    on_documents=None,
):
    fetch = fetch or download
    index, documents = discover(year, event_name, fetch=fetch)
    if on_documents:
        on_documents(documents)
    result = {
        "year": year,
        "round": round_number,
        "eventName": event_name,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "indexUrl": index,
        "documents": documents,
        "teams": [],
        "submissionStatus": "not_published",
    }
    submission = next(
        (d for d in documents if "car presentation" in d["title"].lower()), None
    )
    if not submission:
        return result
    content = fetch(submission["url"])
    digest = hashlib.sha256(content).hexdigest()
    same = (
        previous
        and previous.get("documentHash") == digest
        and previous.get("parserVersion") == 2
        and previous.get("roster", []) == sorted(roster or [])
    )
    teams = (
        previous["teams"]
        if same
        else parse_submission(content, year, event_name, submission["url"], roster)
    )
    status = (
        "indexed"
        if any(t["status"] in ("declared_none", "declared_updates") for t in teams)
        else "needs_review"
    )
    result.update(
        sourceUrl=submission["url"],
        documentHash=digest,
        teams=teams,
        submissionStatus=status,
        parserVersion=2,
        roster=sorted(roster or []),
    )
    if save and status == "indexed":
        save_snapshot(result)
    return result


def snapshots(year):
    records = {}
    for directory in (
        ROOT / "data" / "weekend_evidence",
        DATA_DIR / "weekend_evidence",
    ):
        for path in sorted(directory.glob(f"{year}-*.json")):
            try:
                value = json.loads(path.read_text())
                if value["year"] == year and 1 <= int(value["round"]) <= 100:
                    fia_url(value["sourceUrl"])
                    records[int(value["round"])] = value
            except (ValueError, KeyError, TypeError, OSError):
                continue
    return records


def report(year, round_number, event_name, roster, *, schedule_refresh=True):
    from .fia_documents import get_indexer

    indexer = get_indexer()
    if schedule_refresh:
        indexer.request(year, round_number, event_name, list(roster))
    freshness = indexer.status(year, round_number)
    history = snapshots(year)
    current = history.get(round_number)
    if current and normal(official_event(current["eventName"])) != normal(
        official_event(event_name)
    ):
        current = None
    canonical = {normal(name): name for name in roster}

    def team_name(name):
        if normal(name) in canonical:
            return canonical[normal(name)]
        aliases = [normal(a) for a in TEAM_ALIASES.get(name, [])] + [normal(name)]
        candidates = [
            v for k, v in canonical.items() if any(a in k or k == a for a in aliases)
        ]
        return candidates[0] if len(candidates) == 1 else name

    teams = []
    for team in roster:
        declarations = (
            []
            if not current
            else [r for r in current["teams"] if team_name(r["team"]) == team]
        )
        row = (
            declarations[0]
            if len(declarations) == 1
            else {"status": "not_indexed", "components": [], "pages": []}
        )
        teams.append({**row, "team": team})
    timeline = [
        {
            "round": rd,
            "eventName": value["eventName"],
            "checkedAt": value["checkedAt"],
            "sourceUrl": value["sourceUrl"],
            "teams": [{**r, "team": team_name(r["team"])} for r in value["teams"]],
        }
        for rd, value in sorted(history.items())
        if rd <= round_number
    ]
    return {
        "status": "indexed" if current else "not_indexed",
        "checkedAt": current.get("checkedAt") if current else None,
        "sourceUrl": current.get("sourceUrl") if current else INDEX,
        "documents": freshness.get("documents")
        or (current.get("documents", []) if current else []),
        "refresh": {**freshness, "cached": current is not None},
        "teams": teams,
        "timeline": timeline,
        "note": "FIA submissions record declared component changes, not measured gains or proof of race fitment. Declared none means no updates submitted in this document; not indexed means unknown. Upgrade count is never used as a pace bonus or a causal explanation.",
    }


def track_context(event_name, year, round_number=None):
    profiles = json.loads((ROOT / "data" / "track_context.json").read_text())
    key = normal(official_event(event_name))
    profile = next(
        (
            r
            for r in profiles
            if year in r["validYears"] and key in [normal(a) for a in r["events"]]
        ),
        None,
    )
    result = (
        dict(profile)
        if profile
        else {
            "name": event_name,
            "status": "telemetry_only",
            "demands": [],
            "sources": [],
            "note": "No reviewed track-demand profile is indexed. Use the measured sector comparison and optional recorded corner-speed map; no team advantage is assigned from the circuit name.",
        }
    )
    if round_number is not None:
        from .fia_documents import get_indexer

        docs = get_indexer().status(year, round_number).get("documents", [])
        result["sources"] = list(result["sources"]) + [
            {"label": d["title"], "url": d["url"]}
            for d in docs
            if any(k in d["title"].lower() for k in ("pirelli", "circuit map"))
        ]
    return result
