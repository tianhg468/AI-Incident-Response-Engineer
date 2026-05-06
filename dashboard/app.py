"""Streamlit dashboard for AI Incident Response Engineer.

Displays active and historical investigations, metrics, and analytics.
"""

import streamlit as st
from pathlib import Path
from datetime import datetime
import os

from dashboard.checkpoint_reader import CheckpointReader
from dashboard.cluster_reader import get_live_investigation

# Page config
st.set_page_config(
    page_title="AI Incident Response - Dashboard",
    page_icon="🚨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize checkpoint reader
@st.cache_resource
def get_checkpoint_reader():
    """Get or create checkpoint reader."""
    db_path = Path(os.getenv("CHECKPOINT_DB_PATH", "./data/checkpoints.db"))
    return CheckpointReader(db_path)


def format_duration(started_at, completed_at):
    """Format duration between two timestamps."""
    if not started_at or not completed_at:
        return "In progress"

    try:
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        if isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at)

        duration = (completed_at - started_at).total_seconds()
        minutes = duration / 60

        if minutes < 1:
            return f"{duration:.0f}s"
        elif minutes < 60:
            return f"{minutes:.1f}m"
        else:
            hours = minutes / 60
            return f"{hours:.1f}h"

    except Exception:
        return "Unknown"


def render_overview():
    """Render overview page with statistics."""
    st.title("🚨 AI Incident Response Dashboard")
    st.markdown("Real-time view of investigation activity and metrics")

    reader = get_checkpoint_reader()
    stats = reader.get_statistics()

    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Total Investigations",
            stats["total_investigations"],
            help="Total number of investigations in the database"
        )

    with col2:
        st.metric(
            "Completed",
            stats["completed"],
            delta=f"{stats['completed'] / max(stats['total_investigations'], 1) * 100:.0f}%",
            help="Investigations that reached completion"
        )

    with col3:
        st.metric(
            "Escalated",
            stats["escalated"],
            delta=f"{stats['escalated'] / max(stats['total_investigations'], 1) * 100:.0f}%",
            delta_color="inverse",
            help="Investigations escalated to human after max rounds"
        )

    with col4:
        st.metric(
            "Avg Verification Rounds",
            f"{stats['avg_verification_rounds']:.1f}",
            help="Average number of verification rounds per investigation"
        )

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("By Severity")
        if stats["by_severity"]:
            st.bar_chart(stats["by_severity"])
        else:
            st.info("No data available")

    with col2:
        st.subheader("By Service")
        if stats["by_service"]:
            st.bar_chart(stats["by_service"])
        else:
            st.info("No data available")


def render_investigations_list():
    """Render list of all investigations."""
    st.title("📋 Investigations")

    reader = get_checkpoint_reader()
    investigations = reader.list_investigations()

    if not investigations:
        st.info("No investigations found. Run an investigation to populate the dashboard.")
        st.markdown("```bash\nexport MODE=eval\nexport SCENARIO=oom_after_deploy\npython -m agent.graph\n```")
        return

    # Filters
    col1, col2, col3 = st.columns(3)

    with col1:
        status_filter = st.selectbox(
            "Status",
            ["All"] + list(set(i["status"] for i in investigations)),
            key="status_filter"
        )

    with col2:
        severity_filter = st.selectbox(
            "Severity",
            ["All"] + list(set(i["severity"] for i in investigations)),
            key="severity_filter"
        )

    with col3:
        service_filter = st.selectbox(
            "Service",
            ["All"] + list(set(i["service"] for i in investigations)),
            key="service_filter"
        )

    # Apply filters
    filtered = investigations

    if status_filter != "All":
        filtered = [i for i in filtered if i["status"] == status_filter]

    if severity_filter != "All":
        filtered = [i for i in filtered if i["severity"] == severity_filter]

    if service_filter != "All":
        filtered = [i for i in filtered if i["service"] == service_filter]

    st.markdown(f"**Showing {len(filtered)} of {len(investigations)} investigations**")

    # Display investigations
    for inv in filtered:
        with st.expander(
            f"{'🔴' if inv['severity'] == 'critical' else '🟡' if inv['severity'] == 'high' else '🟢'} "
            f"{inv['service']} - {inv['status'].upper()}",
            expanded=False
        ):
            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.metric("Status", inv["status"])

            with col2:
                st.metric("Severity", inv["severity"])

            with col3:
                st.metric("Verification Rounds", inv["verification_rounds"])

            with col4:
                duration = format_duration(inv["started_at"], inv["completed_at"])
                st.metric("Duration", duration)

            if st.button("View Details", key=f"view_{inv['thread_id']}"):
                st.session_state.selected_thread_id = inv["thread_id"]
                st.session_state.page = "investigation_detail"
                st.rerun()


def render_investigation_detail():
    """Render detailed view of a single investigation."""
    thread_id = st.session_state.get("selected_thread_id")

    if not thread_id:
        st.error("No investigation selected")
        return

    reader = get_checkpoint_reader()
    state = reader.get_investigation(thread_id)

    if not state:
        st.error(f"Investigation not found: {thread_id}")
        return

    # Header
    if st.button("← Back to List"):
        st.session_state.page = "investigations"
        st.rerun()

    incident = state.get("incident", {})

    st.title(f"Investigation: {incident.get('service', 'Unknown')}")
    st.markdown(f"**Thread ID**: `{thread_id}`")

    # Summary
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Status", state.get("status", "unknown"))

    with col2:
        st.metric("Severity", incident.get("severity", "unknown") if incident else "unknown")

    with col3:
        st.metric("Verification Rounds", state.get("verification_round", 0))

    with col4:
        duration = format_duration(state.get("started_at"), state.get("completed_at"))
        st.metric("Duration", duration)

    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Incident", "Hypotheses", "Recovery", "Timeline"])

    with tab1:
        st.subheader("Incident Details")
        if incident:
            st.json(incident)
        else:
            st.info("No incident data")

    with tab2:
        st.subheader("Hypotheses & Verification")

        hypotheses = state.get("hypotheses", [])
        verification_results = state.get("verification_results", [])

        if not hypotheses:
            st.info("No hypotheses generated")
        else:
            for i, hypothesis in enumerate(hypotheses, 1):
                with st.expander(f"Hypothesis #{i}: {hypothesis.get('description', 'N/A')}", expanded=i == 1):
                    st.markdown(f"**Rank**: {hypothesis.get('rank', 'N/A')}")
                    st.markdown(f"**Falsification Criterion**: {hypothesis.get('falsification_criterion', 'N/A')}")

                    # Find verification result for this hypothesis
                    vr = next((v for v in verification_results if v["hypothesis"] == hypothesis), None)

                    if vr:
                        status = vr.get("status", "unknown")
                        color = "green" if status == "confirmed" else "red" if status == "refuted" else "orange"
                        st.markdown(f"**Status**: :{color}[{status.upper()}]")
                        st.markdown(f"**Reasoning**: {vr.get('reasoning', 'N/A')}")
                    else:
                        st.markdown("**Status**: Not yet verified")

    with tab3:
        st.subheader("Recovery Proposal")

        recovery = state.get("recovery_proposal")

        if not recovery:
            st.info("No recovery proposal yet")
        else:
            st.markdown(f"**Action Type**: {recovery.get('action_type', 'N/A')}")
            st.markdown(f"**Description**: {recovery.get('description', 'N/A')}")
            st.markdown(f"**Expected Effect**: {recovery.get('expected_effect', 'N/A')}")
            st.markdown(f"**Blast Radius**: {recovery.get('blast_radius', 'N/A')}")

            approval_status = recovery.get('approval_status', 'unknown')
            color = "green" if approval_status == "approved" else "red" if approval_status == "rejected" else "orange"
            st.markdown(f"**Approval**: :{color}[{approval_status.upper()}]")

            if recovery.get('approval_reasoning'):
                st.markdown(f"**Reasoning**: {recovery.get('approval_reasoning')}")

            if recovery.get('commands'):
                st.markdown("**Commands**:")
                for cmd in recovery.get('commands', []):
                    st.code(cmd, language="bash")

    with tab4:
        st.subheader("Investigation Timeline")

        timeline = reader.get_investigation_timeline(thread_id)

        if not timeline:
            st.info("No timeline data")
        else:
            for event in timeline:
                st.markdown(f"**{event['status']}** - Verification Round: {event['verification_round']}")


def render_live_investigation():
    """Render live investigation from cluster."""
    st.title("🔴 Live Investigation")
    st.markdown("Real-time view of active agent investigation in the cluster")

    # Add refresh button
    if st.button("🔄 Refresh"):
        st.rerun()

    # Get live investigation data
    live_data = get_live_investigation()

    if not live_data:
        st.info("No active investigation found in the cluster.")
        st.markdown("""
        **How to trigger an investigation:**
        1. Deploy a crashing pod (e.g., with OOMKill)
        2. Wait for Prometheus alert to fire
        3. AlertManager will send to webhook
        4. AI agent will investigate automatically
        """)
        return

    incident = live_data['incident']
    investigation = live_data['investigation']
    log_text = live_data['log']

    # Incident Summary
    st.subheader("📋 Current Incident")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Alert", incident['alert_data']['labels'].get('alertname', 'Unknown'))

    with col2:
        st.metric("Severity", incident.get('severity', 'unknown').upper())

    with col3:
        st.metric("Phase", investigation.get('phase', 'idle').replace('_', ' ').title())

    # Incident Details
    with st.expander("Full Incident Details", expanded=False):
        st.json(incident)

    # Investigation Progress
    st.subheader("🔍 Investigation Progress")

    # Phase indicators
    phases = [
        ('gathering_evidence', '🔍 Evidence Gathering', investigation.get('evidence', [])),
        ('analyzing', '🧠 Analysis', investigation.get('hypotheses', []) + investigation.get('verification', [])),
        ('creating_fix', '📝 Remediation', investigation.get('remediation', [])),
        ('completed', '✅ Complete', [investigation.get('prUrl')] if investigation.get('prUrl') else [])
    ]

    cols = st.columns(4)
    current_phase = investigation.get('phase', 'idle')

    for idx, (phase, label, items) in enumerate(phases):
        with cols[idx]:
            if current_phase == phase:
                st.markdown(f"### {label} 🔵")
                st.caption(f"{len(items)} items")
            elif phases.index((phase, label, items)) < phases.index(next((p for p in phases if p[0] == current_phase), phases[0])):
                st.markdown(f"### {label} ✅")
                st.caption(f"{len(items)} items")
            else:
                st.markdown(f"### {label}")
                st.caption("Pending")

    # Detailed sections
    if investigation.get('evidence'):
        st.subheader("🔍 Evidence Gathered")
        for item in investigation['evidence']:
            st.markdown(f"- {item}")

    if investigation.get('hypotheses'):
        st.subheader("🧠 Hypotheses")
        for item in investigation['hypotheses']:
            st.markdown(f"- {item}")

    if investigation.get('verification'):
        st.subheader("✓ Verification")
        for item in investigation['verification']:
            st.markdown(f"- {item}")

    if investigation.get('rootCause'):
        st.success(f"**ROOT CAUSE IDENTIFIED:** {investigation['rootCause']}")

    if investigation.get('remediation'):
        st.subheader("📝 Remediation Plan")
        for item in investigation['remediation']:
            st.markdown(f"- {item}")

    if investigation.get('prUrl'):
        st.markdown(f"### 🔗 Pull Request")
        st.markdown(f"[View PR on GitHub]({investigation['prUrl']})")

    # Full log
    if log_text:
        with st.expander("📋 Full Investigation Log", expanded=False):
            st.code(log_text, language='text')


def main():
    """Main dashboard application."""
    # Sidebar navigation
    st.sidebar.title("Navigation")

    page = st.sidebar.radio(
        "Go to",
        ["Live Investigation", "Overview", "Investigations"],
        key="nav"
    )

    # Update session state page
    if "page" not in st.session_state:
        st.session_state.page = page.lower().replace(' ', '_')

    # Database info
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Database")

    reader = get_checkpoint_reader()
    db_exists = reader.db_path.exists()

    if db_exists:
        st.sidebar.success(f"Connected: {reader.db_path.name}")
        st.sidebar.caption(f"Path: {reader.db_path}")
    else:
        st.sidebar.warning("No checkpoint database found")
        st.sidebar.caption(f"Expected: {reader.db_path}")

    # Auto-refresh
    st.sidebar.markdown("---")
    auto_refresh = st.sidebar.checkbox("Auto-refresh (30s)", value=False)

    if auto_refresh:
        import time
        time.sleep(30)
        st.rerun()

    # Render selected page
    if st.session_state.page == "investigation_detail":
        render_investigation_detail()
    elif st.session_state.page == "live_investigation" or page == "Live Investigation":
        render_live_investigation()
    elif st.session_state.page == "investigations" or page == "Investigations":
        render_investigations_list()
    else:
        render_overview()


if __name__ == "__main__":
    main()
