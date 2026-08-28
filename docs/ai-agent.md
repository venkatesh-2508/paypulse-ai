# AI Investigation Agent & Guardrails

## Philosophy: Tool-Grounded Investigation
PayPulse AI strictly prevents hallucinations by utilizing a **function-calling agent architecture** (Google Gemini 1.5 Flash). The agent does not read the raw entire database into its prompt; instead, it issues structured tool calls to retrieve focused telemetry, compares segments against baselines, and generates ranked hypotheses supported by cited evidence.

## 10 Agent Tools
1. `get_incident(incident_id)`: Fetches incident severity, status, timestamps, and overall metrics.
2. `get_payment_statistics(incident_id)`: Retrieves current vs baseline success rate and degradation delta.
3. `get_failure_breakdown(incident_id, dimension)`: Returns top failure counts and rates across `payment_method`, `bank`, `device`, `location`, `error_reason`, and `error_source`.
4. `get_historical_baseline(incident_id, dimension, dimension_value)`: Queries expected historical performance and standard deviation.
5. `get_affected_segments(incident_id)`: Fetches anomalous segments ranked by deviation from baseline.
6. `get_recent_events(incident_id, limit)`: Returns recent state machine event logs for temporal onset analysis.
7. `get_recent_changes(incident_id)`: Queries external deployment and configuration logs.
8. `estimate_business_impact(incident_id)`: Calculates transparent financial exposure and affected customer counts.
9. `get_available_actions(incident_id)`: Fetches bounded approved action catalog.
10. `create_investigation_report(...)`: Emits structured JSON investigation report with evidence citations.

## Safety Guardrails
- **Zero Fabrication**: The agent is instructed to state "Insufficient evidence to determine the cause" if signal strength is below confidence thresholds.
- **Bounded Recommendations**: Recommendations are strictly validated against the `ActionType` enumeration library.
- **Graceful Deterministic Fallback**: If LLM API keys are missing or experience upstream downtime, the backend automatically falls back to deterministic statistical investigation without disrupting operations.
