"""Storage backend interface.

Both MySQL and SQLite implementations conform to the same surface so that the
rest of the application stays backend-agnostic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class SessionStoreBase(ABC):
    """Abstract interface for persistent review-job storage."""

    @abstractmethod
    def init_schema(self) -> None:
        """Create tables if they do not exist."""

    @abstractmethod
    def create_job(self, job_id: str, source_type: str, source_ref: str = "") -> None:
        """Insert a new job row in 'queued' state."""

    @abstractmethod
    def update_job(self, job_id: str, **kwargs) -> None:
        """Patch arbitrary columns on the job row."""

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[dict]:
        """Return the full job row as a dict, or None if missing."""

    @abstractmethod
    def add_thinking_step(
        self, job_id: str, agent_role: str, phase: str,
        step: str, focus_area: str, raw_output: str,
    ) -> None:
        """Persist one thinking-trace entry."""

    @abstractmethod
    def get_thinking_steps(self, job_id: str) -> list[dict]:
        """Return all thinking steps for a job, ordered by insertion time."""

    @abstractmethod
    def list_jobs(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> list[dict]:
        """Return a list of recent jobs, newest first.

        Supports filtering by status, source_type and case-insensitive
        keyword search over document_title / source_ref.
        """

    @abstractmethod
    def count_jobs(
        self,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> int:
        """Total number of jobs matching the same filters as list_jobs()."""

    @abstractmethod
    def delete_job(self, job_id: str) -> None:
        """Remove a job and its thinking steps."""

    @abstractmethod
    def close(self) -> None:
        """Release any pooled resources."""