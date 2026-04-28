# Mock MCP Servers

Fixture-based mock implementations of MCP servers for deterministic evaluation and testing.

## Overview

The mock MCP servers implement the same tool interfaces as real MCP servers but serve canned fixture data from disk instead of making real API calls. This enables:

1. **Deterministic evaluation** - Same fixtures always produce same results
2. **Fast testing** - No network calls or external dependencies
3. **Reproducible scenarios** - Hand-crafted incident scenarios with known outcomes
4. **Offline development** - No need for live Kubernetes clusters, GitHub, etc.

## Architecture Decision

**Key insight**: The agent code is completely agnostic to whether it's talking to real or mock servers. Only the MCP server URLs/implementations change between modes, controlled by the `MODE` environment variable.

```python
# Agent code - works in both modes
from mcp_servers.registry import get_mcp_server

registry = get_mcp_server()  # MODE env var determines real vs mock
result = registry.call_tool("kubernetes", "k8s_get_pod_status", {...})
```

This dual-mode architecture is resume-worthy because it demonstrates:
- Understanding of fixture-based testing for AI agents
- Proper abstraction and interface design
- Evaluation infrastructure that scales

## Mock Servers

### Kubernetes Mock (`MockKubernetesMCPServer`)

**Tools:**
- `k8s_get_pod_status` - Pod status and health
- `k8s_get_pod_logs` - Pod logs
- `k8s_get_events` - Kubernetes events
- `k8s_get_deployments` - Deployment history and state
- `k8s_describe_pod` - Detailed pod information

**Fixtures:**
- `pods.json` - Pod definitions and status
- `logs.json` - Container logs
- `events.json` - Kubernetes events
- `deployments.json` - Deployment history with rollout details

### GitHub Mock (`MockGitHubMCPServer`)

**Tools:**
- `github_get_recent_commits` - Recent commits with filters
- `github_get_recent_prs` - Pull requests
- `github_get_pr_diff` - PR diffs
- `github_get_commit_diff` - Commit diffs
- `github_get_file_content` - File content at specific commits

**Fixtures:**
- `commits.json` - Commit history
- `prs.json` - Pull request data
- `diffs.json` - Code diffs for PRs and commits

### Slack Mock (`MockSlackMCPServer`)

**Tools:**
- `slack_post_message` - Post messages to channels
- `slack_post_approval_request` - Request human approval
- `slack_get_approval_status` - Check approval status
- `slack_update_message` - Update existing messages

**Fixtures:**
- `config.json` - Slack behavior configuration
  - `auto_approve`: Auto-approve requests in eval mode
  - `approval_delay_seconds`: Simulated approval delay
  - `default_channel`: Default channel for posts

**Special features:**
- In-memory tracking of posted messages and approvals
- `simulate_approval()` helper for testing
- Auto-approval mode for automated eval runs

### Observability Mock (`MockObservabilityMCPServer`)

**Tools:**
- `obs_query_metric` - Query metrics (Prometheus-like)
- `obs_query_range` - Time-series range queries
- `obs_get_alerts` - Active alerts
- `obs_get_metric_labels` - Available metric labels
- `obs_get_service_health` - Aggregated service health

**Fixtures:**
- `metrics.json` - Time-series metrics data
- `alerts.json` - Active alerts (optional)

## Usage

### Running in Eval Mode

```bash
# Set environment variables
export MODE=eval
export SCENARIO=oom_after_deploy

# Run agent
python -m agent.graph
```

### Using in Tests

```python
from mcp_servers.registry import MCPServerRegistry

# Create registry for specific scenario
registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

# Call tools
pods = registry.call_tool("kubernetes", "k8s_get_pod_status", {
    "namespace": "default",
    "label_selector": "app=payment-service"
})

commits = registry.call_tool("github", "github_get_recent_commits", {
    "repo": "myorg/payment-service",
    "limit": 10
})
```

### Creating New Scenarios

1. Create scenario directory:
```bash
mkdir -p fixtures/scenarios/my_scenario/{kubernetes,github,slack,observability}
```

2. Create `manifest.yml` with metadata:
```yaml
name: "My Scenario"
description: "..."
ground_truth:
  root_cause: "..."
  acceptable_remediations: [...]
incident:
  service: "my-service"
  severity: "high"
  ...
```

3. Create fixture files following the schema (see existing scenarios for examples)

4. Run tests:
```bash
SCENARIO=my_scenario pytest tests/test_mock_mcp_servers.py
```

## Fixture Loading

The `FixtureLoader` class handles loading fixtures with fallback logic:

1. First tries scenario-specific fixture: `fixtures/scenarios/{scenario}/{service}/{file}.json`
2. Falls back to shared fixture: `fixtures/shared/{service}/{file}.json`
3. Raises `FileNotFoundError` if neither exists

This allows scenarios to override only the fixtures they need while reusing shared fixtures for common data.

## Testing

Run tests:
```bash
pytest tests/test_mock_mcp_servers.py -v
```

Tests verify:
- Fixtures load correctly
- Tool interfaces match expected schemas
- Filtering and querying work as expected
- Mode switching works properly

## Implementation Notes

### Why Not Use Real MCP SDK?

For mock servers, we implement the tool interface directly rather than using the full MCP SDK because:

1. **Simpler** - No need for stdio/HTTP transport in eval mode
2. **Faster** - Direct Python function calls, no serialization
3. **Easier to debug** - Stack traces show actual fixture loading

In live mode, we would use the real MCP SDK to connect to actual servers.

### Thread Safety

Mock servers are **not thread-safe** by design. Each eval run should use its own registry instance.

### Fixture Size

Keep fixtures reasonably small (< 100KB each) for fast loading. Use sampling for large datasets.

## Future Enhancements

- [ ] Fixture validation against JSON schemas
- [ ] Fixture generation tools from real API responses
- [ ] Parameterized fixtures (e.g., time-shifted scenarios)
- [ ] Fixture compression for large scenarios
- [ ] Live mode implementation with real MCP SDK
