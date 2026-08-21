"""Session store — SQLite persistence for jobs, reports, and thinking traces."""
import json
import sqlite3
from pathlib import Path
from typing import Optional
from ..config import settings


class SessionStore:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    status TEXT DEFAULT 'queued',
                    source_type TEXT,
                    document_title TEXT,
                    source_ref TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    report_json TEXT,
                    error TEXT
                )
            """)
            c.execute("""
                CREATE TABLE IF NOT EXISTS thinking_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT,
                    agent_role TEXT,
                    phase TEXT,
                    step TEXT,
                    focus_area TEXT,
                    raw_output TEXT,
                    timestamp TEXT,
                    FOREIGN KEY (job_id) REFERENCES jobs(id)
                )
            """)
            c.commit()

    def create_job(self, job_id: str, source_type: str, source_ref: str = ""):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO jobs (id, status, source_type, source_ref, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, "queued", source_type, source_ref, now, now)
            )
            c.commit()

    def update_job(self, job_id: str, **kwargs):
        from datetime import datetime, timezone
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values()) + [job_id]
        with self._conn() as c:
            c.execute(f"UPDATE jobs SET {set_clause} WHERE id = ?", values)
            c.commit()

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return dict(row) if row else None

    def add_thinking_step(self, job_id: str, agent_role: str, phase: str,
                          step: str, focus_area: str, raw_output: str):
        from datetime import datetime, timezone
        with self._conn() as c:
            c.execute(
                "INSERT INTO thinking_steps "
                "(job_id, agent_role, phase, step, focus_area, raw_output, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, agent_role, phase, step, focus_area, raw_output,
                 datetime.now(timezone.utc).isoformat())
            )
            c.commit()

    def get_thinking_steps(self, job_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM thinking_steps WHERE job_id = ? ORDER BY id", (job_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def list_jobs(self, limit: int = 20) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT id, status, source_type, document_title, created_at "
                "FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]


session_store = SessionStore()
