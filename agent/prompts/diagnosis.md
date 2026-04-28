# Diagnosis Prompt Template

**Version:** v1.0

## Task

Analyze the incident evidence and generate 2-3 ranked hypotheses about the root cause.

## Evidence

**Incident Details:**
{incident_details}

**Logs:**
{logs_summary}

**Metrics:**
{metrics_summary}

**Recent Deploys:**
{deploys_summary}

**Similar Past Incidents:**
{past_incidents_summary}

**Relevant Runbooks:**
{runbooks_summary}

## Instructions

Generate 2-3 hypotheses ranked by likelihood. For each hypothesis, provide:

1. **Description**: Clear explanation of what you think went wrong
2. **Falsification Criterion**: An explicit test - "if X is true, this hypothesis is wrong"
3. **Supporting Evidence**: References to specific evidence that supports this hypothesis
4. **Verification Checks**: Specific checks to run to confirm or refute

Focus on:
- Correlation between deploy timing and incident onset
- Anomalies in metrics and logs
- Patterns from similar past incidents
- Runbook guidance

Format your response as JSON:
```json
[
  {
    "rank": 1,
    "description": "...",
    "falsification_criterion": "...",
    "supporting_evidence": ["...", "..."],
    "verification_checks": ["...", "..."]
  },
  ...
]
```
