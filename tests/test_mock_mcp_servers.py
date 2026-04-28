"""Test mock MCP servers with fixture data."""

import os
from mcp_servers.registry import MCPServerRegistry


def test_mock_kubernetes_server():
    """Test Kubernetes mock server loads fixtures correctly."""
    # Set environment for test scenario
    os.environ["MODE"] = "eval"
    os.environ["SCENARIO"] = "oom_after_deploy"

    registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

    # Test pod status query
    result = registry.call_tool(
        "kubernetes",
        "k8s_get_pod_status",
        {"namespace": "default", "label_selector": "app=payment-service"}
    )

    assert "pods" in result
    assert len(result["pods"]) > 0

    # Check that we have the OOM-killed pods
    pod_names = [p["metadata"]["name"] for p in result["pods"]]
    assert "payment-service-7d9f8b6c4-xk2p9" in pod_names

    # Test events query
    events_result = registry.call_tool(
        "kubernetes",
        "k8s_get_events",
        {"namespace": "default"}
    )

    assert "events" in events_result
    # Should have OOMKilled events
    oom_events = [e for e in events_result["events"] if e["reason"] == "OOMKilled"]
    assert len(oom_events) > 0

    print("✅ Kubernetes mock server test passed!")


def test_mock_github_server():
    """Test GitHub mock server loads fixtures correctly."""
    os.environ["MODE"] = "eval"
    os.environ["SCENARIO"] = "oom_after_deploy"

    registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

    # Test recent commits
    result = registry.call_tool(
        "github",
        "github_get_recent_commits",
        {"repo": "myorg/payment-service", "limit": 5}
    )

    assert "commits" in result
    assert len(result["commits"]) > 0

    # Should have the memory limit reduction commit
    commit_messages = [c["message"] for c in result["commits"]]
    assert any("memory" in msg.lower() for msg in commit_messages)

    # Test PR diff
    diff_result = registry.call_tool(
        "github",
        "github_get_pr_diff",
        {"repo": "myorg/payment-service", "pr_number": 456}
    )

    assert "diff" in diff_result
    # Diff should show memory limit changes
    assert "512Mi" in diff_result["diff"]
    assert "2Gi" in diff_result["diff"]

    print("✅ GitHub mock server test passed!")


def test_mock_slack_server():
    """Test Slack mock server behavior."""
    os.environ["MODE"] = "eval"
    os.environ["SCENARIO"] = "oom_after_deploy"

    registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

    # Test posting a message
    result = registry.call_tool(
        "slack",
        "slack_post_message",
        {
            "channel": "#incidents",
            "text": "Test incident notification"
        }
    )

    assert result["ok"] is True
    assert "message_id" in result

    # Test approval request
    approval_result = registry.call_tool(
        "slack",
        "slack_post_approval_request",
        {
            "title": "Rollback deployment",
            "description": "Rollback payment-service to v2.0.9"
        }
    )

    assert approval_result["ok"] is True
    assert "approval_id" in approval_result

    # In eval mode with auto_approve=true, should be auto-approved
    assert approval_result["status"] == "approved"

    print("✅ Slack mock server test passed!")


def test_mock_observability_server():
    """Test Observability mock server with metrics."""
    os.environ["MODE"] = "eval"
    os.environ["SCENARIO"] = "oom_after_deploy"

    registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")

    # Test metric query
    result = registry.call_tool(
        "observability",
        "obs_query_metric",
        {"query": "container_memory_usage_bytes"}
    )

    assert result["status"] == "success"
    assert "data" in result
    assert len(result["data"]["result"]) > 0

    # Test service health
    health_result = registry.call_tool(
        "observability",
        "obs_get_service_health",
        {"service": "payment-service", "time_window": "1h"}
    )

    assert health_result["status"] == "success"
    health_data = health_result["data"]
    assert "error_rate" in health_data
    assert "memory_usage" in health_data

    print("✅ Observability mock server test passed!")


def test_registry_mode_switching():
    """Test that registry correctly switches between modes."""
    # Test eval mode
    eval_registry = MCPServerRegistry(mode="eval", scenario="oom_after_deploy")
    assert eval_registry.get_mode() == "eval"
    assert eval_registry.get_scenario() == "oom_after_deploy"

    # Test that all servers are initialized
    all_tools = eval_registry.get_all_tools()
    assert "kubernetes" in all_tools
    assert "github" in all_tools
    assert "slack" in all_tools
    assert "observability" in all_tools

    print("✅ Registry mode switching test passed!")


if __name__ == "__main__":
    test_mock_kubernetes_server()
    test_mock_github_server()
    test_mock_slack_server()
    test_mock_observability_server()
    test_registry_mode_switching()
    print("\n🎉 All mock MCP server tests passed!")
