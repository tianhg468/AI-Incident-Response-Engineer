"""Checkpoint reader for extracting investigation data from the database."""

import sqlite3
from pathlib import Path
from typing import Optional
from langgraph.checkpoint.sqlite import SqliteSaver


class CheckpointReader:
    """Reader for LangGraph checkpoint database.

    Extracts investigation data from the SQLite checkpoint database
    for display in the dashboard.
    """

    def __init__(self, db_path: Optional[Path] = None):
        """Initialize checkpoint reader.

        Args:
            db_path: Path to checkpoint database. Defaults to ./data/checkpoints.db
        """
        if db_path is None:
            db_path = Path("./data/checkpoints.db")

        self.db_path = db_path

    def list_investigations(self) -> list[dict]:
        """List all investigations in the database.

        Returns:
            List of investigation summaries
        """
        if not self.db_path.exists():
            return []

        # Use LangGraph's SqliteSaver to properly deserialize checkpoints
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        saver = SqliteSaver(conn)

        try:
            # Get all unique thread IDs
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC")
            thread_ids = [row[0] for row in cursor.fetchall()]

            investigations = []

            for thread_id in thread_ids:
                try:
                    # Use SqliteSaver to get the latest checkpoint
                    # This properly deserializes the data
                    config = {"configurable": {"thread_id": thread_id}}
                    checkpoint_tuple = saver.get_tuple(config)

                    if checkpoint_tuple and checkpoint_tuple.checkpoint:
                        # Extract channel values (the actual state)
                        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})

                        # Create summary
                        incident = channel_values.get("incident", {})

                        investigations.append({
                            "thread_id": thread_id,
                            "service": incident.get("service", "Unknown") if incident else "Unknown",
                            "severity": incident.get("severity", "unknown") if incident else "unknown",
                            "status": channel_values.get("status", "unknown"),
                            "started_at": channel_values.get("started_at"),
                            "completed_at": channel_values.get("completed_at"),
                            "verification_rounds": channel_values.get("verification_round", 0),
                            "escalated": channel_values.get("status") == "escalated",
                            "checkpoint_id": checkpoint_tuple.checkpoint.get("id", "unknown")
                        })
                except Exception as e:
                    # Skip checkpoints that can't be loaded
                    print(f"Warning: Could not load checkpoint for {thread_id}: {e}")
                    continue

            return investigations

        finally:
            conn.close()

    def get_investigation(self, thread_id: str) -> Optional[dict]:
        """Get full investigation details.

        Args:
            thread_id: Investigation thread ID

        Returns:
            Complete investigation state or None if not found
        """
        if not self.db_path.exists():
            return None

        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        saver = SqliteSaver(conn)

        try:
            # Get latest checkpoint using SqliteSaver
            config = {"configurable": {"thread_id": thread_id}}
            checkpoint_tuple = saver.get_tuple(config)

            if checkpoint_tuple and checkpoint_tuple.checkpoint:
                # Return the channel values (state)
                return checkpoint_tuple.checkpoint.get("channel_values", {})

            return None

        finally:
            conn.close()

    def get_investigation_timeline(self, thread_id: str) -> list[dict]:
        """Get timeline of checkpoints for an investigation.

        Args:
            thread_id: Investigation thread ID

        Returns:
            List of checkpoints in chronological order
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        saver = SqliteSaver(conn)

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT checkpoint_id
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY checkpoint_id ASC
            """, (thread_id,))

            timeline = []

            for row in cursor.fetchall():
                checkpoint_id = row[0]
                try:
                    # Get specific checkpoint
                    config = {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_id": checkpoint_id
                        }
                    }
                    checkpoint_tuple = saver.get_tuple(config)

                    if checkpoint_tuple and checkpoint_tuple.checkpoint:
                        channel_values = checkpoint_tuple.checkpoint.get("channel_values", {})

                        timeline.append({
                            "checkpoint_id": checkpoint_id,
                            "status": channel_values.get("status"),
                            "verification_round": channel_values.get("verification_round", 0),
                            "state_snapshot": channel_values
                        })
                except Exception:
                    continue

            return timeline

        finally:
            conn.close()

    def get_statistics(self) -> dict:
        """Get overall statistics across all investigations.

        Returns:
            Dictionary with aggregate statistics
        """
        investigations = self.list_investigations()

        if not investigations:
            return {
                "total_investigations": 0,
                "completed": 0,
                "escalated": 0,
                "avg_verification_rounds": 0.0,
                "by_severity": {},
                "by_service": {}
            }

        total = len(investigations)
        completed = sum(1 for i in investigations if i["status"] == "completed")
        escalated = sum(1 for i in investigations if i["escalated"])

        verification_rounds = [i["verification_rounds"] for i in investigations]
        avg_rounds = sum(verification_rounds) / len(verification_rounds) if verification_rounds else 0.0

        # Group by severity
        by_severity = {}
        for inv in investigations:
            severity = inv["severity"]
            by_severity[severity] = by_severity.get(severity, 0) + 1

        # Group by service
        by_service = {}
        for inv in investigations:
            service = inv["service"]
            by_service[service] = by_service.get(service, 0) + 1

        return {
            "total_investigations": total,
            "completed": completed,
            "escalated": escalated,
            "avg_verification_rounds": avg_rounds,
            "by_severity": by_severity,
            "by_service": by_service
        }
