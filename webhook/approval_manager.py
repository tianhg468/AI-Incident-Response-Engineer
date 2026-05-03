"""Approval manager for tracking approval state.

This manages the state of approval requests and allows the agent
to check whether a user has approved or rejected an action.

Uses file-based storage for cross-process communication.
"""

import os
import json
import time
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from enum import Enum
from pathlib import Path


class ApprovalStatus(str, Enum):
    """Approval status."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REJECTED_WITH_FEEDBACK = "rejected_with_feedback"
    TIMEOUT = "timeout"


@dataclass
class Approval:
    """Approval request."""
    approval_id: str
    action_type: str
    description: str
    status: ApprovalStatus
    approved_by: Optional[str] = None
    feedback: Optional[str] = None
    created_at: float = 0.0
    updated_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.updated_at == 0.0:
            self.updated_at = time.time()


class ApprovalManager:
    """Manages approval state for the agent.

    Uses file-based storage for cross-process communication between
    the webhook server and the agent.
    """

    def __init__(self, storage_file: str = "./data/approvals.json"):
        self._approvals: Dict[str, Approval] = {}
        self._lock = threading.Lock()
        self._storage_file = Path(storage_file)

        # Create data directory if it doesn't exist
        self._storage_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing approvals from file
        self._load()

    def _load(self):
        """Load approvals from file."""
        if self._storage_file.exists():
            try:
                with open(self._storage_file, 'r') as f:
                    data = json.load(f)
                    for approval_id, approval_dict in data.items():
                        self._approvals[approval_id] = Approval(
                            approval_id=approval_dict["approval_id"],
                            action_type=approval_dict["action_type"],
                            description=approval_dict["description"],
                            status=ApprovalStatus(approval_dict["status"]),
                            approved_by=approval_dict.get("approved_by"),
                            feedback=approval_dict.get("feedback"),
                            created_at=approval_dict.get("created_at", time.time()),
                            updated_at=approval_dict.get("updated_at", time.time())
                        )
            except Exception as e:
                print(f"Warning: Failed to load approvals from {self._storage_file}: {e}")

    def _save(self):
        """Save approvals to file."""
        try:
            data = {aid: asdict(approval) for aid, approval in self._approvals.items()}
            # Convert enum to string
            for approval_dict in data.values():
                approval_dict["status"] = approval_dict["status"].value if isinstance(approval_dict["status"], Enum) else approval_dict["status"]

            with open(self._storage_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error: Failed to save approvals to {self._storage_file}: {e}")

    def create_approval(self, approval_id: str, action_type: str, description: str) -> Approval:
        """Create a new approval request."""
        with self._lock:
            approval = Approval(
                approval_id=approval_id,
                action_type=action_type,
                description=description,
                status=ApprovalStatus.PENDING
            )
            self._approvals[approval_id] = approval
            self._save()  # Persist to file
            return approval

    def approve(self, approval_id: str, approved_by: str):
        """Mark an approval as approved."""
        with self._lock:
            # Reload from file to get latest state
            self._load()

            if approval_id in self._approvals:
                approval = self._approvals[approval_id]
                approval.status = ApprovalStatus.APPROVED
                approval.approved_by = approved_by
                approval.updated_at = time.time()
                print(f"✅ Approval {approval_id} APPROVED by {approved_by}")
                self._save()  # Persist to file

    def reject(self, approval_id: str, rejected_by: str):
        """Mark an approval as rejected."""
        with self._lock:
            # Reload from file to get latest state
            self._load()

            if approval_id in self._approvals:
                approval = self._approvals[approval_id]
                approval.status = ApprovalStatus.REJECTED
                approval.approved_by = rejected_by
                approval.updated_at = time.time()
                print(f"❌ Approval {approval_id} REJECTED by {rejected_by}")
                self._save()  # Persist to file

    def reject_with_feedback(self, approval_id: str, rejected_by: str, feedback: str):
        """Mark an approval as rejected with feedback."""
        with self._lock:
            # Reload from file to get latest state
            self._load()

            if approval_id in self._approvals:
                approval = self._approvals[approval_id]
                approval.status = ApprovalStatus.REJECTED_WITH_FEEDBACK
                approval.approved_by = rejected_by
                approval.feedback = feedback
                approval.updated_at = time.time()
                print(f"🔄 Approval {approval_id} REJECTED WITH FEEDBACK by {rejected_by}: {feedback}")
                self._save()  # Persist to file

    def get_status(self, approval_id: str) -> Dict[str, Any]:
        """Get the status of an approval."""
        with self._lock:
            # Reload from file to get latest state from other processes
            self._load()

            if approval_id in self._approvals:
                approval = self._approvals[approval_id]
                result = asdict(approval)
                # Convert enum to string for JSON serialization
                if isinstance(result["status"], Enum):
                    result["status"] = result["status"].value
                return result
            else:
                return {
                    "approval_id": approval_id,
                    "status": "not_found",
                    "error": f"Approval {approval_id} not found"
                }

    def wait_for_approval(
        self,
        approval_id: str,
        timeout: float = 300.0,
        poll_interval: float = 1.0
    ) -> bool:
        """Wait for an approval to be approved or rejected.

        Args:
            approval_id: The approval ID to wait for
            timeout: Maximum time to wait in seconds (default 5 minutes)
            poll_interval: How often to check status in seconds

        Returns:
            True if approved, False if rejected or timeout
        """
        start_time = time.time()

        while (time.time() - start_time) < timeout:
            status = self.get_status(approval_id)

            if status.get("status") == ApprovalStatus.APPROVED:
                return True
            elif status.get("status") == ApprovalStatus.REJECTED:
                return False
            elif status.get("status") == ApprovalStatus.REJECTED_WITH_FEEDBACK:
                return False  # Still returns False but feedback is available in status

            # Check if timed out
            if (time.time() - start_time) >= timeout:
                with self._lock:
                    if approval_id in self._approvals:
                        self._approvals[approval_id].status = ApprovalStatus.TIMEOUT
                return False

            # Wait before checking again
            time.sleep(poll_interval)

        return False

    def list_pending(self) -> list[Dict[str, Any]]:
        """List all pending approvals."""
        with self._lock:
            return [
                asdict(approval)
                for approval in self._approvals.values()
                if approval.status == ApprovalStatus.PENDING
            ]

    def cleanup_old(self, max_age_seconds: float = 3600):
        """Clean up old approvals (older than max_age_seconds)."""
        with self._lock:
            current_time = time.time()
            to_remove = [
                approval_id
                for approval_id, approval in self._approvals.items()
                if (current_time - approval.created_at) > max_age_seconds
            ]

            for approval_id in to_remove:
                del self._approvals[approval_id]

            if to_remove:
                print(f"🧹 Cleaned up {len(to_remove)} old approvals")


# Global singleton instance
_approval_manager: Optional[ApprovalManager] = None


def get_approval_manager() -> ApprovalManager:
    """Get the global approval manager instance."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager
