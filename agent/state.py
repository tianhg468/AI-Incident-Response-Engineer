"""State types for the incident response agent."""

from typing import TypedDict, Literal, Optional, Annotated
from datetime import datetime
from operator import add


class Incident(TypedDict):
    """Structured incident information from the alert."""
    alert_id: str
    service: str
    severity: Literal["critical", "high", "medium", "low"]
    time_window_start: datetime
    time_window_end: datetime
    affected_pods: list[str]
    affected_endpoints: list[str]
    description: str
    raw_alert: dict


class Evidence(TypedDict):
    """Aggregated evidence from observability and infrastructure tools."""
    logs: list[dict]  # Log entries from affected pods
    metrics: dict  # Relevant metrics data
    recent_deploys: list[dict]  # Recent deployments
    pod_status: dict  # Current pod status and events
    github_activity: list[dict]  # Recent commits/PRs
    runbooks: list[dict]  # Relevant runbooks found
    past_incidents: list[dict]  # Similar past incidents


class Hypothesis(TypedDict):
    """A hypothesis about the root cause."""
    rank: int  # Priority ranking (1 = highest)
    description: str  # What we think went wrong
    falsification_criterion: str  # Explicit test: "if X is true, this hypothesis is wrong"
    supporting_evidence: list[str]  # References to evidence
    verification_checks: list[str]  # Specific checks to run


class VerificationResult(TypedDict):
    """Result of verifying a hypothesis."""
    hypothesis: Hypothesis
    status: Literal["confirmed", "refuted", "inconclusive"]
    evidence: list[dict]  # Evidence gathered during verification
    reasoning: str  # Explanation of the result
    timestamp: datetime


class RecoveryProposal(TypedDict):
    """Proposed remediation action."""
    action_type: Literal["rollback", "scale", "restart", "config_change", "other"]
    description: str
    expected_effect: str
    blast_radius: str  # Impact assessment
    dry_run_output: Optional[str]
    commands: list[str]  # Actual commands/API calls to execute
    approval_status: Literal["pending", "approved", "rejected", "timeout"]
    approval_reasoning: Optional[str]
    decided_by: Optional[str]  # Who approved/rejected (user ID, "auto-approve", etc.)
    approval_method: Optional[str]  # How approved (slack, cli, auto_approve)


class ExecutionResult(TypedDict):
    """Result of executing a remediation."""
    success: bool
    output: str
    timestamp: datetime
    rollback_available: bool


class PostMortem(TypedDict):
    """Incident post-mortem report."""
    timeline: list[dict]  # Chronological events
    root_cause: str
    contributing_factors: list[str]
    remediation_taken: str
    action_items: list[str]
    incident_duration: float  # In minutes
    report_markdown: str


class AgentState(TypedDict):
    """Overall agent state, persisted via LangGraph checkpointing."""
    # Core incident data
    incident: Optional[Incident]
    evidence: Optional[Evidence]

    # Hypothesis tracking
    hypotheses: Annotated[list[Hypothesis], add]  # All generated hypotheses
    current_hypothesis_index: int  # Which hypothesis we're currently verifying
    verification_results: Annotated[list[VerificationResult], add]  # All verification attempts
    verification_round: int  # Number of verification attempts

    # Recovery and execution
    recovery_proposal: Optional[RecoveryProposal]
    execution_result: Optional[ExecutionResult]

    # Final output
    post_mortem: Optional[PostMortem]

    # Control flow
    status: Literal[
        "intake",
        "gathering_evidence",
        "diagnosing",
        "verifying",
        "awaiting_approval",
        "executing",
        "completed",
        "escalated"
    ]
    escalation_reason: Optional[str]
    human_feedback: Optional[str]  # Feedback from human when recovery proposal is rejected

    # Metadata
    messages: Annotated[list[dict], add]  # Conversation history for LLM context
    tool_calls: Annotated[list[dict], add]  # Track all tool invocations
    started_at: datetime
    completed_at: Optional[datetime]
