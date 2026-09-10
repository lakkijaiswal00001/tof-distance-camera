"""
core/database.py
================
Offline-first SQLite database manager.

Responsibilities:
  - Auto-create the `data/` directory and `gait_records.db` on first run.
  - Persist all screening sessions (metadata + risk classification).
  - Persist per-session detailed kinematic metrics as a linked record.
  - Provide query methods for the history viewer.

Schema
------
  screening_sessions
    id INTEGER PK AUTOINCREMENT
    timestamp TEXT (ISO-8601)
    mode TEXT ("webcam" | "file")
    duration_seconds REAL
    risk_level TEXT
    risk_score INTEGER
    data_sufficient INTEGER (boolean)
    summary TEXT
    frame_count INTEGER
    step_count INTEGER

  gait_metrics
    id INTEGER PK AUTOINCREMENT
    session_id INTEGER FK → screening_sessions.id
    left_knee_mean REAL
    left_knee_min REAL
    left_knee_max REAL
    left_knee_rom REAL
    right_knee_mean REAL
    right_knee_min REAL
    right_knee_max REAL
    right_knee_rom REAL
    knee_angle_asymmetry REAL
    hip_sway_asymmetry_pct REAL
    stride_duration_mean REAL
    stride_duration_cv REAL
    cadence_spm REAL
    left_stance_ratio REAL
    right_stance_ratio REAL

Offline-first: uses Python stdlib sqlite3 — zero external dependencies.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator, List, Optional

from .gait_processor import GaitMetrics
from .oa_classifier  import RiskAssessment

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes (query results)
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class SessionRecord:
    """Flattened view of a screening session (sessions + metrics joined)."""
    id:                    int
    timestamp:             str
    mode:                  str
    duration_seconds:      float
    risk_level:            str
    risk_score:            int
    data_sufficient:       bool
    summary:               str
    frame_count:           int
    step_count:            int
    # Metrics (may be None if metrics row missing)
    left_knee_rom:         Optional[float]
    right_knee_rom:        Optional[float]
    knee_angle_asymmetry:  Optional[float]
    hip_sway_asymmetry_pct:Optional[float]
    stride_duration_mean:  Optional[float]
    stride_duration_cv:    Optional[float]
    cadence_spm:           Optional[float]
    left_stance_ratio:     Optional[float]
    right_stance_ratio:    Optional[float]


# ──────────────────────────────────────────────────────────────────────────────
# DDL
# ──────────────────────────────────────────────────────────────────────────────

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS screening_sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT    NOT NULL,
    mode             TEXT    NOT NULL DEFAULT 'webcam',
    duration_seconds REAL    NOT NULL DEFAULT 0.0,
    risk_level       TEXT    NOT NULL,
    risk_score       INTEGER NOT NULL DEFAULT 0,
    data_sufficient  INTEGER NOT NULL DEFAULT 1,
    summary          TEXT    NOT NULL DEFAULT '',
    frame_count      INTEGER NOT NULL DEFAULT 0,
    step_count       INTEGER NOT NULL DEFAULT 0
);
"""

_CREATE_METRICS = """
CREATE TABLE IF NOT EXISTS gait_metrics (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id              INTEGER NOT NULL REFERENCES screening_sessions(id)
                                            ON DELETE CASCADE,
    left_knee_mean          REAL,
    left_knee_min           REAL,
    left_knee_max           REAL,
    left_knee_rom           REAL,
    right_knee_mean         REAL,
    right_knee_min          REAL,
    right_knee_max          REAL,
    right_knee_rom          REAL,
    knee_angle_asymmetry    REAL,
    hip_sway_asymmetry_pct  REAL,
    stride_duration_mean    REAL,
    stride_duration_cv      REAL,
    cadence_spm             REAL,
    left_stance_ratio       REAL,
    right_stance_ratio      REAL
);
"""


# ──────────────────────────────────────────────────────────────────────────────
# DatabaseManager
# ──────────────────────────────────────────────────────────────────────────────

class DatabaseManager:
    """
    Manages the local SQLite database for gait screening results.

    Parameters
    ----------
    db_path : str | Path
        Path to the SQLite file.  The parent directory is created if absent.
        Defaults to ``<project_root>/data/gait_records.db``.

    Usage
    -----
    ::

        db = DatabaseManager()
        session_id = db.save_session(metrics, assessment, mode="webcam",
                                     duration=12.5)
        records = db.get_all_sessions()
        record  = db.get_session_by_id(session_id)
    """

    DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gait_records.db"

    # How many times to retry a locked-database operation
    _MAX_RETRIES   = 5
    _RETRY_DELAY_S = 0.25   # seconds between retries

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        try:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.error("Cannot create DB directory %s: %s", self._db_path.parent, exc)
            raise
        self._init_schema()

    # ── Schema initialisation & migration ─────────────────────────────────────────

    def _init_schema(self) -> None:
        """
        Create tables if they do not exist and check for any missing
        columns added in later versions (non-destructive migration).
        Retries on a locked database up to _MAX_RETRIES times.
        """
        for attempt in range(self._MAX_RETRIES):
            try:
                with self._connect() as conn:
                    conn.execute("PRAGMA foreign_keys = ON;")
                    conn.execute("PRAGMA journal_mode = WAL;")  # safe concurrent reads
                    conn.execute("PRAGMA busy_timeout = 5000;")
                    conn.execute(_CREATE_SESSIONS)
                    conn.execute(_CREATE_METRICS)
                    self._ensure_schema_current(conn)
                log.info("Database schema ready: %s", self._db_path)
                return
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower() and attempt < self._MAX_RETRIES - 1:
                    log.warning(
                        "DB locked during init (attempt %d/%d) — retrying in %.2fs",
                        attempt + 1, self._MAX_RETRIES, self._RETRY_DELAY_S,
                    )
                    time.sleep(self._RETRY_DELAY_S)
                else:
                    log.error("Database init failed after %d attempts: %s", attempt + 1, exc)
                    raise
            except Exception as exc:
                log.error("Unexpected DB init error: %s", exc)
                raise

    @staticmethod
    def _ensure_schema_current(conn: sqlite3.Connection) -> None:
        """
        Non-destructive schema migration: add any columns that are present
        in the DDL but missing in an older on-disk database.
        Safe to run on every startup.
        """
        # Introspect existing columns for each table
        existing = {}
        for table in ("screening_sessions", "gait_metrics"):
            try:
                rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
                existing[table] = {r[1] for r in rows}  # r[1] = column name
            except Exception:
                existing[table] = set()

        # screening_sessions additions (none yet — placeholder for future fields)
        # gait_metrics additions (none yet — placeholder for future fields)
        # Example pattern for future columns:
        # if "new_column" not in existing.get("screening_sessions", set()):
        #     conn.execute("ALTER TABLE screening_sessions ADD COLUMN new_column REAL")
        #     log.info("Migrated screening_sessions: added new_column")


    # ── Write ─────────────────────────────────────────────────────────────────

    def save_session(
        self,
        metrics: GaitMetrics,
        assessment: RiskAssessment,
        mode: str = "webcam",
        duration_seconds: float = 0.0,
    ) -> int:
        """
        Persist a screening session and its kinematic metrics atomically.

        Both the session row and the metrics row are written inside a
        single transaction.  On failure the transaction is rolled back
        and the error is logged — no partial writes are left in the DB.
        Retries on a temporarily locked database.

        Returns
        -------
        int : The auto-assigned session ID, or -1 on unrecoverable failure.
        """
        ts = datetime.now(timezone.utc).isoformat()

        for attempt in range(self._MAX_RETRIES):
            conn: Optional[sqlite3.Connection] = None
            try:
                conn = sqlite3.connect(str(self._db_path), timeout=10)
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA busy_timeout = 5000;")
                conn.execute("BEGIN IMMEDIATE;")   # serialise concurrent writers

                cur = conn.execute(
                    """
                    INSERT INTO screening_sessions
                      (timestamp, mode, duration_seconds, risk_level,
                       risk_score, data_sufficient, summary,
                       frame_count, step_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ts,
                        mode,
                        duration_seconds,
                        assessment.level.value,
                        assessment.score,
                        int(assessment.data_sufficient),
                        assessment.summary,
                        metrics.frame_count,
                        metrics.step_count,
                    ),
                )
                session_id = cur.lastrowid

                conn.execute(
                    """
                    INSERT INTO gait_metrics
                      (session_id,
                       left_knee_mean,  left_knee_min,   left_knee_max,  left_knee_rom,
                       right_knee_mean, right_knee_min,  right_knee_max, right_knee_rom,
                       knee_angle_asymmetry, hip_sway_asymmetry_pct,
                       stride_duration_mean, stride_duration_cv, cadence_spm,
                       left_stance_ratio, right_stance_ratio)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        metrics.left_knee_mean,  metrics.left_knee_min,
                        metrics.left_knee_max,   metrics.left_knee_rom,
                        metrics.right_knee_mean, metrics.right_knee_min,
                        metrics.right_knee_max,  metrics.right_knee_rom,
                        metrics.knee_angle_asymmetry,
                        metrics.hip_sway_asymmetry_pct,
                        metrics.stride_duration_mean,
                        metrics.stride_duration_cv,
                        metrics.cadence_spm,
                        metrics.left_stance_ratio,
                        metrics.right_stance_ratio,
                    ),
                )
                conn.commit()
                log.info("Session #%d saved to database.", session_id)
                return session_id

            except sqlite3.OperationalError as exc:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                if "locked" in str(exc).lower() and attempt < self._MAX_RETRIES - 1:
                    log.warning(
                        "DB locked during save (attempt %d/%d) — retrying…",
                        attempt + 1, self._MAX_RETRIES,
                    )
                    time.sleep(self._RETRY_DELAY_S)
                else:
                    log.error("DB write failed after %d attempts: %s", attempt + 1, exc)
                    print(f"[DB ERROR] Could not save session: {exc}")
                    return -1
            except Exception as exc:
                if conn:
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                log.error("Unexpected DB write error: %s", exc)
                print(f"[DB ERROR] Unexpected error saving session: {exc}")
                return -1
            finally:
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass

        return -1   # Should not reach here


    # ── Read ──────────────────────────────────────────────────────────────────

    def get_all_sessions(self, limit: int = 100) -> List[SessionRecord]:
        """
        Return the most recent *limit* sessions, newest first.
        Each record is a joined view of sessions + metrics.
        """
        query = self._joined_query() + " ORDER BY s.id DESC LIMIT ?"
        with self._connect() as conn:
            rows = conn.execute(query, (limit,)).fetchall()
        return [self._row_to_record(r) for r in rows]

    def get_session_by_id(self, session_id: int) -> Optional[SessionRecord]:
        """Return a single session record by primary key, or None."""
        query = self._joined_query() + " WHERE s.id = ?"
        with self._connect() as conn:
            row = conn.execute(query, (session_id,)).fetchone()
        return self._row_to_record(row) if row else None

    def get_session_count(self) -> int:
        """Return total number of saved sessions."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM screening_sessions"
            ).fetchone()
        return row[0] if row else 0

    def delete_session(self, session_id: int) -> bool:
        """Delete a session (and cascade to metrics). Returns True if deleted."""
        with self._connect() as conn:
            conn.execute("PRAGMA foreign_keys = ON;")
            cur = conn.execute(
                "DELETE FROM screening_sessions WHERE id = ?", (session_id,)
            )
            rowcount = cur.rowcount  # Capture BEFORE exiting context
            conn.commit()
        return rowcount > 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Open a connection, yield it, commit on clean exit, rollback on error.
        Sets busy_timeout so concurrent writers do not immediately error.
        """
        conn = sqlite3.connect(str(self._db_path), timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout = 5000;")
        try:
            yield conn
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass


    @staticmethod
    def _joined_query() -> str:
        return """
            SELECT
              s.id, s.timestamp, s.mode, s.duration_seconds,
              s.risk_level, s.risk_score, s.data_sufficient,
              s.summary, s.frame_count, s.step_count,
              m.left_knee_rom, m.right_knee_rom,
              m.knee_angle_asymmetry, m.hip_sway_asymmetry_pct,
              m.stride_duration_mean, m.stride_duration_cv,
              m.cadence_spm, m.left_stance_ratio, m.right_stance_ratio
            FROM screening_sessions s
            LEFT JOIN gait_metrics m ON m.session_id = s.id
        """

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> SessionRecord:
        return SessionRecord(
            id=row["id"],
            timestamp=row["timestamp"],
            mode=row["mode"],
            duration_seconds=row["duration_seconds"],
            risk_level=row["risk_level"],
            risk_score=row["risk_score"],
            data_sufficient=bool(row["data_sufficient"]),
            summary=row["summary"],
            frame_count=row["frame_count"],
            step_count=row["step_count"],
            left_knee_rom=row["left_knee_rom"],
            right_knee_rom=row["right_knee_rom"],
            knee_angle_asymmetry=row["knee_angle_asymmetry"],
            hip_sway_asymmetry_pct=row["hip_sway_asymmetry_pct"],
            stride_duration_mean=row["stride_duration_mean"],
            stride_duration_cv=row["stride_duration_cv"],
            cadence_spm=row["cadence_spm"],
            left_stance_ratio=row["left_stance_ratio"],
            right_stance_ratio=row["right_stance_ratio"],
        )
