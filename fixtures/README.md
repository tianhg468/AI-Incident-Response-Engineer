# Fixture Data for Mock MCP Servers

This directory contains fixture data used by mock MCP servers during evaluation and testing.

## Structure

```
fixtures/
├── scenarios/           # Per-scenario fixture sets (for evals)
│   ├── oom_after_deploy/
│   ├── 5xx_feature_flag/
│   ├── dns_failure/
│   └── ...
├── shared/              # Shared fixture data
│   ├── kubernetes/      # Pod templates, event types
│   ├── github/          # Common commit/PR structures
│   ├── slack/           # Message templates
│   └── observability/   # Metric templates
└── README.md
```

## Scenario Structure

Each scenario directory contains all the fixture data needed for a complete incident simulation:

```
scenario_name/
├── manifest.yml         # Scenario metadata (root cause, expected remediation)
├── kubernetes/
│   ├── pods.json       # Pod status at incident time
│   ├── events.json     # Kubernetes events
│   ├── logs.json       # Pod logs
│   └── deployments.json
├── github/
│   ├── commits.json    # Recent commits
│   ├── prs.json        # Recent PRs
│   └── diffs.json      # Code diffs
├── slack/
│   └── config.json     # Slack behavior (approval delay, etc.)
└── observability/
    └── metrics.json    # Time-series metrics data
```

## Manifest Schema

```yaml
name: "OOM after deploy"
description: "Memory limit lowered in recent deploy causing OOM kills"
ground_truth:
  root_cause: "Memory limit reduced from 2Gi to 512Mi in deployment"
  acceptable_remediations:
    - "rollback"
    - "scale_up_memory"
  verification_steps_expected: 2
incident:
  service: "payment-service"
  severity: "high"
  alert_type: "pod_crash_loop"
  time_window:
    start: "2024-01-15T10:00:00Z"
    end: "2024-01-15T10:30:00Z"
```

## Usage

Mock MCP servers load fixtures based on:
1. `MODE` env var (eval vs live)
2. `SCENARIO` env var (which scenario to load)

Example:
```bash
MODE=eval SCENARIO=oom_after_deploy python -m agent.graph
```
