"""Evaluation rubric for scoring incident response investigations."""

from typing import Literal, Optional
from dataclasses import dataclass
import re


@dataclass
class EvalScenario:
    """Evaluation scenario with ground truth."""
    scenario_id: str
    name: str
    description: str

    # Ground truth
    ground_truth_root_cause: str
    ground_truth_root_cause_keywords: list[str]  # Keywords to match in hypothesis
    acceptable_remediations: list[str]  # List of acceptable action types

    # Expected behavior
    expected_verification_rounds: int  # Ideal number of rounds
    max_acceptable_rounds: int  # Maximum before it's considered poor performance

    # Metadata
    difficulty: Literal["easy", "medium", "hard"]
    incident_type: str  # e.g., "oom", "5xx_spike", "dns_failure"


@dataclass
class EvalResult:
    """Result of evaluating a single investigation."""
    scenario_id: str

    # Root cause scoring
    root_cause_score: Literal["exact", "partial", "wrong"]
    root_cause_reasoning: str

    # Remediation scoring
    remediation_acceptable: bool
    remediation_reasoning: str

    # Performance metrics
    verification_rounds: int
    total_llm_calls: int
    total_tool_calls: int
    estimated_cost_usd: float

    # Investigation outcome
    final_status: str
    escalated: bool

    # Timing
    duration_seconds: float


def score_root_cause_identification(
    hypothesis: Optional[str],
    ground_truth: str,
    ground_truth_keywords: list[str]
) -> tuple[Literal["exact", "partial", "wrong"], str]:
    """Score root cause identification accuracy.

    Args:
        hypothesis: The agent's confirmed hypothesis description
        ground_truth: Ground truth root cause from scenario
        ground_truth_keywords: Keywords that must appear in hypothesis

    Returns:
        Tuple of (score, reasoning)
    """
    if hypothesis is None:
        return "wrong", "No hypothesis was confirmed"

    hypothesis_lower = hypothesis.lower()
    ground_truth_lower = ground_truth.lower()

    # Exact match: hypothesis contains the ground truth phrase or vice versa
    if ground_truth_lower in hypothesis_lower or hypothesis_lower in ground_truth_lower:
        return "exact", f"Hypothesis matches ground truth: '{hypothesis}'"

    # Partial match: hypothesis contains most of the keywords
    matched_keywords = [kw for kw in ground_truth_keywords if kw.lower() in hypothesis_lower]
    match_ratio = len(matched_keywords) / len(ground_truth_keywords) if ground_truth_keywords else 0

    if match_ratio >= 0.7:  # At least 70% of keywords matched
        return "partial", f"Hypothesis partially matches ({len(matched_keywords)}/{len(ground_truth_keywords)} keywords): '{hypothesis}'"
    elif match_ratio >= 0.4:  # 40-70% match
        return "partial", f"Hypothesis weakly matches ({len(matched_keywords)}/{len(ground_truth_keywords)} keywords): '{hypothesis}'"
    else:
        return "wrong", f"Hypothesis does not match ground truth ({len(matched_keywords)}/{len(ground_truth_keywords)} keywords): '{hypothesis}'"


def score_remediation_acceptability(
    action_type: Optional[str],
    acceptable_actions: list[str]
) -> tuple[bool, str]:
    """Score whether the remediation is acceptable.

    Args:
        action_type: The proposed action type
        acceptable_actions: List of acceptable action types for this scenario

    Returns:
        Tuple of (acceptable, reasoning)
    """
    if action_type is None:
        return False, "No remediation action was proposed"

    if action_type in acceptable_actions:
        return True, f"Action '{action_type}' is acceptable for this scenario"
    else:
        return False, f"Action '{action_type}' is not acceptable. Expected one of: {acceptable_actions}"


def score_verification_efficiency(
    actual_rounds: int,
    expected_rounds: int,
    max_acceptable_rounds: int
) -> tuple[Literal["excellent", "good", "acceptable", "poor"], str]:
    """Score verification efficiency based on number of rounds.

    Args:
        actual_rounds: Actual number of verification rounds
        expected_rounds: Expected number of rounds for this scenario
        max_acceptable_rounds: Maximum acceptable rounds

    Returns:
        Tuple of (score, reasoning)
    """
    if actual_rounds <= expected_rounds:
        return "excellent", f"Verification completed in {actual_rounds} rounds (expected: {expected_rounds})"
    elif actual_rounds <= expected_rounds + 1:
        return "good", f"Verification completed in {actual_rounds} rounds (expected: {expected_rounds})"
    elif actual_rounds <= max_acceptable_rounds:
        return "acceptable", f"Verification completed in {actual_rounds} rounds (max acceptable: {max_acceptable_rounds})"
    else:
        return "poor", f"Verification took {actual_rounds} rounds (max acceptable: {max_acceptable_rounds})"


def estimate_cost(
    llm_calls: int,
    tool_calls: int,
    avg_tokens_per_call: int = 2000,
    cost_per_million_tokens: float = 3.0
) -> float:
    """Estimate cost of investigation.

    Rough estimation based on Claude Sonnet 3.5 pricing.

    Args:
        llm_calls: Number of LLM calls made
        tool_calls: Number of MCP tool calls
        avg_tokens_per_call: Average tokens per LLM call
        cost_per_million_tokens: Cost per million tokens (input + output blended)

    Returns:
        Estimated cost in USD
    """
    # Estimate total tokens (input + output)
    total_tokens = llm_calls * avg_tokens_per_call

    # Cost calculation
    cost_usd = (total_tokens / 1_000_000) * cost_per_million_tokens

    return cost_usd


def calculate_pass_rate(results: list[EvalResult]) -> dict:
    """Calculate overall pass rates from eval results.

    Args:
        results: List of evaluation results

    Returns:
        Dictionary with pass rate metrics
    """
    if not results:
        return {
            "total_scenarios": 0,
            "root_cause_exact": 0.0,
            "root_cause_partial_or_better": 0.0,
            "remediation_acceptable": 0.0,
            "avg_verification_rounds": 0.0,
            "avg_cost_usd": 0.0,
            "escalation_rate": 0.0
        }

    total = len(results)

    return {
        "total_scenarios": total,
        "root_cause_exact": sum(1 for r in results if r.root_cause_score == "exact") / total,
        "root_cause_partial_or_better": sum(1 for r in results if r.root_cause_score in ["exact", "partial"]) / total,
        "remediation_acceptable": sum(1 for r in results if r.remediation_acceptable) / total,
        "avg_verification_rounds": sum(r.verification_rounds for r in results) / total,
        "avg_cost_usd": sum(r.estimated_cost_usd for r in results) / total,
        "escalation_rate": sum(1 for r in results if r.escalated) / total
    }


def format_eval_report(results: list[EvalResult], scenarios: dict[str, EvalScenario]) -> str:
    """Format evaluation results as a markdown report.

    Args:
        results: List of evaluation results
        scenarios: Dictionary mapping scenario_id to EvalScenario

    Returns:
        Markdown formatted report
    """
    metrics = calculate_pass_rate(results)

    report = f"""# Incident Response Agent - Evaluation Report

## Summary

| Metric | Score |
|--------|-------|
| **Total Scenarios** | {metrics['total_scenarios']} |
| **Root Cause Accuracy (Exact)** | {metrics['root_cause_exact']:.1%} |
| **Root Cause Accuracy (Partial or Better)** | {metrics['root_cause_partial_or_better']:.1%} |
| **Remediation Acceptability** | {metrics['remediation_acceptable']:.1%} |
| **Avg Verification Rounds** | {metrics['avg_verification_rounds']:.1f} |
| **Avg Cost per Incident** | ${metrics['avg_cost_usd']:.4f} |
| **Escalation Rate** | {metrics['escalation_rate']:.1%} |

## Per-Scenario Results

"""

    for result in results:
        scenario = scenarios.get(result.scenario_id)
        scenario_name = scenario.name if scenario else result.scenario_id

        report += f"""### {scenario_name}

- **Root Cause**: {result.root_cause_score.upper()} - {result.root_cause_reasoning}
- **Remediation**: {'✅ Acceptable' if result.remediation_acceptable else '❌ Not Acceptable'} - {result.remediation_reasoning}
- **Verification Rounds**: {result.verification_rounds}
- **Status**: {result.final_status}
- **Cost**: ${result.estimated_cost_usd:.4f}
- **Duration**: {result.duration_seconds:.1f}s

"""

    return report
