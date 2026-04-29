"""Test evaluation harness."""

import os
from pathlib import Path

# Set eval mode
os.environ["MODE"] = "eval"
os.environ["SCENARIO"] = "oom_after_deploy"

from evals.runner import EvalRunner
from evals.rubric import calculate_pass_rate


def test_eval_runner_single_scenario():
    """Test running a single evaluation scenario."""
    print("\n" + "=" * 80)
    print("TESTING: Eval Runner - Single Scenario")
    print("=" * 80 + "\n")

    # Create runner
    runner = EvalRunner()

    # Verify scenarios loaded
    assert len(runner.scenarios) > 0, "Should load at least one scenario"
    print(f"Loaded {len(runner.scenarios)} scenarios")

    # Run OOM scenario
    result = runner.run_scenario("oom_after_deploy")

    print(f"\nScenario Results:")
    print(f"  Root Cause: {result.root_cause_score}")
    print(f"  Reasoning: {result.root_cause_reasoning}")
    print(f"  Remediation: {'Acceptable' if result.remediation_acceptable else 'Not Acceptable'}")
    print(f"  Reasoning: {result.remediation_reasoning}")
    print(f"  Verification Rounds: {result.verification_rounds}")
    print(f"  LLM Calls: {result.total_llm_calls}")
    print(f"  Tool Calls: {result.total_tool_calls}")
    print(f"  Cost: ${result.estimated_cost_usd:.4f}")
    print(f"  Duration: {result.duration_seconds:.1f}s")
    print(f"  Status: {result.final_status}")

    # Basic assertions
    assert result.scenario_id == "oom_after_deploy"
    assert result.root_cause_score in ["exact", "partial", "wrong"]
    assert isinstance(result.remediation_acceptable, bool)
    assert result.verification_rounds >= 0
    assert result.estimated_cost_usd >= 0

    print("\n✅ Single scenario test passed!")

    return result


def test_eval_rubric_scoring():
    """Test evaluation rubric scoring functions."""
    print("\n" + "=" * 80)
    print("TESTING: Eval Rubric Scoring")
    print("=" * 80 + "\n")

    from evals.rubric import (
        score_root_cause_identification,
        score_remediation_acceptability
    )

    # Test exact match
    score, reasoning = score_root_cause_identification(
        hypothesis="Memory limits were lowered from 2Gi to 512Mi",
        ground_truth="Memory limits were lowered from 2Gi to 512Mi",
        ground_truth_keywords=["memory", "limit", "lowered"]
    )
    print(f"Exact match test: {score} - {reasoning}")
    assert score == "exact", f"Should be exact match, got {score}"

    # Test partial match
    score, reasoning = score_root_cause_identification(
        hypothesis="The memory limit change in deployment revision 3 caused OOM",
        ground_truth="Memory limits were lowered from 2Gi to 512Mi",
        ground_truth_keywords=["memory", "limit", "deployment"]
    )
    print(f"Partial match test: {score} - {reasoning}")
    assert score in ["exact", "partial"], f"Should be partial or exact match, got {score}"

    # Test wrong match
    score, reasoning = score_root_cause_identification(
        hypothesis="The issue is caused by network latency",
        ground_truth="Memory limits were lowered from 2Gi to 512Mi",
        ground_truth_keywords=["memory", "limit", "lowered"]
    )
    print(f"Wrong match test: {score} - {reasoning}")
    assert score == "wrong", f"Should be wrong, got {score}"

    # Test acceptable remediation
    acceptable, reasoning = score_remediation_acceptability(
        action_type="rollback",
        acceptable_actions=["rollback", "config_change"]
    )
    print(f"\nAcceptable remediation test: {acceptable} - {reasoning}")
    assert acceptable == True, "Rollback should be acceptable"

    # Test unacceptable remediation
    acceptable, reasoning = score_remediation_acceptability(
        action_type="restart",
        acceptable_actions=["rollback", "config_change"]
    )
    print(f"Unacceptable remediation test: {acceptable} - {reasoning}")
    assert acceptable == False, "Restart should not be acceptable"

    print("\n✅ Rubric scoring test passed!")


def test_eval_report_generation():
    """Test evaluation report generation."""
    print("\n" + "=" * 80)
    print("TESTING: Eval Report Generation")
    print("=" * 80 + "\n")

    from evals.rubric import EvalResult, EvalScenario, format_eval_report

    # Create mock results
    scenario = EvalScenario(
        scenario_id="test_001",
        name="Test Scenario",
        description="Test description",
        ground_truth_root_cause="Test root cause",
        ground_truth_root_cause_keywords=["test"],
        acceptable_remediations=["rollback"],
        expected_verification_rounds=1,
        max_acceptable_rounds=3,
        difficulty="easy",
        incident_type="test"
    )

    result = EvalResult(
        scenario_id="test_001",
        root_cause_score="exact",
        root_cause_reasoning="Perfect match",
        remediation_acceptable=True,
        remediation_reasoning="Rollback is acceptable",
        verification_rounds=1,
        total_llm_calls=2,
        total_tool_calls=5,
        estimated_cost_usd=0.006,
        final_status="completed",
        escalated=False,
        duration_seconds=12.5
    )

    # Generate report
    report = format_eval_report([result], {"test_001": scenario})

    print("Generated Report Preview:")
    print(report[:500])
    print("...")

    # Verify report contains key sections
    assert "# Incident Response Agent - Evaluation Report" in report
    assert "## Summary" in report
    assert "## Per-Scenario Results" in report
    assert "Test Scenario" in report

    print("\n✅ Report generation test passed!")


def test_pass_rate_calculation():
    """Test pass rate calculation from results."""
    print("\n" + "=" * 80)
    print("TESTING: Pass Rate Calculation")
    print("=" * 80 + "\n")

    from evals.rubric import EvalResult

    # Create mock results
    results = [
        EvalResult(
            scenario_id="s1",
            root_cause_score="exact",
            root_cause_reasoning="",
            remediation_acceptable=True,
            remediation_reasoning="",
            verification_rounds=1,
            total_llm_calls=2,
            total_tool_calls=5,
            estimated_cost_usd=0.005,
            final_status="completed",
            escalated=False,
            duration_seconds=10.0
        ),
        EvalResult(
            scenario_id="s2",
            root_cause_score="partial",
            root_cause_reasoning="",
            remediation_acceptable=True,
            remediation_reasoning="",
            verification_rounds=2,
            total_llm_calls=3,
            total_tool_calls=7,
            estimated_cost_usd=0.009,
            final_status="completed",
            escalated=False,
            duration_seconds=15.0
        ),
        EvalResult(
            scenario_id="s3",
            root_cause_score="wrong",
            root_cause_reasoning="",
            remediation_acceptable=False,
            remediation_reasoning="",
            verification_rounds=3,
            total_llm_calls=4,
            total_tool_calls=10,
            estimated_cost_usd=0.012,
            final_status="escalated",
            escalated=True,
            duration_seconds=20.0
        )
    ]

    metrics = calculate_pass_rate(results)

    print(f"Calculated Metrics:")
    print(f"  Total: {metrics['total_scenarios']}")
    print(f"  Exact: {metrics['root_cause_exact']:.1%}")
    print(f"  Partial+: {metrics['root_cause_partial_or_better']:.1%}")
    print(f"  Remediation: {metrics['remediation_acceptable']:.1%}")
    print(f"  Avg Rounds: {metrics['avg_verification_rounds']:.1f}")
    print(f"  Avg Cost: ${metrics['avg_cost_usd']:.4f}")
    print(f"  Escalation: {metrics['escalation_rate']:.1%}")

    # Verify calculations
    assert metrics['total_scenarios'] == 3
    assert metrics['root_cause_exact'] == 1/3  # 1 exact out of 3
    assert metrics['root_cause_partial_or_better'] == 2/3  # 2 (exact + partial) out of 3
    assert metrics['remediation_acceptable'] == 2/3  # 2 acceptable out of 3
    assert metrics['avg_verification_rounds'] == 2.0  # (1+2+3)/3
    assert metrics['escalation_rate'] == 1/3  # 1 escalated out of 3

    print("\n✅ Pass rate calculation test passed!")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("RUNNING EVAL HARNESS TEST SUITE")
    print("=" * 80)

    # Run all tests
    test_eval_rubric_scoring()
    test_pass_rate_calculation()
    test_eval_report_generation()
    test_eval_runner_single_scenario()

    print("\n" + "=" * 80)
    print("ALL EVAL HARNESS TESTS PASSED!")
    print("=" * 80 + "\n")
