"""SQLite-backed session store. Suitable for single-machine, file-based use."""
import json
import sqlite3
from pathlib import Path
from typing import Optional

from ..config import settings
from .base import SessionStoreBase


class SQLiteStore(SessionStoreBase):
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self):
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
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_thinking_job "
                "ON thinking_steps(job_id)"
            )
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_created "
                "ON jobs(created_at DESC)"
            )
            c.commit()

    def create_job(self, job_id: str, source_type: str, source_ref: str = ""):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            c.execute(
                "INSERT INTO jobs (id, status, source_type, source_ref, "
                "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, "queued", source_type, source_ref, now, now),
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
            row = c.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
            return dict(row) if row else None

    def add_thinking_step(self, job_id, agent_role, phase, step,
                          focus_area, raw_output):
        from datetime import datetime, timezone
        with self._conn() as c:
            c.execute(
                "INSERT INTO thinking_steps "
                "(job_id, agent_role, phase, step, focus_area, "
                "raw_output, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (job_id, agent_role, phase, step, focus_area, raw_output,
                 datetime.now(timezone.utc).isoformat()),
            )
            c.commit()

    def get_thinking_steps(self, job_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM thinking_steps WHERE job_id = ? ORDER BY id",
                (job_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def list_jobs(self, limit=20, offset=0, status=None, source_type=None,
                  keyword=None):
        where, params = [], []
        if status:
            where.append("status = ?"); params.append(status)
        if source_type:
            where.append("source_type = ?"); params.append(source_type)
        if keyword:
            where.append(
                "(LOWER(IFNULL(document_title, '')) LIKE ? "
                "OR LOWER(IFNULL(source_ref, '')) LIKE ?)"
            )
            kw = f"%{keyword.lower()}%"
            params += [kw, kw]
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT id, status, source_type, document_title, "
            "source_ref, created_at, updated_at, "
            "CASE WHEN report_json IS NULL THEN 0 ELSE 1 END AS has_report "
            "FROM jobs "
            f"{where_sql} "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?"
        )
        params += [limit, offset]
        with self._conn() as c:
            rows = c.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def count_jobs(self, status=None, source_type=None, keyword=None):
        where, params = [], []
        if status:
            where.append("status = ?"); params.append(status)
        if source_type:
            where.append("source_type = ?"); params.append(source_type)
        if keyword:
            where.append(
                "(LOWER(IFNULL(document_title, '')) LIKE ? "
                "OR LOWER(IFNULL(source_ref, '')) LIKE ?)"
            )
            kw = f"%{keyword.lower()}%"
            params += [kw, kw]
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._conn() as c:
            return c.execute(
                f"SELECT COUNT(*) FROM jobs {where_sql}", params
            ).fetchone()[0]

    def delete_job(self, job_id: str):
        with self._conn() as c:
            c.execute("DELETE FROM thinking_steps WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            c.commit()

    def close(self):
        # SQLite has no persistent pool; nothing to release.
        pass