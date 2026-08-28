# Security, Privacy & Compliance

1. **Zero Real Customer Data**: All customer and card records in the demo environment are synthetically generated with Faker and randomized seeds.
2. **Credential Safety**: No API secrets or production tokens are hardcoded. All configurations use `.env` / environment variables.
3. **Bounded Actions Only**: The AI agent is prohibited from issuing arbitrary system calls or unbounded financial refunds. All actions belong to pre-vetted operational templates.
4. **Human-in-the-Loop Safeguards**: Sensitive actions (e.g. gateway rerouting, support escalations, retry policies) require explicit authenticated user approval.
5. **Full Auditability**: Every detection, hypothesis, approval, rejection, and execution is written to an immutable `audit_logs` table.
