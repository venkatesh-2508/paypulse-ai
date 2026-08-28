# Relational Data Model & Schema

PayPulse AI utilizes a normalized relational schema with UUID primary keys, foreign key constraints, and indexed telemetry lookup columns.

## Core Relational Tables

| Table | Purpose | Key Columns |
|---|---|---|
| `merchants` | Merchant profile and Razorpay configuration | `id`, `name`, `email`, `business_type`, `razorpay_key_id` |
| `customers` | Synthetic customer segmentation | `id`, `merchant_id`, `name`, `email`, `segment` (NEW, RETURNING, VIP) |
| `payment_methods` | Payment rails | `id`, `name`, `type` (UPI, CARD, NET_BANKING, WALLET, EMI) |
| `banks` | Issuer and acquiring banks | `id`, `name`, `code` (HDFC, ICICI, SBI, AXIS, etc.) |
| `devices` | Client device profiles | `id`, `type` (ANDROID, IOS, DESKTOP), `os_version`, `browser` |
| `locations` | Geographic regions | `id`, `country`, `state`, `city` |
| `transactions` | Core payment transactions (85k+ rows) | `id`, `merchant_id`, `amount`, `status`, `error_source`, `error_step`, `error_reason`, `created_at` |
| `payment_events` | State machine transition events | `id`, `transaction_id`, `event_type` (INITIATED, PROCESSING, SUCCESS, FAILURE, RETRY, REFUND) |
| `historical_baselines` | 7-day rolling statistical baselines | `merchant_id`, `dimension`, `dimension_value`, `success_rate`, `std_dev` |
| `incidents` | Detected payment incidents | `id`, `severity`, `status`, `current_success_rate`, `baseline_success_rate`, `estimated_exposure` |
| `incident_signals` | Dimensional trigger signals | `incident_id`, `dimension`, `dimension_value`, `deviation_pct`, `z_score` |
| `incident_hypotheses` | Candidate root-cause explanations | `incident_id`, `title`, `confidence`, `supporting_evidence_ids` |
| `recommendations` | Bounded actions | `incident_id`, `action_type`, `approval_status`, `approved_by` |
| `action_results` | Verification loop results | `recommendation_id`, `success_rate_before`, `success_rate_after`, `verification_result` |
| `audit_logs` | Immutable system and user audit trail | `actor`, `action`, `reason`, `result`, `metadata`, `created_at` |
