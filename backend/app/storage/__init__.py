"""Storage backend factory.

Selects MySQL or SQLite at startup based on settings.storage_backend.
The rest of the application imports ``session_store`` from here and is
completely backend-agnostic.
"""
import logging

from ..config import settings
from .base import SessionStoreBase

logger = logging.getLogger(__name__)


def _create_store() -> SessionStoreBase:
    backend = settings.storage_backend.lower().strip()
    if backend == "mysql":
        try:
            from .mysql_store import MySQLStore
            store = MySQLStore()
            logger.info("Using MySQL storage backend.")
            return store
        except Exception as e:
            logger.warning(
                "MySQL backend unavailable (%s); falling back to SQLite.", e
            )
    # Default / fallback
    from .sqlite_store import SQLiteStore
    store = SQLiteStore()
    logger.info("Using SQLite storage backend at %s", settings.db_path)
    return store


session_store: SessionStoreBase = _create_store()
