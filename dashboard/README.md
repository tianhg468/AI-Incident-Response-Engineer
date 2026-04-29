## AI Incident Response Dashboard

Streamlit-based dashboard for monitoring and analyzing incident investigations. Provides real-time visibility into active investigations, historical data, and performance metrics.

## Features

### Overview Page
- **Summary Metrics**
  - Total investigations
  - Completion rate
  - Escalation rate
  - Average verification rounds
- **Distribution Charts**
  - Investigations by severity (critical/high/medium/low)
  - Investigations by service
- **Real-time Updates**
  - Auto-refresh option (30s interval)

### Investigations List
- **Filterable Table**
  - Filter by status (completed, escalated, etc.)
  - Filter by severity
  - Filter by service
- **Investigation Cards**
  - Status, severity, duration
  - Verification rounds
  - Quick access to details

### Investigation Detail View
- **Incident Tab**
  - Full incident details (service, severity, time window)
  - Affected pods and endpoints
  - Alert information
- **Hypotheses Tab**
  - All generated hypotheses
  - Verification status (confirmed/refuted/inconclusive)
  - Falsification criteria
  - Supporting evidence
- **Recovery Tab**
  - Proposed remediation action
  - Expected effect and blast radius
  - Approval status and reasoning
  - Commands to execute
- **Timeline Tab**
  - Chronological view of investigation progress
  - Checkpoint history

## Quick Start

### 1. Run Some Investigations

The dashboard reads from the checkpoint database, so you need investigations first:

```bash
# Set environment
export MODE=eval
export SCENARIO=oom_after_deploy
export CHECKPOINT_MODE=sqlite
export CHECKPOINT_DB_PATH=./data/checkpoints.db

# Run an investigation
python -m agent.graph

# Run multiple scenarios for more data
export SCENARIO=5xx_spike_feature_flag
python -m agent.graph

export SCENARIO=dns_resolution_failure
python -m agent.graph
```

### 2. Launch Dashboard

```bash
streamlit run dashboard/app.py
```

The dashboard will open in your browser at http://localhost:8501

### 3. Explore

- **Overview** - See summary statistics and charts
- **Investigations** - Browse all investigations with filters
- Click any investigation to see full details

## Configuration

### Database Path

By default, the dashboard reads from `./data/checkpoints.db`. To use a different database:

```bash
export CHECKPOINT_DB_PATH=/path/to/your/checkpoints.db
streamlit run dashboard/app.py
```

### Auto-Refresh

Enable auto-refresh from the sidebar to automatically reload data every 30 seconds:

1. Open sidebar
2. Check "Auto-refresh (30s)"

## Dashboard Components

### checkpoint_reader.py

Reads investigation data from the LangGraph SQLite checkpoint database:

```python
from dashboard.checkpoint_reader import CheckpointReader

reader = CheckpointReader()

# List all investigations
investigations = reader.list_investigations()

# Get detailed state for one investigation
state = reader.get_investigation(thread_id)

# Get timeline of checkpoints
timeline = reader.get_investigation_timeline(thread_id)

# Get aggregate statistics
stats = reader.get_statistics()
```

### app.py

Main Streamlit application with three views:

1. **Overview** - `render_overview()`
2. **Investigations List** - `render_investigations_list()`
3. **Investigation Detail** - `render_investigation_detail()`

## Understanding the Data

### Investigation States

Investigations progress through these states:

- `intake` - Parsing the incident
- `gathering_evidence` - Collecting logs, metrics, events
- `diagnosing` - Generating hypotheses
- `verifying` - Testing hypotheses
- `awaiting_approval` - Waiting for human approval
- `executing` - Running remediation
- `completed` - Successfully completed
- `escalated` - Escalated to human after max rounds

### Verification Status

Each hypothesis can have these verification statuses:

- `confirmed` - Hypothesis verified, proceeding to remediation
- `refuted` - Hypothesis disproven, backtracking to try next
- `inconclusive` - Not enough evidence to confirm or refute

### Approval Status

Recovery proposals have these approval statuses:

- `pending` - Awaiting approval
- `approved` - Approved (auto or manual)
- `rejected` - Rejected by human
- `timeout` - No response within timeout window

## Metrics Explained

### Completion Rate

Percentage of investigations that reached `completed` status (vs. escalated or still in progress).

**Target**: ≥ 75% (from eval harness goals)

### Escalation Rate

Percentage of investigations escalated to humans after reaching max verification rounds.

**Target**: ≤ 25% (from eval harness goals)

### Average Verification Rounds

Average number of hypothesis verification attempts per investigation.

**Target**: ≤ 2.5 (from eval harness goals)

Lower is better - indicates the agent is finding the right hypothesis quickly.

## Example Workflow

1. **Run investigation**:
   ```bash
   export MODE=eval SCENARIO=oom_after_deploy
   python -m agent.graph
   ```

2. **View in dashboard**:
   - Open http://localhost:8501
   - See the new investigation in the list
   - Click to view full transcript

3. **Analyze results**:
   - Check if hypothesis was correct
   - Review verification reasoning
   - Verify remediation is appropriate
   - Check approval flow worked

4. **Iterate**:
   - Run more investigations
   - Track metrics over time
   - Identify patterns in failures

## Advanced Usage

### Filtering

Use the filters to find specific investigations:

```
Status: completed
Severity: critical
Service: payment-service
```

This shows all completed critical incidents for the payment service.

### Timeline Analysis

The timeline view shows every checkpoint saved during the investigation:

- See when each verification round started
- Identify where the agent spent the most time
- Debug unexpected state transitions

### Comparing Investigations

Open multiple investigations in separate browser tabs to compare:

- Different hypotheses for similar incidents
- Verification strategies
- Recovery proposals

## Troubleshooting

### "No investigations found"

The checkpoint database is empty. Run some investigations first:

```bash
export MODE=eval
python -m agent.graph
```

### Database connection error

Check that the database path is correct:

```bash
ls -la ./data/checkpoints.db

# Or set custom path
export CHECKPOINT_DB_PATH=/path/to/checkpoints.db
```

### Dashboard not updating

If you run a new investigation but don't see it:

1. Click the sidebar refresh button
2. Or enable auto-refresh
3. Or manually refresh the browser (F5)

### Data looks wrong

The checkpoint database schema might have changed. Try:

```bash
# Backup old database
mv ./data/checkpoints.db ./data/checkpoints.db.bak

# Run fresh investigations
export MODE=eval
python -m agent.graph
```

## Production Deployment

For production use, consider:

### Authentication

Add authentication to restrict dashboard access:

```python
# Install streamlit-authenticator
pip install streamlit-authenticator

# Add to app.py
import streamlit_authenticator as stauth

authenticator = stauth.Authenticate(...)
name, authentication_status, username = authenticator.login('Login', 'main')
```

### HTTPS

Deploy behind a reverse proxy with TLS:

```nginx
server {
    listen 443 ssl;
    server_name dashboard.your-company.com;

    location / {
        proxy_pass http://localhost:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### Database Permissions

Ensure the dashboard has read-only access to the database:

```sql
-- Create read-only user (if using Postgres)
CREATE USER dashboard_readonly WITH PASSWORD 'password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO dashboard_readonly;
```

### Monitoring

Track dashboard usage and performance:

```bash
# Enable Streamlit metrics
streamlit run dashboard/app.py --server.enableXsrfProtection=true \
    --server.enableCORS=false \
    --logger.level=info
```

## Future Enhancements

Potential additions:

- [ ] Per-node latency tracking
- [ ] Token cost estimation per investigation
- [ ] Hypothesis acceptance rate (was first hypothesis correct?)
- [ ] Time-to-diagnosis distribution chart
- [ ] Time-to-resolution distribution chart
- [ ] Export investigation as PDF report
- [ ] Compare multiple investigations side-by-side
- [ ] Alert if escalation rate exceeds threshold
- [ ] Integration with Slack for notifications
- [ ] Search across investigation transcripts

## Resources

- [Streamlit Documentation](https://docs.streamlit.io)
- [Streamlit Charts](https://docs.streamlit.io/library/api-reference/charts)
- [LangGraph Checkpointing](https://langchain-ai.github.io/langgraph/how-tos/persistence/)
