"""Local SQLite storage. Every counted event is written immediately, so nothing is lost on crash."""

import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at REAL NOT NULL,
    ended_at REAL
);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    score REAL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


class Storage:
    def __init__(self, path: Path):
        self._lock = threading.Lock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.executescript(SCHEMA)
        with self._lock:
            # Sessions left open by a crash or power cut get closed at their last event.
            self._db.execute(
                "UPDATE sessions SET ended_at = COALESCE("
                "(SELECT MAX(ts) FROM events e WHERE e.session_id = sessions.id), started_at) "
                "WHERE ended_at IS NULL"
            )
            self._db.commit()

    def start_session(self, ts: float) -> int:
        with self._lock:
            cur = self._db.execute("INSERT INTO sessions (started_at) VALUES (?)", (ts,))
            self._db.commit()
            return int(cur.lastrowid)

    def end_session(self, session_id: int, ts: float) -> None:
        with self._lock:
            self._db.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (ts, session_id))
            self._db.commit()

    def add_event(self, session_id: int, ts: float, kind: str, score: float) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events (session_id, ts, kind, score) VALUES (?, ?, ?, ?)",
                (session_id, ts, kind, score),
            )
            self._db.commit()

    def totals(self) -> dict:
        with self._lock:
            rows = self._db.execute("SELECT kind, COUNT(*) FROM events GROUP BY kind").fetchall()
        return {kind: count for kind, count in rows}

    def counts_since(self, ts: float) -> dict:
        with self._lock:
            rows = self._db.execute(
                "SELECT kind, COUNT(*) FROM events WHERE ts >= ? GROUP BY kind", (ts,)
            ).fetchall()
        return {kind: count for kind, count in rows}

    def active_seconds(self, now: float) -> float:
        with self._lock:
            row = self._db.execute(
                "SELECT COALESCE(SUM(COALESCE(ended_at, ?) - started_at), 0) FROM sessions",
                (now,),
            ).fetchone()
        return float(row[0] or 0.0)

    def sessions(self, now: float, limit: int = 100) -> list:
        with self._lock:
            rows = self._db.execute(
                """
                SELECT s.id, s.started_at, s.ended_at,
                       (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id AND e.kind = 'chest_open'),
                       (SELECT COUNT(*) FROM events e WHERE e.session_id = s.id AND e.kind = 'chest_break')
                FROM sessions s ORDER BY s.started_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        result = []
        for sid, started, ended, opens, breaks in rows:
            end = ended if ended is not None else now
            result.append(
                {"id": sid, "started_at": started, "duration": max(0.0, end - started),
                 "open": opens, "break": breaks, "open_now": ended is None}
            )
        return result

    def daily(self, days: int = 14) -> list:
        """(YYYY-MM-DD, opens, breaks) for the last `days` local days, oldest first."""
        with self._lock:
            rows = self._db.execute(
                """
                SELECT date(ts, 'unixepoch', 'localtime') AS day, kind, COUNT(*)
                FROM events
                WHERE ts >= strftime('%s', 'now', ?)
                GROUP BY day, kind
                """,
                (f"-{days} days",),
            ).fetchall()
        table = {}
        for day, kind, count in rows:
            entry = table.setdefault(day, {"chest_open": 0, "chest_break": 0})
            entry[kind] = count
        ordered = sorted(table.items())
        return [(day, v["chest_open"], v["chest_break"]) for day, v in ordered]

    def close(self) -> None:
        with self._lock:
            self._db.close()


def open_storage(folder: Path) -> Storage:
    return Storage(folder / "tracker.db")


def now() -> float:
    return time.time()
