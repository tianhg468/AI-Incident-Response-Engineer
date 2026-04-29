# Evaluation Harness

Automated evaluation system for the AI Incident Response Engineer, providing deterministic testing against scripted incident scenarios with ground truth labels.

## Overview

The eval harness runs the agent against synthetic incident scenarios with known root causes and acceptable remediations, scoring performance on:
- **Root Cause Accuracy**: exact / partial / wrong
- **Remediation Acceptability**: yes / no
- **Verification Efficiency**: number of rounds required
- **Cost per Incident**: estimated LLM and tool call costs

## Architecture

```
evals/
├── scenarios/           # Scenario definitions (JSON)
│   ├── oom_after_deploy.json
│   ├── 5xx_spike_feature_flag.json
│   ├── dns_resolution_failure.json
│   ├── slow_query_missing_index.json
│   └── cascading_failure_timeout.json
├── rubric.py           # Scoring logic
├── runner.py           # Eval execution engine
└── README.md           # This file
```

## Scenario Definition Format

Each scenario is defined in a JSON file with:

```json
{
  "scenario_id": "oom_after_deploy",
  "name": "OOM After Deploy",
  "description": "Pods are OOMKilled after deployment lowered memory limits",

  "ground_truth_root_cause": "Memory limits were lowered from 2Gi to 512Mi",
  "ground_truth_root_cause_keywords": ["memory", "limit", "lowered", "512Mi"],

  "acceptable_remediations": ["rollback", "config_change"],

  "expected_verification_rounds": 1,
  "max_acceptable_rounds": 3,

  "difficulty": "easy",
  "incident_type": "oom"
}
```

## Scoring Rubric

### Root Cause Identification

- **Exact** (100%): Hypothesis matches ground truth or contains all key concepts
- **Partial** (50%): Hypothesis contains 40-70% of ground truth keywords
- **Wrong** (0%): Hypothesis does not match ground truth

Scoring uses keyword matching against `ground_truth_root_cause_keywords`:
- 70%+ keywords matched → Exact or Partial (high)
- 40-70% keywords matched → Partial (low)
- <40% keywords matched → Wrong

### Remediation Acceptability

Binary yes/no based on whether the proposed `action_type` is in the `acceptable_remediations` list.

Examples:
- OOM incident: `rollback`, `config_change` acceptable
- DNS incident: `rollback`, `config_change`, `restart` acceptable
- Feature flag incident: `config_change`, `rollback` acceptable

### Verification Efficiency

Scored based on number of verification rounds:
- **Excellent**: ≤ expected_verification_rounds
- **Good**: expected + 1
- **Acceptable**: ≤ max_acceptable_rounds
- **Poor**: > max_acceptable_rounds

### Cost Estimation

Rough cost calculation based on:
- LLM calls (diagnosis + verification rounds)
- Tool calls (evidence gathering, verification checks)
- Estimated tokens per call (default: 2000)
- Cost per million tokens (Claude Sonnet 3.5: $3/M)

Formula: `cost = (llm_calls * avg_tokens * $3) / 1M`

## Running Evaluations

### Run All Scenarios

```bash
cd /path/to/project
python -m evals.runner
```

This will:
1. Load all scenario definitions from `evals/scenarios/*.json`
2. Execute each scenario against the agent
3. Score results using the rubric
4. Generate a markdown report at `eval_report.md`

### Run Single Scenario

```bash
python -m evals.runner --scenario oom_after_deploy
```

### Custom Report Path

```bash
python -m evals.runner --report results/eval_$(date +%Y%m%d).md
```

### Verbose Logging

```bash
python -m evals.runner --verbose
```

## Example Output

```
================================================================================
INCIDENT RESPONSE AGENT - EVALUATION HARNESS
================================================================================

Loaded 5 scenarios

Running scenario: OOM After Deploy
  Root Cause: exact
  Remediation: Acceptable
  Rounds: 1

Running scenario: 5xx Spike from Feature Flag
  Root Cause: partial
  Remediation: Acceptable
  Rounds: 2

...

================================================================================
EVALUATION COMPLETE
================================================================================

Total Scenarios: 5
Root Cause Accuracy (Exact): 60.0%
Root Cause Accuracy (Partial+): 80.0%
Remediation Acceptable: 80.0%
Avg Verification Rounds: 1.8
Avg Cost: $0.0078
Escalation Rate: 20.0%

📊 Full report saved to: eval_report.md
```

## Eval Report Format

The generated report includes:

### Summary Table

| Metric | Score |
|--------|-------|
| **Total Scenarios** | 5 |
| **Root Cause Accuracy (Exact)** | 60.0% |
| **Root Cause Accuracy (Partial or Better)** | 80.0% |
| **Remediation Acceptability** | 80.0% |
| **Avg Verification Rounds** | 1.8 |
| **Avg Cost per Incident** | $0.0078 |
| **Escalation Rate** | 20.0% |

### Per-Scenario Results

For each scenario:
- Root cause score (EXACT/PARTIAL/WRONG) with reasoning
- Remediation acceptability (✅/❌) with reasoning
- Verification rounds
- Final status
- Cost
- Duration

## Adding New Scenarios

1. Create a new JSON file in `evals/scenarios/`
2. Follow the scenario definition format (see above)
3. Create corresponding fixture data in `fixtures/scenarios/{scenario_id}/`
   - `manifest.yml` - Incident metadata
   - `kubernetes/` - Pod status, logs, events, deployments
   - `github/` - Commits, PRs, diffs
   - `observability/` - Metrics, alerts
   - `slack/` - Messages (optional)

4. Run the eval harness to test the new scenario

## Current Scenarios

1. **oom_after_deploy** (Easy) - Memory limits lowered in deployment
2. **5xx_spike_feature_flag** (Medium) - Feature flag enabled causing errors
3. **dns_resolution_failure** (Hard) - CoreDNS config breaking DNS
4. **slow_query_missing_index** (Medium) - Database index dropped
5. **cascading_failure_timeout** (Hard) - Timeout increase causing cascade

## Target Metrics (Goals)

Based on SPEC.md requirements:

- Root Cause Accuracy (Exact): ≥ 60%
- Root Cause Accuracy (Partial+): ≥ 80%
- Remediation Acceptability: ≥ 75%
- Avg Verification Rounds: ≤ 2.5
- Avg Cost per Incident: ≤ $0.015
- Escalation Rate: ≤ 25%

## Integration with CI/CD

To run evals in CI:

```bash
# In CI pipeline
python -m evals.runner --report eval_results_$CI_BUILD_ID.md

# Check for regressions
python -m evals.check_regression --baseline baseline_scores.json --current eval_results.json
```

(Note: `check_regression.py` not yet implemented)

## Limitations

- Cost estimation is approximate (based on averages, not actual token counts)
- Keyword matching for root cause is simple (could use semantic similarity)
- Mock MCP servers return static fixtures (no dynamic behavior)
- No support for multi-turn approval scenarios yet
- Escalation scenarios treated as failures (but may be appropriate in some cases)

## Future Enhancements

- Expand to 15-25 scenarios (target from SPEC.md)
- Add semantic similarity scoring for root cause (embeddings + cosine similarity)
- Track token usage accurately via LangSmith or API callbacks
- Add scenario difficulty weighting to scores
- Support partial credit for remediation (e.g., "acceptable but not optimal")
- Generate trend charts tracking scores over time
- CI integration with pass/fail gates
- Regression detection against baseline scores
