"""Checkpointing utilities for durable state persistence."""

import os
import logging
from typing import Literal, Optional
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

logger = logging.getLogger(__name__)


def get_checkpointer(
    mode: Optional[Literal["sqlite", "postgres", "memory"]] = None,
    db_path: Optional[Path] = None
):
    """Get a checkpointer for state persistence.

    Args:
        mode: Checkpointer type. Defaults to CHECKPOINT_MODE env var.
              - "sqlite": File-based SQLite (for dev/testing)
              - "postgres": Postgres database (for production)
              - "memory": In-memory (no persistence)
        db_path: Path to SQLite database file. Defaults to ./data/checkpoints.db

    Returns:
        Checkpointer instance or None (for memory mode)
    """
    checkpoint_mode = mode or os.getenv("CHECKPOINT_MODE", "sqlite")

    if checkpoint_mode == "memory":
        logger.info("Using in-memory checkpointing (no persistence)")
        return None

    elif checkpoint_mode == "sqlite":
        # SQLite checkpointer for dev/testing
        if db_path is None:
            db_path = Path(os.getenv(
                "CHECKPOINT_DB_PATH",
                "./data/checkpoints.db"
            ))

        # Ensure directory exists
        db_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Using SQLite checkpointer: {db_path}")

        # SqliteSaver expects a connection string
        conn_string = f"sqlite:///{db_path}"

        # Create and return the checkpointer
        # The SqliteSaver will handle creating tables on first use
        checkpointer = SqliteSaver.from_conn_string(conn_string)

        return checkpointer

    elif checkpoint_mode == "postgres":
        # Postgres checkpointer for production
        # This would be implemented when needed for production deployment
        logger.warning("Postgres checkpointing not yet implemented, falling back to SQLite")

        # For now, fall back to SQLite
        return get_checkpointer(mode="sqlite", db_path=db_path)

    else:
        raise ValueError(f"Unknown checkpoint mode: {checkpoint_mode}")


def get_thread_id(incident_id: Optional[str] = None) -> str:
    """Get a thread ID for checkpointing.

    LangGraph uses thread_id to identify conversation threads.
    For incident response, we use the incident/alert ID as the thread.

    Args:
        incident_id: Incident or alert ID. If None, generates a new ID.

    Returns:
        Thread ID string
    """
    if incident_id:
        return f"incident_{incident_id}"

    # Generate a new thread ID
    import uuid
    return f"incident_{uuid.uuid4().hex[:8]}"


def list_investigations(checkpointer) -> list[dict]:
    """List all investigations stored in checkpointer.

    Args:
        checkpointer: LangGraph checkpointer instance

    Returns:
        List of investigation metadata dicts
    """
    if checkpointer is None:
        logger.warning("No checkpointer configured, cannot list investigations")
        return []

    # This is a placeholder - actual implementation would query the checkpointer
    # The SqliteSaver stores checkpoints in a table, we'd query it directly
    logger.info("Listing investigations from checkpointer")

    # TODO: Implement actual querying of checkpoint database
    # For now, return empty list
    return []


def get_investigation_status(checkpointer, thread_id: str) -> Optional[dict]:
    """Get the current status of an investigation.

    Args:
        checkpointer: LangGraph checkpointer instance
        thread_id: Investigation thread ID

    Returns:
        Investigation status dict or None if not found
    """
    if checkpointer is None:
        logger.warning("No checkpointer configured")
        return None

    # Placeholder - would query the latest checkpoint for this thread
    logger.info(f"Getting status for thread: {thread_id}")

    # TODO: Implement actual checkpoint querying
    return None
