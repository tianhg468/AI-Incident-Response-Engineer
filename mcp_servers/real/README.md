# Real MCP Server Integration

This directory contains the integration layer for connecting to real MCP servers in live mode. When `MODE=live`, the agent connects to actual Kubernetes clusters, GitHub repositories, Slack workspaces, and observability platforms instead of using fixture-based mocks.

## Architecture

```
┌─────────────────┐
│  Agent Code     │  (completely agnostic to mode)
└────────┬────────┘
         │
    ┌────▼─────┐
    │ Registry │  (routes based on MODE env var)
    └────┬─────┘
         │
    ┌────▼────────────────────┐
    │  MODE=eval  │  MODE=live│
    ├─────────────┼───────────┤
    │ Mock        │ Real      │
    │ Servers     │ Servers   │
    │ (fixtures)  │ (stdio)   │
    └─────────────┴───────────┘
```

## How It Works

### Real MCP Server Client

The `RealMCPServerClient` class wraps an MCP server process and communicates with it via stdio using JSON-RPC:

1. **Server Start**: Spawns the MCP server as a subprocess on first use
2. **Communication**: Sends JSON-RPC requests over stdin, reads responses from stdout
3. **Tool Calls**: Translates agent tool calls to MCP protocol requests
4. **Lifecycle**: Manages server process lifecycle (start, shutdown, cleanup)

### Configuration

Each MCP server requires configuration via environment variables. The `config.py` module reads these and constructs server configurations:

```python
from mcp_servers.real import get_all_server_configs

# Reads from environment and returns configs for all configured servers
configs = get_all_server_configs()
```

## Required MCP Servers

To use live mode, you need to set up the following MCP servers:

### 1. Kubernetes MCP Server

**Purpose**: Pod status, logs, events, deployments

**Environment Variables**:
```bash
MCP_K8S_SERVER=/path/to/kubernetes-mcp-server
KUBECONFIG=~/.kube/config  # Optional
K8S_NAMESPACE=default      # Optional
```

**Expected Tools**:
- `k8s_get_pod_status` - Get pod status by label selector
- `k8s_get_pod_logs` - Get logs from a pod
- `k8s_get_events` - Get Kubernetes events
- `k8s_get_deployments` - Get deployment history
- `k8s_describe_pod` - Describe pod details

**Example Server Implementation**:
```python
# kubernetes_mcp_server.py
from mcp import Server
from kubernetes import client, config

server = Server("kubernetes")

@server.tool()
async def k8s_get_pod_status(namespace: str = "default", label_selector: str = None):
    config.load_kube_config()
    v1 = client.CoreV1Api()
    pods = v1.list_namespaced_pod(namespace=namespace, label_selector=label_selector)
    # ... return pod status
```

**Available Implementations**:
- Community MCP servers: Check [MCP servers directory](https://github.com/modelcontextprotocol/servers)
- Build your own using [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)

### 2. GitHub MCP Server

**Purpose**: Commits, PRs, diffs, file content

**Environment Variables**:
```bash
MCP_GITHUB_SERVER=/path/to/github-mcp-server
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your_org  # Optional
```

**Expected Tools**:
- `github_get_recent_commits` - Get recent commits for a repo
- `github_get_recent_prs` - Get recent pull requests
- `github_get_pr_diff` - Get diff for a PR
- `github_get_commit_diff` - Get diff for a commit
- `github_get_file_content` - Get file content at a commit

**Example Setup**:
```bash
# Install GitHub MCP server (example - check actual package name)
npm install -g @modelcontextprotocol/server-github

# Or use Python implementation
pip install mcp-server-github

# Set path
export MCP_GITHUB_SERVER=$(which mcp-server-github)
```

### 3. Slack MCP Server

**Purpose**: Messages, approvals, notifications

**Environment Variables**:
```bash
MCP_SLACK_SERVER=/path/to/slack-mcp-server
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=#incidents  # Optional default channel
```

**Expected Tools**:
- `slack_post_message` - Post a message to a channel
- `slack_post_approval_request` - Post approval request with buttons
- `slack_get_approval_status` - Check status of approval request
- `slack_update_message` - Update an existing message

**Slack App Setup**:
1. Create a Slack app at https://api.slack.com/apps
2. Add Bot Token Scopes: `chat:write`, `chat:write.public`, `users:read`
3. Install app to workspace
4. Copy Bot User OAuth Token

### 4. Observability MCP Server

**Purpose**: Metrics, alerts, service health

**Supported Providers**: Grafana, Datadog, Prometheus

**Environment Variables**:
```bash
MCP_OBSERVABILITY_SERVER=/path/to/observability-mcp-server
OBSERVABILITY_PROVIDER=grafana  # or datadog, prometheus

# For Grafana
GRAFANA_URL=http://localhost:3000
GRAFANA_API_KEY=your_api_key

# For Datadog
DATADOG_API_KEY=your_api_key
DATADOG_APP_KEY=your_app_key

# For Prometheus
PROMETHEUS_URL=http://localhost:9090
```

**Expected Tools**:
- `obs_query_metric` - Query a metric by name/query
- `obs_get_active_alerts` - Get currently firing alerts
- `obs_get_service_health` - Get service health metrics
- `obs_get_alert_history` - Get alert history for a service
- `obs_query_logs` - Query logs (if supported)

### 5. Runbook Correlator (Custom)

**Purpose**: Runbook search, deploy correlation, similar incidents

**Environment Variables**:
```bash
MCP_RUNBOOK_SERVER=/path/to/runbook_correlator/server.py
```

**Note**: This server is included in the repository at `mcp_servers/runbook_correlator/` and is automatically configured if not specified.

## Quick Start

### 1. Install MCP Servers

```bash
# Example: Install community MCP servers
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-slack

# Or build your own (see examples above)
```

### 2. Configure Environment

```bash
# Copy example config
cp .env.example .env

# Edit .env with your server paths and credentials
vim .env
```

Example `.env` for live mode:
```bash
# Mode
MODE=live

# Kubernetes
MCP_K8S_SERVER=/usr/local/bin/kubernetes-mcp-server
KUBECONFIG=~/.kube/config
K8S_NAMESPACE=production

# GitHub
MCP_GITHUB_SERVER=/usr/local/bin/github-mcp-server
GITHUB_TOKEN=ghp_your_token_here
GITHUB_ORG=your_company

# Slack
MCP_SLACK_SERVER=/usr/local/bin/slack-mcp-server
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_CHANNEL=#incidents

# Observability
MCP_OBSERVABILITY_SERVER=/usr/local/bin/grafana-mcp-server
OBSERVABILITY_PROVIDER=grafana
GRAFANA_URL=https://grafana.your-company.com
GRAFANA_API_KEY=your_api_key
```

### 3. Test Live Mode

```bash
# Set environment
export MODE=live

# Test MCP server connections
python -c "from mcp_servers.registry import get_mcp_server; registry = get_mcp_server(); print('Servers:', list(registry._servers.keys()))"

# Run an investigation
python -m agent.graph
```

## Building Custom MCP Servers

If you can't find an existing MCP server for your tool, you can build one using the MCP SDK:

### Python Example

```python
# my_mcp_server.py
from mcp import Server
import asyncio

server = Server("my-service")

@server.tool()
async def my_tool(param1: str, param2: int = 10):
    """Tool description for LLM."""
    # Your tool implementation
    return {"result": f"Processed {param1} with {param2}"}

async def main():
    async with server:
        await server.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### TypeScript/Node Example

```typescript
// my-mcp-server.ts
import { Server } from "@modelcontextprotocol/sdk";

const server = new Server({
  name: "my-service",
  version: "1.0.0"
});

server.setRequestHandler("tools/call", async (request) => {
  if (request.params.name === "my_tool") {
    // Your tool implementation
    return { result: "..." };
  }
});

server.listen();
```

## Troubleshooting

### Server Not Starting

**Error**: `Failed to start MCP server: [Errno 2] No such file or directory`

**Solution**: Check that `MCP_*_SERVER` path is correct and the file is executable.

```bash
# Make server executable
chmod +x /path/to/server

# Test manually
/path/to/server  # Should start and wait for JSON-RPC input
```

### Connection Timeout

**Error**: `MCP server communication error: Server closed connection`

**Solution**: Server may have crashed. Check stderr logs:

```python
# Enable verbose logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check server stderr
# Look in process logs for error messages
```

### Missing Tools

**Error**: `Unknown tool: k8s_get_pod_status`

**Solution**: Server doesn't implement expected tools. List available tools:

```python
from mcp_servers.registry import get_mcp_server

registry = get_mcp_server()
tools = registry.list_tools("kubernetes")
print("Available tools:", [t['name'] for t in tools])
```

### Authentication Errors

**Error**: `401 Unauthorized` or `403 Forbidden`

**Solution**: Check API tokens/credentials:

```bash
# Kubernetes
kubectl get pods  # Test kubeconfig works

# GitHub
curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

# Slack
curl -H "Authorization: Bearer $SLACK_BOT_TOKEN" https://slack.com/api/auth.test
```

## Security Considerations

### Credentials

- **Never commit tokens/secrets** to version control
- Use `.env` file (gitignored) or environment variables
- Consider using secret management systems (Vault, AWS Secrets Manager)

### Network Access

- MCP servers run locally but may access remote APIs
- Ensure network policies allow required connections
- Use TLS for remote connections

### Permissions

- Follow principle of least privilege
- Kubernetes: Use read-only service accounts for observation tools
- GitHub: Use personal access tokens with minimal scopes
- Slack: Grant only necessary bot permissions

## Testing Live Mode

Before using in production, test each MCP server individually:

```bash
# Test Kubernetes server
python -c "from mcp_servers.real import get_kubernetes_server_config; config = get_kubernetes_server_config(); print(config)"

# Test tool calls
python -c "
from mcp_servers.registry import get_mcp_server
registry = get_mcp_server(mode='live')
result = registry.call_tool('kubernetes', 'k8s_get_pod_status', {'namespace': 'default'})
print(result)
"
```

## Fallback Strategy

If some servers are unavailable, the agent will still work with available servers:

```python
# Registry gracefully handles missing servers
# Logs warnings but continues with available servers

# Check which servers are available
registry = get_mcp_server()
print("Available servers:", list(registry._servers.keys()))
```

## Performance Considerations

- **Server Startup**: First call starts the server process (~1-2s overhead)
- **Caching**: Tool lists are cached after first fetch
- **Connection Pooling**: Servers maintain persistent connections
- **Cleanup**: Servers are shutdown gracefully on exit

## Next Steps

1. Install/build required MCP servers for your infrastructure
2. Configure environment variables in `.env`
3. Test each server individually
4. Run full investigation in live mode
5. Monitor for errors and tune configurations

## Resources

- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
- [Community MCP Servers](https://github.com/modelcontextprotocol/servers)
- [MCP Protocol Specification](https://modelcontextprotocol.io)
