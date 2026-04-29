"""Checkpoint reader for extracting investigation data from the database."""

import sqlite3
import json
from pathlib import Path
from typing import Optional
from datetime import datetime


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
        """List all investigations in the checkpoint database.

        Returns:
            List of investigation summaries
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Query checkpoints table
            # LangGraph stores checkpoints with thread_id, checkpoint_id, checkpoint_data
            cursor.execute("""
                SELECT DISTINCT thread_id
                FROM checkpoints
                ORDER BY thread_ts DESC
            """)

            thread_ids = [row[0] for row in cursor.fetchall()]

            investigations = []

            for thread_id in thread_ids:
                # Get latest checkpoint for this thread
                cursor.execute("""
                    SELECT checkpoint, thread_ts
                    FROM checkpoints
                    WHERE thread_id = ?
                    ORDER BY thread_ts DESC
                    LIMIT 1
                """, (thread_id,))

                row = cursor.fetchone()
                if row:
                    checkpoint_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]

                    # Extract state from checkpoint
                    # LangGraph checkpoint structure: {"v": 1, "ts": "...", "channel_values": {...}}
                    state = checkpoint_data.get("channel_values", {})

                    # Create summary
                    incident = state.get("incident", {})

                    investigations.append({
                        "thread_id": thread_id,
                        "service": incident.get("service", "Unknown") if incident else "Unknown",
                        "severity": incident.get("severity", "unknown") if incident else "unknown",
                        "status": state.get("status", "unknown"),
                        "started_at": state.get("started_at"),
                        "completed_at": state.get("completed_at"),
                        "verification_rounds": state.get("verification_round", 0),
                        "escalated": state.get("status") == "escalated",
                        "timestamp": row[1]
                    })

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

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get latest checkpoint for thread
            cursor.execute("""
                SELECT checkpoint
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY thread_ts DESC
                LIMIT 1
            """, (thread_id,))

            row = cursor.fetchone()
            if not row:
                return None

            checkpoint_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
            state = checkpoint_data.get("channel_values", {})

            return state

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

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT checkpoint, thread_ts, checkpoint_ns
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY thread_ts ASC, checkpoint_ns ASC
            """, (thread_id,))

            timeline = []

            for row in cursor.fetchall():
                checkpoint_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                state = checkpoint_data.get("channel_values", {})

                timeline.append({
                    "timestamp": row[1],
                    "checkpoint_ns": row[2],
                    "status": state.get("status"),
                    "verification_round": state.get("verification_round", 0),
                    "state_snapshot": state
                })

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
