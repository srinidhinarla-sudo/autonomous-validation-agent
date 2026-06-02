"""SQLite-backed transition logger."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB = Path(__file__).parent.parent / "transitions.db"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(_DB))
    c.row_factory = sqlite3.Row
    return c


def init_db() -> None:
    with _conn() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS transitions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ts           TEXT    NOT NULL,
                from_state   TEXT    NOT NULL,
                event        TEXT    NOT NULL,
                to_state     TEXT    NOT NULL,
                success      INTEGER NOT NULL,
                context_json TEXT
            )
        """)
        c.commit()


def log(from_state: str, event: str, to_state: str,
        success: bool, context: dict | None = None) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO transitions "
            "(ts, from_state, event, to_state, success, context_json) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                from_state, event, to_state,
                int(success),
                json.dumps(context or {}),
            ),
        )
        c.commit()


def recent(limit: int = 50) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM transitions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def stats() -> dict:
    with _conn() as c:
        total   = c.execute("SELECT COUNT(*) FROM transitions").fetchone()[0]
        success = c.execute(
            "SELECT COUNT(*) FROM transitions WHERE success=1"
        ).fetchone()[0]
        unique  = c.execute(
            "SELECT COUNT(DISTINCT to_state) FROM transitions WHERE success=1"
        ).fetchone()[0]
    return {
        "total":                total,
        "success":              success,
        "failed":               total - success,
        "unique_states_reached": unique,
    }
