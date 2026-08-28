# Evaluation & Benchmark Results

## Benchmark Summary (Evaluated on 85,200 Synthetic Transactions)

```
============================================================
PAYPULSE AI — EVALUATION BENCHMARK SUITE
============================================================

[Benchmark 1] Anomaly Detection Precision on Incident Traffic
  - Anomaly Flagged: True (100% Precision)
  - Observed Success Rate: 81.9%
  - Baseline Success Rate: 93.6%
  - Severity Classified: CRITICAL
  - Anomalous Signals Detected: 2 (UPI and correlated gateways)

[Benchmark 2] Multi-dimensional Investigation & Segment Localization
  - Top Affected Segments Identified: 8
    * payment_method = UPI (Deviation: +413.4%, z=47.75)
    * device = UNKNOWN (Deviation: +246.7%, z=5.96)
    * location = Kolkata (Deviation: +218.7%, z=8.75)

[Benchmark 3] Business Impact Quantification Accuracy
  - Affected Transactions: 792
  - Incremental Failures (above baseline): 509.2
  - Estimated Exposure: INR 7,302,244.53
  - Customers Impacted: 735

[Benchmark 4] Computation Latency Profile
  - Anomaly Detection Pipeline: 27.07 ms
  - Dimensional Investigation Pipeline: 162.85 ms
  - Total Real-time Telemetry Latency: 189.92 ms (Target: < 200 ms)

[Benchmark 5] Post-Action Verification Loop
  - Pre-Action Success: 76.8%
  - Post-Action Success: 91.4%
  - Measured Absolute Gain: +14.6 percentage points
```
