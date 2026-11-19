"""Immutable prediction snapshots, persisted across backend restarts."""

import json
import sqlite3
import uuid
from .data import DATA_DIR


def connect():
    db = sqlite3.connect(DATA_DIR / "predictions.sqlite3", timeout=30)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute(
        "CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, created TEXT NOT NULL, payload TEXT NOT NULL)"
    )
    return db


def save(payload):
    payload = {**payload, "runId": str(uuid.uuid4())}
    with connect() as db:
        db.execute(
            "INSERT INTO runs VALUES (?, ?, ?)",
            (
                payload["runId"],
                payload["createdAt"],
                json.dumps(payload, allow_nan=False),
            ),
        )
    return payload


def get(run_id):
    with connect() as db:
        row = db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def recent():
    with connect() as db:
        return [
            json.loads(r[0])
            for r in db.execute(
                "SELECT payload FROM runs ORDER BY created DESC LIMIT 100"
            )
        ]
