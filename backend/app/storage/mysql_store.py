"""MySQL-backed session store.

Uses PyMySQL with a thread-safe connection pool.  Designed for multi-user
or persistent deployments where SQLite is not sufficient.
"""
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

import pymysql
from pymysql.cursors import DictCursor
from dbutils.pooled_db import PooledDB

from ..config import settings
from .base import SessionStoreBase

logger = logging.getLogger(__name__)

_CREATE_JOBS = """
CREATE TABLE IF NOT EXISTS jobs (
    id             VARCHAR(32)  PRIMARY KEY,
    status         VARCHAR(20)  DEFAULT 'queued',
    source_type    VARCHAR(20),
    document_title TEXT,
    source_ref     TEXT,
    created_at     VARCHAR(40),
    updated_at     VARCHAR(40),
    report_json    LONGTEXT,
    error          TEXT,
    INDEX idx_jobs_created (created_at),
    INDEX idx_jobs_status (status),
    INDEX idx_jobs_source (source_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

_CREATE_THINKING = """
CREATE TABLE IF NOT EXISTS thinking_steps (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    job_id      VARCHAR(32) NOT NULL,
    agent_role  VARCHAR(30),
    phase       VARCHAR(30),
    step        VARCHAR(40),
    focus_area  TEXT,
    raw_output  LONGTEXT,
    timestamp   VARCHAR(40),
    INDEX idx_thinking_job (job_id),
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


class MySQLStore(SessionStoreBase):
    """MySQL implementation of SessionStoreBase."""

    def __init__(
        self,
        host: str = None,
        port: int = None,
        user: str = None,
        password: str = None,
        database: str = None,
        pool_size: int = None,
    ):
        self._host = host or settings.mysql_host
        self._port = port or settings.mysql_port
        self._user = user or settings.mysql_user
        self._password = password or settings.mysql_password
        self._database = database or settings.mysql_database
        self._pool_size = pool_size or settings.mysql_pool_size
        self._pool: PooledDB = None
        self._local = threading.local()
        self.init_schema()

    # -- pool -----------------------------------------------------------

    def _get_pool(self) -> PooledDB:
        if self._pool is None:
            self._pool = PooledDB(
                creator=pymysql,
                maxconnections=self._pool_size,
                mincached=1,
                maxcached=self._pool_size,
                host=self._host,
                port=self._port,
                user=self._user,
                password=self._password,
                database=self._database,
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
            )
            logger.info(
                "MySQL pool created: %s@%s:%s/%s (pool=%d)",
                self._user, self._host, self._port, self._database,
                self._pool_size,
            )
        return self._pool

    def _conn(self):
        """Return a pooled connection.  Must be closed by the caller."""
        return self._get_pool().connection()

    # -- schema --------------------------------------------------------

    def init_schema(self) -> None:
        try:
            with self._conn() as c:
                with c.cursor() as cur:
                    cur.execute(_CREATE_JOBS)
                    cur.execute(_CREATE_THINKING)
        except Exception as e:
            logger.error("Failed to init MySQL schema: %s", e)
            raise

    # -- CRUD ----------------------------------------------------------

    def create_job(self, job_id: str, source_type: str, source_ref: str = "") -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO jobs (id, status, source_type, source_ref, "
                    "created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                    (job_id, "queued", source_type, source_ref, now, now),
                )

    def update_job(self, job_id: str, **kwargs) -> None:
        kwargs["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = %s" for k in kwargs)
        values = list(kwargs.values()) + [job_id]
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    f"UPDATE jobs SET {set_clause} WHERE id = %s", values
                )

    def get_job(self, job_id: str) -> Optional[dict]:
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute("SELECT * FROM jobs WHERE id = %s", (job_id,))
                row = cur.fetchone()
                return dict(row) if row else None

    def add_thinking_step(
        self, job_id: str, agent_role: str, phase: str,
        step: str, focus_area: str, raw_output: str,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "INSERT INTO thinking_steps "
                    "(job_id, agent_role, phase, step, focus_area, "
                    "raw_output, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (job_id, agent_role, phase, step, focus_area,
                     raw_output, now),
                )

    def get_thinking_steps(self, job_id: str) -> list[dict]:
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(
                    "SELECT * FROM thinking_steps "
                    "WHERE job_id = %s ORDER BY id", (job_id,)
                )
                return [dict(r) for r in cur.fetchall()]

    def list_jobs(
        self, limit: int = 20, offset: int = 0,
        status: Optional[str] = None, source_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> list[dict]:
        where, params = [], []
        if status:
            where.append("status = %s"); params.append(status)
        if source_type:
            where.append("source_type = %s"); params.append(source_type)
        if keyword:
            where.append(
                "(LOWER(IFNULL(document_title, '')) LIKE %s "
                "OR LOWER(IFNULL(source_ref, '')) LIKE %s)"
            )
            kw = f"%{keyword.lower()}%"
            params += [kw, kw]
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT id, status, source_type, document_title, "
            "source_ref, created_at, updated_at, "
            "CASE WHEN report_json IS NULL THEN 0 ELSE 1 END AS has_report "
            f"FROM jobs {where_sql} "
            "ORDER BY created_at DESC LIMIT %s OFFSET %s"
        )
        params += [limit, offset]
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(sql, params)
                return [dict(r) for r in cur.fetchall()]

    def count_jobs(
        self, status: Optional[str] = None,
        source_type: Optional[str] = None, keyword: Optional[str] = None,
    ) -> int:
        where, params = [], []
        if status:
            where.append("status = %s"); params.append(status)
        if source_type:
            where.append("source_type = %s"); params.append(source_type)
        if keyword:
            where.append(
                "(LOWER(IFNULL(document_title, '')) LIKE %s "
                "OR LOWER(IFNULL(source_ref, '')) LIKE %s)"
            )
            kw = f"%{keyword.lower()}%"
            params += [kw, kw]
        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        with self._conn() as c:
            with c.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) AS n FROM jobs {where_sql}", params)
                row = cur.fetchone()
                return row["n"] if row else 0

    def delete_job(self, job_id: str) -> None:
        with self._conn() as c:
            with c.cursor() as cur:
                # FK ON DELETE CASCADE handles thinking_steps
                cur.execute("DELETE FROM jobs WHERE id = %s", (job_id,))

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None
            logger.info("MySQL pool closed.")
