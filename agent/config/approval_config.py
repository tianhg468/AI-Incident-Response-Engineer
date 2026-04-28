"""Approval configuration and allowlists for human-in-the-loop safety."""

from typing import Literal

# Hard-coded allowlist of action types
# Novel actions not in this list always escalate to human review
ALLOWED_ACTION_TYPES = {
    "rollback": {
        "description": "Rollback deployment to previous version",
        "risk_level": "medium",
        "requires_approval": True,
        "can_auto_approve_in_eval": True
    },
    "scale": {
        "description": "Scale replicas or resources up/down",
        "risk_level": "low",
        "requires_approval": True,
        "can_auto_approve_in_eval": True
    },
    "restart": {
        "description": "Restart pods or deployment",
        "risk_level": "low",
        "requires_approval": True,
        "can_auto_approve_in_eval": True
    },
    "config_change": {
        "description": "Update configuration (ConfigMap, Secret, etc.)",
        "risk_level": "high",
        "requires_approval": True,
        "can_auto_approve_in_eval": True
    },
    "patch": {
        "description": "Apply a patch to running resources",
        "risk_level": "medium",
        "requires_approval": True,
        "can_auto_approve_in_eval": True
    }
}


def is_action_allowed(action_type: str) -> bool:
    """Check if action type is in the allowlist.

    Args:
        action_type: Action type to check

    Returns:
        True if allowed, False otherwise
    """
    return action_type in ALLOWED_ACTION_TYPES


def get_action_info(action_type: str) -> dict:
    """Get information about an action type.

    Args:
        action_type: Action type

    Returns:
        Action info dict, or None if not found
    """
    return ALLOWED_ACTION_TYPES.get(action_type)


def requires_approval(action_type: str, mode: Literal["eval", "live"]) -> bool:
    """Check if action requires human approval.

    Args:
        action_type: Action type
        mode: Running mode (eval or live)

    Returns:
        True if approval required
    """
    action_info = get_action_info(action_type)

    if not action_info:
        # Unknown actions always require approval
        return True

    if mode == "eval":
        # In eval mode, check if auto-approve is allowed
        return not action_info.get("can_auto_approve_in_eval", False)
    else:
        # In live mode, check requires_approval flag
        return action_info.get("requires_approval", True)


def validate_action_type(action_type: str) -> tuple[bool, str]:
    """Validate action type against allowlist.

    Args:
        action_type: Action type to validate

    Returns:
        Tuple of (is_valid, message)
    """
    if action_type in ALLOWED_ACTION_TYPES:
        return True, f"Action type '{action_type}' is allowed"

    return False, (
        f"Action type '{action_type}' is not in allowlist. "
        f"This action requires manual review and approval. "
        f"Allowed types: {', '.join(ALLOWED_ACTION_TYPES.keys())}"
    )
