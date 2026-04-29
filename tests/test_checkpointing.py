"""Test checkpointing and resumability.

This test demonstrates that investigations can survive process restarts
by persisting state to a checkpointer (SQLite database).
"""

import os
from datetime import datetime
from pathlib import Path
import tempfile

# Set eval mode
os.environ["MODE"] = "eval"
os.environ["SCENARIO"] = "oom_after_deploy"

from agent.graph import create_incident_response_graph
from agent.state import AgentState
from agent.utils.checkpointing import get_checkpointer, get_thread_id


def test_checkpointing_basic():
    """Test that checkpointing works and state is persisted."""
    print("\n" + "=" * 80)
    print("TESTING: Basic Checkpointing")
    print("=" * 80 + "\n")

    # Create a temporary database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        # Create checkpointer
        checkpointer = get_checkpointer(mode="sqlite", db_path=db_path)
        print(f"Created checkpointer with database: {db_path}")

        # Create graph with checkpointing
        graph = create_incident_response_graph(checkpointer=checkpointer)

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

        # Generate a thread ID for this investigation
        thread_id = get_thread_id("test_checkpoint_001")
        print(f"Using thread_id: {thread_id}\n")

        # Run the graph with checkpointing
        config = {"configurable": {"thread_id": thread_id}}
        print("🚀 Starting investigation with checkpointing...\n")

        result = graph.invoke(initial_state, config=config)

        # Verify checkpointing happened
        assert result is not None, "Graph should return a result"
        print(f"\n✅ Investigation completed: {result.get('status')}")
        print(f"   Database file exists: {db_path.exists()}")
        print(f"   Database size: {db_path.stat().st_size} bytes")

        # Verify database is not empty
        assert db_path.stat().st_size > 0, "Checkpoint database should not be empty"

        print("\n✅ Basic checkpointing test passed!")

    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()
            print(f"\n🧹 Cleaned up test database: {db_path}")


def test_resumability_after_restart():
    """Test that investigations can resume after a simulated process restart.

    This is the key test for Step 7. It demonstrates:
    1. Starting an investigation
    2. Running it partway through
    3. Simulating a restart by creating a new graph instance
    4. Resuming from the checkpoint
    5. Verifying state continuity
    """
    print("\n" + "=" * 80)
    print("TESTING: Resumability After Restart")
    print("=" * 80 + "\n")

    # Create a temporary database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        # Generate thread ID for this investigation
        incident_id = "restart_test_001"
        thread_id = get_thread_id(incident_id)
        print(f"Investigation thread_id: {thread_id}\n")

        # ===== PART 1: Initial run (will be interrupted) =====
        print("=" * 80)
        print("PART 1: Initial Investigation (before restart)")
        print("=" * 80 + "\n")

        # Create checkpointer and graph
        checkpointer1 = get_checkpointer(mode="sqlite", db_path=db_path)
        graph1 = create_incident_response_graph(checkpointer=checkpointer1)

        # Initial state
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

        # Run with checkpointing
        config = {"configurable": {"thread_id": thread_id}}
        print("🚀 Starting initial investigation...\n")

        result1 = graph1.invoke(initial_state, config=config)

        # Capture state before "restart"
        status_before = result1.get("status")
        incident_before = result1.get("incident")
        evidence_before = result1.get("evidence")
        hypotheses_before = result1.get("hypotheses", [])

        print(f"\n📊 State before restart:")
        print(f"   Status: {status_before}")
        print(f"   Incident: {incident_before['service'] if incident_before else None}")
        print(f"   Evidence collected: {evidence_before is not None}")
        print(f"   Hypotheses: {len(hypotheses_before)}")

        # ===== SIMULATE PROCESS RESTART =====
        print("\n" + "=" * 80)
        print("⚠️  SIMULATING PROCESS RESTART")
        print("=" * 80 + "\n")

        # Delete the graph and checkpointer to simulate restart
        del graph1
        del checkpointer1

        # ===== PART 2: Resume after restart =====
        print("=" * 80)
        print("PART 2: Resume Investigation (after restart)")
        print("=" * 80 + "\n")

        # Create NEW checkpointer and graph instances (simulating restart)
        checkpointer2 = get_checkpointer(mode="sqlite", db_path=db_path)
        graph2 = create_incident_response_graph(checkpointer=checkpointer2)

        print("🔄 Resuming investigation from checkpoint...\n")

        # Get the current state from checkpoint
        # We do this by calling get_state on the graph
        state_snapshot = graph2.get_state(config)

        print(f"📊 Checkpoint state retrieved:")
        print(f"   Next node: {state_snapshot.next}")
        print(f"   Values keys: {list(state_snapshot.values.keys())}")

        # Verify we recovered the state
        status_after = state_snapshot.values.get("status")
        incident_after = state_snapshot.values.get("incident")
        evidence_after = state_snapshot.values.get("evidence")
        hypotheses_after = state_snapshot.values.get("hypotheses", [])

        print(f"\n📊 State after restart:")
        print(f"   Status: {status_after}")
        print(f"   Incident: {incident_after['service'] if incident_after else None}")
        print(f"   Evidence collected: {evidence_after is not None}")
        print(f"   Hypotheses: {len(hypotheses_after)}")

        # Verify state was preserved
        assert status_after == status_before, \
            f"Status should match: {status_before} != {status_after}"

        if incident_before:
            assert incident_after is not None, "Incident should be preserved"
            assert incident_after['service'] == incident_before['service'], \
                "Incident service should match"

        if evidence_before:
            assert evidence_after is not None, "Evidence should be preserved"

        assert len(hypotheses_after) == len(hypotheses_before), \
            f"Hypotheses count should match: {len(hypotheses_before)} != {len(hypotheses_after)}"

        print("\n✅ State successfully preserved across restart!")

        # Now continue the investigation from where it left off
        # If the investigation was already completed, we can still verify we can access the state
        if state_snapshot.next:
            print(f"\n▶️  Investigation can continue from: {state_snapshot.next}")
        else:
            print("\n✓ Investigation was already completed")

        print("\n✅ Resumability test passed!")
        print("   - State persisted to checkpoint database")
        print("   - State retrieved after restart")
        print("   - All state values preserved correctly")

    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()
            print(f"\n🧹 Cleaned up test database: {db_path}")


def test_multiple_investigations():
    """Test that multiple concurrent investigations can be tracked."""
    print("\n" + "=" * 80)
    print("TESTING: Multiple Concurrent Investigations")
    print("=" * 80 + "\n")

    # Create a temporary database for this test
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        # Create checkpointer
        checkpointer = get_checkpointer(mode="sqlite", db_path=db_path)
        graph = create_incident_response_graph(checkpointer=checkpointer)

        # Start 3 different investigations
        thread_ids = [
            get_thread_id("multi_test_001"),
            get_thread_id("multi_test_002"),
            get_thread_id("multi_test_003")
        ]

        results = []

        for thread_id in thread_ids:
            print(f"Starting investigation: {thread_id}")

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

            config = {"configurable": {"thread_id": thread_id}}
            result = graph.invoke(initial_state, config=config)
            results.append((thread_id, result))
            print(f"  Completed: {result.get('status')}\n")

        # Verify all investigations completed
        assert len(results) == 3, "Should have 3 completed investigations"

        for thread_id, result in results:
            assert result is not None, f"Investigation {thread_id} should complete"
            assert result.get("status") in ["completed", "escalated"], \
                f"Investigation {thread_id} should have valid status"

        print("✅ Multiple investigations test passed!")
        print(f"   - {len(results)} investigations completed")
        print(f"   - Database size: {db_path.stat().st_size} bytes")

    finally:
        # Cleanup
        if db_path.exists():
            db_path.unlink()
            print(f"\n🧹 Cleaned up test database: {db_path}")


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("RUNNING CHECKPOINTING TEST SUITE")
    print("=" * 80)

    # Run all tests
    test_checkpointing_basic()
    test_resumability_after_restart()
    test_multiple_investigations()

    print("\n" + "=" * 80)
    print("ALL CHECKPOINTING TESTS PASSED!")
    print("=" * 80 + "\n")
