# Known Limitations & Roadmap

## Current Prototype Limitations
1. **Simulated Action Execution**: Action execution simulates routing changes and retry behavior rather than modifying live bank core switches.
2. **Batch Windowing**: Rolling statistics operate on configurable 5-to-30 minute micro-batches rather than sub-millisecond stream processing (e.g. Apache Flink).
3. **Single Merchant Tenant**: The current demo focuses on deep single-merchant operational workflows with multi-user auditability.

## Future Engineering Roadmap
1. **Multi-Gateway Smart Router Integration**: Direct webhook webhooks for automatic failover with Razorpay Route / Optimizer APIs.
2. **Cross-Merchant Network Intelligence**: Privacy-preserving federated anomaly detection across multiple merchants to identify industry-wide bank outages before local impact.
3. **Predictive Outage Forecasting**: LSTM / Prophet time-series models for predicting scheduled bank maintenance downtime.
