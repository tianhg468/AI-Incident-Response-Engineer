# Recovery Proposal Prompt Template

**Version:** v1.0

## Task

Draft a remediation proposal for the confirmed root cause.

## Confirmed Root Cause

{confirmed_hypothesis}

## Context

**Incident:** {incident_summary}

**Evidence:** {evidence_summary}

**Runbook Recommendations:** {runbook_recommendations}

## Instructions

Propose a remediation action that:
1. Addresses the confirmed root cause
2. Has minimal blast radius
3. Can be rolled back if needed
4. Is specific and actionable

Provide:
- **Action Type**: rollback | scale | restart | config_change | other
- **Description**: What action to take and why
- **Expected Effect**: What should happen after execution
- **Blast Radius**: Impact assessment (which services/pods affected)
- **Commands**: Exact commands or API calls to execute
- **Dry-run**: If possible, preview of what would happen

Consider:
- Can this be done with zero downtime?
- What are the risks?
- Do we need to notify anyone first?
- Is there a runbook for this?

Format as JSON:
```json
{
  "action_type": "...",
  "description": "...",
  "expected_effect": "...",
  "blast_radius": "...",
  "commands": ["...", "..."],
  "dry_run_output": "..."
}
```
