# Demo Walkthrough Guide

## Step-by-Step Presentation Script

### 1. The Normal Baseline (Dashboard)
- Open `http://localhost:3000`
- Point out the **94.2% Payment Success Rate**, telemetry line chart, and payment method distribution.
- Emphasize the live 7-day rolling baselines computed over 85,000+ historical transactions.

### 2. Triggering the Incident
- Click **One-Click Demo** in the top navigation bar (or call `POST /api/simulator/scenario` with `{"scenario": "upi_degradation"}`).
- Watch the live telemetry chart dip as UPI payment failures surge.
- An alert banner immediately flags: **"Payment Incident in Progress — Performance Degraded"**.

### 3. Entering the Incident War Room
- Navigate to **Incidents** and click **Open War Room** for the active incident.
- Point out the key facts:
  - **What changed?** Success rate fell by 30pp.
  - **When did it start?** Accurate timestamp of anomaly onset.
  - **Which dimensions are affected?** UPI (+413% failure rate, z=47.75).
  - **Explainable Revenue Exposure**: Transparent calculation of failed volume.

### 4. AI Grounded Investigation
- Click the **AI Investigation Report** tab.
- Review ranked root-cause hypotheses with confidence scores and evidence citations.
- The AI identifies: *"External UPI payment network degradation concentrated in bank timeouts"*.

### 5. Asking the AI Investigator
- Click **AI Investigator** in the sidebar.
- Click quick prompts like *"Why did payment success drop?"* or *"What is the most affected segment?"*.
- Point out that every response is strictly grounded in database telemetry without hallucinations.

### 6. Human-in-the-Loop Approval & Action Execution
- Return to the Incident detail page.
- Review the pending recommendation: *"Recommend alternative payment method to customers"*.
- Click **Approve & Execute Action**.

### 7. Closed-Loop Verification & Resolution
- Open the **Post-Action Verification** tab.
- View the Before-vs-After recovery chart: Success rate recovers from 76.8% back to 91.4% (+14.6pp gain).
- The incident status transitions to **RESOLVED**.

### 8. Reviewing the Audit Trail
- Click **Audit Trail** in the sidebar to show the complete immutable record of detections, investigations, merchant approvals, and results.
