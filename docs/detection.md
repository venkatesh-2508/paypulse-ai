# Statistical Anomaly Detection Methodology

## Formula & Logic
PayPulse AI operates on rolling 30-minute observation windows compared against 7-day historical segment baselines:

$$Z = \frac{R_{\text{current}} - R_{\text{baseline}}}{\text{SE}}$$

$$\text{SE} = \frac{\sigma_{\text{baseline}}}{\sqrt{N}}$$

$$\text{Deviation \%} = \frac{R_{\text{baseline}} - R_{\text{current}}}{R_{\text{baseline}}} \times 100$$

## Minimum Volume Thresholds
To prevent false alarms caused by low-traffic sampling noise, an anomaly is only flagged if $N \ge 20$ transactions in the evaluation window.

## Severity Classification
- **CRITICAL**: Deviation $\ge 40\%$ OR $|Z| \ge 6.0$
- **HIGH**: Deviation $\ge 25\%$ OR $|Z| \ge 4.0$
- **MEDIUM**: Deviation $\ge 15\%$ OR $|Z| \ge 2.5$
- **LOW**: Below threshold (Normal baseline fluctuations)
