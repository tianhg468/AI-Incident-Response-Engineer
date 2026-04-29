"""Evaluation harness runner for testing incident response agent."""

import os
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional
import json

from agent.graph import create_incident_response_graph
from agent.state import AgentState
from agent.utils.checkpointing import get_thread_id
from evals.rubric import (
    EvalScenario,
    EvalResult,
    score_root_cause_identification,
    score_remediation_acceptability,
    estimate_cost,
    calculate_pass_rate,
    format_eval_report
)

logger = logging.getLogger(__name__)


class EvalRunner:
    """Runner for executing evaluation scenarios."""

    def __init__(
        self,
        scenarios_dir: Optional[Path] = None,
        enable_checkpointing: bool = False
    ):
        """Initialize eval runner.

        Args:
            scenarios_dir: Directory containing scenario definitions
            enable_checkpointing: Whether to enable checkpointing (usually False for evals)
        """
        self.scenarios_dir = scenarios_dir or Path(__file__).parent / "scenarios"
        self.enable_checkpointing = enable_checkpointing
        self.scenarios: dict[str, EvalScenario] = {}
        self.results: list[EvalResult] = []

        # Load scenarios
        self._load_scenarios()

    def _load_scenarios(self):
        """Load scenario definitions from JSON files."""
        scenario_files = list(self.scenarios_dir.glob("*.json"))

        if not scenario_files:
            logger.warning(f"No scenario files found in {self.scenarios_dir}")
            return

        for scenario_file in scenario_files:
            try:
                with open(scenario_file, 'r') as f:
                    data = json.load(f)

                scenario = EvalScenario(
                    scenario_id=data["scenario_id"],
                    name=data["name"],
                    description=data["description"],
                    ground_truth_root_cause=data["ground_truth_root_cause"],
                    ground_truth_root_cause_keywords=data["ground_truth_root_cause_keywords"],
                    acceptable_remediations=data["acceptable_remediations"],
                    expected_verification_rounds=data.get("expected_verification_rounds", 1),
                    max_acceptable_rounds=data.get("max_acceptable_rounds", 3),
                    difficulty=data.get("difficulty", "medium"),
                    incident_type=data.get("incident_type", "unknown")
                )

                self.scenarios[scenario.scenario_id] = scenario
                logger.info(f"Loaded scenario: {scenario.name}")

            except Exception as e:
                logger.error(f"Failed to load scenario {scenario_file}: {e}")

    def run_scenario(self, scenario_id: str) -> EvalResult:
        """Run a single evaluation scenario.

        Args:
            scenario_id: Scenario ID to run

        Returns:
            EvalResult with scoring
        """
        scenario = self.scenarios.get(scenario_id)
        if not scenario:
            raise ValueError(f"Unknown scenario: {scenario_id}")

        logger.info(f"Running scenario: {scenario.name}")

        # Set environment for this scenario
        os.environ["MODE"] = "eval"
        os.environ["SCENARIO"] = scenario_id

        # Create graph
        graph = create_incident_response_graph(
            checkpointer=None,
            enable_checkpointing=self.enable_checkpointing
        )

        # Initialize state
        initial_state: AgentState = {
            "incident": None,
            "evidence": None,
            "hypotheses": [],
            "current_hypothesis_index": 0,
            "verification_results": [],
            "verification_round": 0,
            "recovery_proposal": None,
            "execution_result": None,
            "post_mortem": None,
            "status": "intake",
            "escalation_reason": None,
            "messages": [],
            "tool_calls": [],
            "started_at": datetime.now(),
            "completed_at": None
        }

        # Track timing
        start_time = time.time()

        # Run investigation
        try:
            result = graph.invoke(initial_state)
        except Exception as e:
            logger.error(f"Investigation failed: {e}", exc_info=True)
            # Return a failed result
            return EvalResult(
                scenario_id=scenario_id,
                root_cause_score="wrong",
                root_cause_reasoning=f"Investigation crashed: {str(e)}",
                remediation_acceptable=False,
                remediation_reasoning="No remediation proposed (crash)",
                verification_rounds=0,
                total_llm_calls=0,
                total_tool_calls=0,
                estimated_cost_usd=0.0,
                final_status="error",
                escalated=False,
                duration_seconds=time.time() - start_time
            )

        duration = time.time() - start_time

        # Extract results
        verification_results = result.get("verification_results", [])
        confirmed_hypothesis = None

        # Find confirmed hypothesis
        for vr in verification_results:
            if vr["status"] == "confirmed":
                confirmed_hypothesis = vr["hypothesis"]["description"]
                break

        # Score root cause
        root_cause_score, root_cause_reasoning = score_root_cause_identification(
            hypothesis=confirmed_hypothesis,
            ground_truth=scenario.ground_truth_root_cause,
            ground_truth_keywords=scenario.ground_truth_root_cause_keywords
        )

        # Score remediation
        recovery_proposal = result.get("recovery_proposal")
        action_type = recovery_proposal.get("action_type") if recovery_proposal else None

        remediation_acceptable, remediation_reasoning = score_remediation_acceptability(
            action_type=action_type,
            acceptable_actions=scenario.acceptable_remediations
        )

        # Count LLM and tool calls
        messages = result.get("messages", [])
        tool_calls = result.get("tool_calls", [])

        # Estimate LLM calls (diagnosis + verification rounds)
        verification_rounds = result.get("verification_round", 0)
        llm_calls = 1 + verification_rounds  # Diagnosis + each verification

        # Estimate cost
        cost = estimate_cost(
            llm_calls=llm_calls,
            tool_calls=len(tool_calls)
        )

        # Create eval result
        eval_result = EvalResult(
            scenario_id=scenario_id,
            root_cause_score=root_cause_score,
            root_cause_reasoning=root_cause_reasoning,
            remediation_acceptable=remediation_acceptable,
            remediation_reasoning=remediation_reasoning,
            verification_rounds=verification_rounds,
            total_llm_calls=llm_calls,
            total_tool_calls=len(tool_calls),
            estimated_cost_usd=cost,
            final_status=result.get("status", "unknown"),
            escalated=result.get("status") == "escalated",
            duration_seconds=duration
        )

        logger.info(f"Scenario complete: {scenario.name}")
        logger.info(f"  Root Cause: {root_cause_score}")
        logger.info(f"  Remediation: {'Acceptable' if remediation_acceptable else 'Not Acceptable'}")
        logger.info(f"  Rounds: {verification_rounds}")

        return eval_result

    def run_all_scenarios(self) -> list[EvalResult]:
        """Run all loaded scenarios.

        Returns:
            List of EvalResults
        """
        self.results = []

        for scenario_id in self.scenarios.keys():
            try:
                result = self.run_scenario(scenario_id)
                self.results.append(result)
            except Exception as e:
                logger.error(f"Failed to run scenario {scenario_id}: {e}")

        return self.results

    def generate_report(self, output_path: Optional[Path] = None) -> str:
        """Generate evaluation report.

        Args:
            output_path: Optional path to save report to

        Returns:
            Markdown report string
        """
        report = format_eval_report(self.results, self.scenarios)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report)
            logger.info(f"Report saved to: {output_path}")

        return report

    def get_summary(self) -> dict:
        """Get summary metrics from evaluation results.

        Returns:
            Dictionary with summary metrics
        """
        return calculate_pass_rate(self.results)


def main():
    """Run eval harness from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Run incident response agent evals")
    parser.add_argument(
        "--scenario",
        type=str,
        help="Run a specific scenario (default: run all)"
    )
    parser.add_argument(
        "--report",
        type=str,
        default="eval_report.md",
        help="Output report path (default: eval_report.md)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Create runner
    runner = EvalRunner()

    print("\n" + "=" * 80)
    print("INCIDENT RESPONSE AGENT - EVALUATION HARNESS")
    print("=" * 80 + "\n")

    print(f"Loaded {len(runner.scenarios)} scenarios\n")

    # Run scenarios
    if args.scenario:
        # Run single scenario
        result = runner.run_scenario(args.scenario)
        runner.results = [result]
    else:
        # Run all scenarios
        runner.run_all_scenarios()

    # Generate report
    report = runner.generate_report(output_path=Path(args.report))

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80 + "\n")

    # Print summary
    summary = runner.get_summary()
    print(f"Total Scenarios: {summary['total_scenarios']}")
    print(f"Root Cause Accuracy (Exact): {summary['root_cause_exact']:.1%}")
    print(f"Root Cause Accuracy (Partial+): {summary['root_cause_partial_or_better']:.1%}")
    print(f"Remediation Acceptable: {summary['remediation_acceptable']:.1%}")
    print(f"Avg Verification Rounds: {summary['avg_verification_rounds']:.1f}")
    print(f"Avg Cost: ${summary['avg_cost_usd']:.4f}")
    print(f"Escalation Rate: {summary['escalation_rate']:.1%}")

    print(f"\n📊 Full report saved to: {args.report}\n")


if __name__ == "__main__":
    main()
