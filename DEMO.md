# Quick Demo Guide

This guide will walk you through running a test demo to see the AI Incident Response Engineer in action.

## Prerequisites

Before starting, ensure you have:
- Python 3.11 or higher
- pip or uv package manager
- An Anthropic API key (get one at https://console.anthropic.com/)

## Step 1: Install Dependencies

```bash
# Navigate to project directory
cd /Users/tianhuang/Documents/Personal/Job_Intern_Application/projects/agentic_ai

# Install dependencies
pip install -e "."

# Or with uv (faster):
# uv pip install -e "."
```

This will install all required packages including:
- langgraph (state machine framework)
- anthropic (LLM API)
- streamlit (dashboard)
- sentence-transformers (for similar incident search)
- And all other dependencies

## Step 2: Set Up Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your API key
# You only need to set ANTHROPIC_API_KEY for the demo
nano .env  # or use your preferred editor
```

**Minimal .env configuration for demo:**
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Already configured for demo (no changes needed)
MODE=eval
SCENARIO=oom_after_deploy
CHECKPOINT_MODE=sqlite
CHECKPOINT_DB_PATH=./data/checkpoints.db
```

**Where to get your Anthropic API key:**
1. Go to https://console.anthropic.com/
2. Sign in or create an account
3. Navigate to "API Keys"
4. Create a new key
5. Copy it to your .env file

## Step 3: Run Your First Investigation

Now let's run the OOM (Out of Memory) incident scenario:

```bash
# Set environment variables (if not using .env file)
export MODE=eval
export SCENARIO=oom_after_deploy
export ANTHROPIC_API_KEY=sk-ant-api03-your-key-here

# Run the investigation
python -m agent.graph
```

**What you should see:**

```
=== AI Incident Response Engineer ===

[Intake] Loading incident from scenario: oom_after_deploy
  ✓ Incident loaded: payment-service pods OOMKilled
  Service: payment-service
  Severity: high
  Status: active

[Evidence Gathering] Collecting evidence from MCP servers...
  ✓ Kubernetes: Pod status (3 pods)
  ✓ Kubernetes: Pod logs
  ✓ Kubernetes: Events (6 events)
  ✓ GitHub: Deploy history
  ✓ Evidence collected in 1.2s

[Diagnosis] Generating hypotheses...
  ✓ Generated 3 hypotheses
  1. Memory limits lowered in deployment (suspicion: 95)
  2. Memory leak in application code (suspicion: 60)
  3. Traffic spike overwhelming pods (suspicion: 40)

[Verification] Testing hypothesis 1: Memory limits lowered...
  ✓ Running verification checks
  ✓ Check: Deployment history
  ✓ Check: Memory limits
  ✓ LLM evaluation: CONFIRMED
  Reasoning: Strong evidence of limit change from 2Gi to 512Mi

[Recovery Proposal] Generating remediation...
  ✓ Action: rollback deployment
  ✓ Description: Restore memory limits to 2Gi
  ✓ Auto-approved in eval mode

[Execution] Executing remediation...
  ✓ Rollback simulated (eval mode)
  ✓ Status: success

[Post-Mortem] Generating report...
  ✓ Timeline created
  ✓ Root cause documented
  ✓ Action items generated

=== Investigation Complete ===
Duration: 12.3s
Verification rounds: 1
Cost: $0.009
Status: resolved
```

## Step 4: View Results in Dashboard

Now launch the Streamlit dashboard to see your investigation:

```bash
# Launch dashboard
streamlit run dashboard/app.py
```

This will:
1. Start the Streamlit server
2. Automatically open your browser to http://localhost:8501
3. Show the dashboard with your investigation

**Dashboard features:**

1. **Overview Page:**
   - Total investigations: 1
   - Completion rate: 100%
   - Average verification rounds: 1
   - Charts showing distribution

2. **Investigations List:**
   - Click on "oom_after_deploy" to see details
   - Filter by status, severity, service

3. **Investigation Detail (click on investigation):**
   - **Incident Tab:** Full incident details
   - **Hypotheses Tab:** All 3 hypotheses with verification status
   - **Recovery Tab:** Rollback proposal and approval info
   - **Timeline Tab:** Complete investigation flow

## Step 5: Run Additional Scenarios

Try other incident scenarios to see different behaviors:

```bash
# Scenario 1: OOM after deploy (Easy - you just ran this)
export SCENARIO=oom_after_deploy
python -m agent.graph

# Scenario 2: 5xx spike from feature flag (Medium)
export SCENARIO=5xx_spike_feature_flag
python -m agent.graph

# Scenario 3: DNS resolution failure (Hard)
export SCENARIO=dns_resolution_failure
python -m agent.graph

# Scenario 4: Slow query missing index (Medium)
export SCENARIO=slow_query_missing_index
python -m agent.graph

# Scenario 5: Cascading failure timeout (Hard)
export SCENARIO=cascading_failure_timeout
python -m agent.graph
```

After running multiple scenarios, refresh the dashboard to see all investigations!

## Step 6: Run the Full Eval Suite

Run automated evaluation across all scenarios:

```bash
# Run all 5 scenarios with automated scoring
python -m evals.runner

# Or run a specific scenario
python -m evals.runner --scenario oom_after_deploy

# Generate report to custom location
python -m evals.runner --report ./my_eval_results.md
```

**Expected output:**
```
Running evaluation scenarios...

Scenario 1/5: oom_after_deploy
  ✓ Investigation completed
  ✓ Root cause: exact match (100%)
  ✓ Remediation: acceptable
  ✓ Rounds: 1 (expected: 1)
  ✓ Cost: $0.009

Scenario 2/5: 5xx_spike_feature_flag
  ✓ Investigation completed
  ...

=== Evaluation Results ===
Root Cause Accuracy (Exact): 80%
Root Cause Accuracy (Partial+): 100%
Remediation Acceptability: 100%
Avg Verification Rounds: 1.8
Avg Cost: $0.011
Escalation Rate: 0%

✓ Report saved to: eval_results.md
```

## Step 7: Test Resumability (Optional)

Test that investigations survive restarts:

```bash
# Run the resumability test
python tests/test_checkpointing.py
```

This demonstrates:
1. Starting an investigation
2. Simulating a process restart
3. Resuming from the exact checkpoint
4. Verifying state continuity

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'langgraph'"

**Solution:** Dependencies not installed
```bash
pip install -e "."
```

### Issue: "anthropic.AuthenticationError"

**Solution:** API key not set or invalid
```bash
# Check your .env file has the correct key
cat .env | grep ANTHROPIC_API_KEY

# Or export directly
export ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
```

### Issue: "FileNotFoundError: fixtures/scenarios/oom_after_deploy"

**Solution:** Make sure you're in the project root directory
```bash
cd /Users/tianhuang/Documents/Personal/Job_Intern_Application/projects/agentic_ai
python -m agent.graph
```

### Issue: Dashboard shows "No investigations found"

**Solution:** Run an investigation first, then refresh the dashboard
```bash
# Run an investigation
python -m agent.graph

# Then in another terminal, launch dashboard
streamlit run dashboard/app.py

# Click "Refresh Data" button in the dashboard
```

### Issue: "Could not connect to checkpoint database"

**Solution:** Database directory doesn't exist
```bash
# Create the data directory
mkdir -p data

# Run again
python -m agent.graph
```

## What's Happening Under the Hood

When you run `python -m agent.graph` in eval mode:

1. **Intake:** Loads incident from `fixtures/scenarios/oom_after_deploy/manifest.json`
2. **Evidence Gathering:** Calls mock MCP servers that serve fixture data
3. **Diagnosis:** Uses Claude (Anthropic LLM) to generate hypotheses
4. **Verification:** Tests each hypothesis with targeted checks
5. **Backtracking:** If hypothesis refuted, goes back to test next one
6. **Recovery:** Proposes remediation (auto-approved in eval mode)
7. **Execution:** Simulates execution (no real changes)
8. **Post-Mortem:** Generates comprehensive report
9. **Checkpointing:** Saves full state to SQLite database

The entire investigation takes ~10-15 seconds and costs ~$0.01 in API calls.

## Next Steps

Now that you've seen the basic demo:

1. **Read the worked example:** See `EXAMPLE.md` for detailed walkthrough
2. **Review architecture:** See `ARCHITECTURE.md` for system design
3. **Understand limitations:** See `LIMITATIONS.md` for honest assessment
4. **Explore the code:** Start with `agent/graph.py` for the main workflow
5. **Try live mode:** Follow `mcp_servers/real/README.md` to connect real infrastructure

## Demo Checklist

- [ ] Python 3.11+ installed
- [ ] Dependencies installed (`pip install -e "."`)
- [ ] .env file created with ANTHROPIC_API_KEY
- [ ] First investigation run successfully (`python -m agent.graph`)
- [ ] Dashboard launched (`streamlit run dashboard/app.py`)
- [ ] Multiple scenarios tested
- [ ] Eval suite run (`python -m evals.runner`)
- [ ] Explored dashboard features (overview, list, detail views)

Congratulations! You've successfully run the AI Incident Response Engineer demo.
