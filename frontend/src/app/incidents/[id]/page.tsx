"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { 
  AlertTriangle, 
  ArrowLeft, 
  Bot, 
  CheckCircle2, 
  Clock, 
  IndianRupee, 
  ShieldAlert, 
  TrendingDown, 
  TrendingUp, 
  UserCheck, 
  XCircle,
  Play,
  Sparkles,
  HelpCircle,
  Check,
  Layers,
  Activity,
  ArrowRight
} from "lucide-react";
import { 
  BarChart, 
  Bar, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  Cell, 
  CartesianGrid 
} from "recharts";

interface IncidentDetail {
  id: string;
  merchant_id: string;
  merchant_name: string;
  severity: string;
  status: string;
  title: string;
  description: string;
  start_time: string;
  detected_at: string;
  resolved_at: string | null;
  current_success_rate: number;
  baseline_success_rate: number;
  affected_transaction_count: number;
  estimated_exposure: number;
  investigation_report: any;
  signals: any[];
  hypotheses: any[];
  recommendation: any;
  action_result: any;
}

export default function IncidentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const incidentId = resolvedParams.id;

  const [incident, setIncident] = useState<IncidentDetail | null>(null);
  const [timeline, setTimeline] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"investigation" | "segments" | "timeline" | "verification">("investigation");

  const fetchIncident = async () => {
    try {
      const [incRes, timeRes] = await Promise.all([
        fetch(`/api/incidents/${incidentId}`),
        fetch(`/api/incidents/${incidentId}/timeline`)
      ]);
      if (incRes.ok) {
        const data = await incRes.json();
        setIncident(data);
      }
      if (timeRes.ok) {
        const tData = await timeRes.json();
        setTimeline(tData.timeline || []);
      }
    } catch (e) {
      console.error("Failed to fetch incident", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncident();
    const interval = setInterval(fetchIncident, 5000);
    return () => clearInterval(interval);
  }, [incidentId]);

  const handleTriggerInvestigate = async () => {
    try {
      setActionLoading(true);
      await fetch(`/api/incidents/${incidentId}/investigate`, { method: "POST" });
      setTimeout(fetchIncident, 2000);
    } catch (e) {
      alert("Investigation trigger failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleApprove = async () => {
    try {
      setActionLoading(true);
      await fetch(`/api/incidents/${incidentId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approved_by: "merchant_ops@demomart.com" }),
      });
      // Immediately execute the approved action
      await fetch(`/api/incidents/${incidentId}/execute`, { method: "POST" });
      setTimeout(fetchIncident, 1000);
    } catch (e) {
      alert("Approval / execution failed");
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    const reason = prompt("Enter rejection reason:");
    if (!reason) return;
    try {
      setActionLoading(true);
      await fetch(`/api/incidents/${incidentId}/reject`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rejected_by: "merchant_ops@demomart.com", reason }),
      });
      fetchIncident();
    } catch (e) {
      alert("Rejection failed");
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !incident) {
    return (
      <div style={{ padding: "60px 0", textAlign: "center", color: "var(--text-muted)" }}>
        <Activity style={{ animation: "spin 2s infinite linear", margin: "0 auto 12px" }} />
        <p>Loading incident war room...</p>
      </div>
    );
  }

  const report = incident.investigation_report;
  const isResolved = incident.status === "RESOLVED";
  const sevClass = `badge-${incident.severity.toLowerCase()}`;
  const successPct = (incident.current_success_rate * 100).toFixed(1);
  const basePct = (incident.baseline_success_rate * 100).toFixed(1);
  const degradationPp = ((incident.baseline_success_rate - incident.current_success_rate) * 100).toFixed(1);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Top Breadcrumb & Actions */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Link href="/incidents" style={{ display: "flex", alignItems: "center", gap: "6px", color: "var(--text-secondary)", fontSize: "0.875rem" }}>
          <ArrowLeft style={{ width: "16px", height: "16px" }} />
          <span>Back to Incidents</span>
        </Link>
        <div style={{ display: "flex", gap: "10px" }}>
          {!report && (
            <button 
              onClick={handleTriggerInvestigate} 
              disabled={actionLoading}
              className="btn btn-primary btn-sm"
            >
              <Sparkles style={{ width: "14px", height: "14px" }} />
              <span>{actionLoading ? "Investigating..." : "Run AI Investigation"}</span>
            </button>
          )}
          <Link href={`/investigator?incident_id=${incident.id}`} className="btn btn-secondary btn-sm">
            <Bot style={{ width: "14px", height: "14px", color: "var(--accent-primary)" }} />
            <span>Ask AI Investigator</span>
          </Link>
        </div>
      </div>

      {/* Incident Header Card */}
      <div className="card" style={{ borderColor: incident.severity === "CRITICAL" ? "rgba(239, 68, 68, 0.4)" : "var(--border-subtle)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
          <div style={{ flex: 1, minWidth: "300px" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" }}>
              <span className={`badge ${sevClass}`}>
                <span className="badge-dot" />
                {incident.severity}
              </span>
              <span className={`badge ${isResolved ? 'badge-success' : 'badge-warning'}`}>
                {incident.status}
              </span>
              <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                ID: {incident.id}
              </span>
            </div>
            <h1 style={{ fontSize: "1.375rem", fontWeight: "700", color: "#FFFFFF", lineHeight: "1.3" }}>
              {incident.title}
            </h1>
            <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "6px" }}>
              {incident.description}
            </p>
          </div>

          {/* Quick Metrics Bar */}
          <div style={{ display: "flex", gap: "20px", background: "var(--bg-surface-elevated)", padding: "12px 20px", borderRadius: "var(--radius-md)", border: "1px solid var(--border-subtle)" }}>
            <div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Success Rate</div>
              <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "#F87171", marginTop: "2px" }}>
                {successPct}%
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>Base: {basePct}%</div>
            </div>
            <div style={{ width: "1px", background: "var(--border-medium)" }} />
            <div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Est. Exposure</div>
              <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "#FBBF24", marginTop: "2px" }}>
                ₹{Number(incident.estimated_exposure || 0).toLocaleString("en-IN")}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{incident.affected_transaction_count} failed txns</div>
            </div>
            <div style={{ width: "1px", background: "var(--border-medium)" }} />
            <div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", textTransform: "uppercase" }}>Started At</div>
              <div style={{ fontSize: "0.9375rem", fontWeight: "600", color: "var(--text-primary)", marginTop: "6px" }}>
                {new Date(incident.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
              <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>{new Date(incident.start_time).toLocaleDateString()}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Human Approval Action Card (if action pending) */}
      {incident.recommendation && incident.recommendation.approval_status === "PENDING" && (
        <div style={{
          background: "linear-gradient(135deg, rgba(245, 158, 11, 0.12) 0%, rgba(245, 158, 11, 0.04) 100%)",
          border: "1px solid rgba(245, 158, 11, 0.5)",
          borderRadius: "var(--radius-lg)",
          padding: "20px 24px",
          boxShadow: "0 4px 20px rgba(245, 158, 11, 0.15)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "16px" }}>
            <div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#FBBF24", fontWeight: "700", fontSize: "0.9375rem" }}>
                <UserCheck style={{ width: "18px", height: "18px" }} />
                <span>Human-in-the-Loop Action Approval Required</span>
                <span className="badge badge-warning" style={{ fontSize: "0.65rem" }}>Approval Required</span>
              </div>
              <h3 style={{ fontSize: "1.125rem", fontWeight: "700", color: "#FFFFFF", marginTop: "8px" }}>
                {incident.recommendation.title}
              </h3>
              <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "4px", maxWidth: "700px" }}>
                {incident.recommendation.description}
              </p>
              <div style={{ marginTop: "10px", fontSize: "0.8125rem", color: "var(--status-success)", fontWeight: "500" }}>
                ✓ {incident.recommendation.expected_improvement}
              </div>
            </div>

            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <button 
                onClick={handleReject}
                disabled={actionLoading}
                className="btn btn-secondary"
              >
                <XCircle style={{ width: "16px", height: "16px", color: "#F87171" }} />
                <span>Reject</span>
              </button>
              <button 
                onClick={handleApprove}
                disabled={actionLoading}
                className="btn btn-success"
              >
                <CheckCircle2 style={{ width: "16px", height: "16px" }} />
                <span>Approve & Execute Action</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tabs Navigation */}
      <div style={{ display: "flex", borderBottom: "1px solid var(--border-subtle)", gap: "24px" }}>
        {[
          { id: "investigation", label: "AI Investigation Report", icon: Bot },
          { id: "segments", label: "Anomalous Segments", icon: Layers },
          { id: "timeline", label: "Incident Timeline", icon: Clock },
          { id: "verification", label: "Post-Action Verification", icon: CheckCircle2 },
        ].map((t) => {
          const Icon = t.icon;
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id as any)}
              style={{
                background: "transparent",
                color: isActive ? "var(--accent-primary)" : "var(--text-secondary)",
                padding: "12px 4px",
                fontSize: "0.875rem",
                fontWeight: isActive ? "600" : "500",
                borderBottom: isActive ? "2px solid var(--accent-primary)" : "2px solid transparent",
                display: "flex",
                alignItems: "center",
                gap: "8px",
                cursor: "pointer",
                transition: "all 0.15s ease"
              }}
            >
              <Icon style={{ width: "16px", height: "16px" }} />
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: AI Investigation Report */}
      {activeTab === "investigation" && (
        <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "20px" }}>
          {/* Main Investigation Content */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {report ? (
              <>
                {/* Executive Summary */}
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">
                      <Bot style={{ width: "18px", height: "18px", color: "var(--accent-primary)" }} />
                      <span>Executive Investigation Summary</span>
                    </h2>
                    <span className="badge badge-purple">
                      AI Generated ({report.confidence ? `${(report.confidence * 100).toFixed(0)}% Confidence` : 'Verified'})
                    </span>
                  </div>
                  <p style={{ fontSize: "0.9375rem", color: "var(--text-primary)", lineHeight: "1.6" }}>
                    {report.incident_summary}
                  </p>

                  <div style={{ marginTop: "16px", padding: "12px 16px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}>
                    <div style={{ fontSize: "0.75rem", fontWeight: "600", color: "var(--text-muted)", textTransform: "uppercase" }}>
                      What Changed & Onset Timing
                    </div>
                    <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "4px" }}>
                      {report.what_changed}
                    </p>
                  </div>
                </div>

                {/* Root Cause Hypotheses */}
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">
                      <ShieldAlert style={{ width: "18px", height: "18px", color: "var(--status-warning)" }} />
                      <span>Root Cause Hypotheses (Ranked)</span>
                    </h2>
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    {report.candidate_causes?.map((cause: any, idx: number) => (
                      <div 
                        key={idx} 
                        style={{ 
                          padding: "14px 16px", 
                          background: idx === 0 ? "rgba(59, 130, 246, 0.08)" : "var(--bg-surface-elevated)",
                          border: idx === 0 ? "1px solid rgba(59, 130, 246, 0.3)" : "1px solid var(--border-subtle)",
                          borderRadius: "var(--radius-md)" 
                        }}
                      >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                          <div style={{ fontWeight: "600", color: idx === 0 ? "#60A5FA" : "var(--text-primary)", fontSize: "0.9375rem" }}>
                            {idx === 0 ? "★ Leading Hypothesis: " : "Candidate Hypothesis: "}
                            {cause.hypothesis}
                          </div>
                          <span className={`badge ${cause.confidence > 0.7 ? 'badge-high' : 'badge-low'}`} style={{ fontSize: "0.7rem" }}>
                            {(cause.confidence * 100).toFixed(0)}% Confidence
                          </span>
                        </div>
                        <div style={{ marginTop: "8px" }}>
                          <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginBottom: "4px" }}>Supporting Evidence:</div>
                          <ul style={{ paddingLeft: "18px", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                            {cause.supporting_evidence?.map((ev: string, evIdx: number) => (
                              <li key={evIdx} style={{ marginBottom: "2px" }}>{ev}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Key Evidence & Reasoning */}
                <div className="card">
                  <div className="card-header">
                    <h2 className="card-title">
                      <CheckCircle2 style={{ width: "18px", height: "18px", color: "var(--status-success)" }} />
                      <span>Key Telemetry Evidence</span>
                    </h2>
                  </div>
                  <ul style={{ paddingLeft: "20px", display: "flex", flexDirection: "column", gap: "8px", fontSize: "0.875rem", color: "var(--text-primary)" }}>
                    {report.key_evidence?.map((ev: string, idx: number) => (
                      <li key={idx}>{ev}</li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              <div className="card" style={{ textAlign: "center", padding: "60px 20px" }}>
                <Bot style={{ width: "40px", height: "40px", color: "var(--accent-primary)", margin: "0 auto 12px" }} />
                <h3 style={{ fontSize: "1.125rem", fontWeight: "700" }}>Investigation Pending</h3>
                <p style={{ color: "var(--text-secondary)", fontSize: "0.875rem", maxWidth: "460px", margin: "8px auto 20px" }}>
                  The AI Investigation Agent inspects dimensional telemetry, compares against baselines, and builds evidence-backed root cause hypotheses.
                </p>
                <button 
                  onClick={handleTriggerInvestigate} 
                  disabled={actionLoading}
                  className="btn btn-primary"
                >
                  <Sparkles style={{ width: "16px", height: "16px" }} />
                  <span>{actionLoading ? "Investigating..." : "Launch AI Investigation"}</span>
                </button>
              </div>
            )}
          </div>

          {/* Side Info: Impact & Next Steps */}
          <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
            {/* Impact Calculation Transparency */}
            <div className="card">
              <h3 className="card-title" style={{ fontSize: "0.9375rem" }}>
                <IndianRupee style={{ width: "16px", height: "16px", color: "var(--status-warning)" }} />
                <span>Explainable Impact Formula</span>
              </h3>
              <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "10px", fontSize: "0.8125rem" }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)" }}>
                  <span>Affected Transactions:</span>
                  <span style={{ fontWeight: "600", color: "var(--text-primary)" }}>{incident.affected_transaction_count}</span>
                </div>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--text-secondary)" }}>
                  <span>Est. Revenue Exposure:</span>
                  <span style={{ fontWeight: "700", color: "#FBBF24" }}>
                    ₹{Number(incident.estimated_exposure || 0).toLocaleString("en-IN")}
                  </span>
                </div>
                <div style={{ padding: "10px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-sm)", fontSize: "0.7rem", color: "var(--text-muted)", lineHeight: "1.4" }}>
                  Formula: <code style={{ color: "var(--accent-primary)" }}>exposure = incremental_failures × avg_txn_value</code>
                  <br />
                  Documented estimate — not guaranteed lost revenue.
                </div>
              </div>
            </div>

            {/* Next Recommended Steps */}
            {report?.next_steps && (
              <div className="card">
                <h3 className="card-title" style={{ fontSize: "0.9375rem" }}>
                  <Play style={{ width: "16px", height: "16px", color: "var(--accent-primary)" }} />
                  <span>Action Next Steps</span>
                </h3>
                <ol style={{ paddingLeft: "18px", marginTop: "10px", display: "flex", flexDirection: "column", gap: "6px", fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                  {report.next_steps.map((step: string, idx: number) => (
                    <li key={idx}>{step}</li>
                  ))}
                </ol>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: Anomalous Segments */}
      {activeTab === "segments" && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <Layers style={{ width: "18px", height: "18px", color: "var(--accent-primary)" }} />
                <span>Multi-Dimensional Anomaly Breakdown</span>
              </h2>
              <p className="card-subtitle">Statistical deviation from 7-day rolling baselines</p>
            </div>
          </div>

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Dimension</th>
                  <th>Segment Value</th>
                  <th>Observed Rate</th>
                  <th>Baseline Rate</th>
                  <th>Deviation</th>
                  <th>Z-Score</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {incident.signals && incident.signals.length > 0 ? (
                  incident.signals.map((sig: any, idx: number) => (
                    <tr key={idx}>
                      <td style={{ textTransform: "capitalize", fontWeight: "600" }}>{sig.dimension.replace("_", " ")}</td>
                      <td style={{ fontWeight: "700", color: "#60A5FA" }}>{sig.dimension_value}</td>
                      <td style={{ color: sig.current_rate < 0.8 ? "#F87171" : "inherit" }}>
                        {(sig.current_rate * 100).toFixed(1)}%
                      </td>
                      <td style={{ color: "var(--text-muted)" }}>{(sig.baseline_rate * 100).toFixed(1)}%</td>
                      <td>
                        <span style={{ color: "#F87171", fontWeight: "600" }}>
                          +{Math.abs(sig.deviation_pct).toFixed(1)}% failures
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-high" style={{ fontSize: "0.7rem" }}>
                          z = {Number(sig.z_score || 0).toFixed(2)}
                        </span>
                      </td>
                      <td style={{ color: "var(--text-secondary)" }}>{sig.transaction_count} txns</td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={7} style={{ textAlign: "center", padding: "30px", color: "var(--text-muted)" }}>
                      No dimensional signals stored yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* TAB 3: Incident Timeline */}
      {activeTab === "timeline" && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <Clock style={{ width: "18px", height: "18px", color: "var(--accent-primary)" }} />
                <span>Incident Timeline & Audit Trail</span>
              </h2>
              <p className="card-subtitle">Complete chronological sequence of events</p>
            </div>
          </div>

          <div style={{ position: "relative", paddingLeft: "24px", display: "flex", flexDirection: "column", gap: "20px" }}>
            <div style={{ position: "absolute", left: "7px", top: "10px", bottom: "10px", width: "2px", background: "var(--border-medium)" }} />
            
            {timeline.map((evt, idx) => (
              <div key={idx} style={{ position: "relative", display: "flex", flexDirection: "column", gap: "4px" }}>
                <div style={{
                  position: "absolute",
                  left: "-21px",
                  top: "4px",
                  width: "10px",
                  height: "10px",
                  borderRadius: "50%",
                  background: evt.action.includes("RESOLVED") || evt.action.includes("APPROVED") ? "#10B981" : "#3B82F6",
                  border: "2px solid var(--bg-surface)"
                }} />
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ fontSize: "0.75rem", fontFamily: "var(--font-mono)", color: "var(--text-muted)" }}>
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                  <span className="badge badge-low" style={{ fontSize: "0.65rem", padding: "1px 6px" }}>
                    {evt.actor}
                  </span>
                  <span style={{ fontWeight: "600", fontSize: "0.875rem", color: "var(--text-primary)" }}>
                    {evt.action}
                  </span>
                </div>
                <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginLeft: "0" }}>
                  {evt.description || evt.result}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: Post-Action Verification */}
      {activeTab === "verification" && (
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <CheckCircle2 style={{ width: "18px", height: "18px", color: "var(--status-success)" }} />
                <span>Closed-Loop Verification</span>
              </h2>
              <p className="card-subtitle">Empirical measurement of action outcome</p>
            </div>
          </div>

          {incident.action_result ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
                gap: "16px"
              }}>
                <div style={{ padding: "16px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Outcome Result</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "#34D399", marginTop: "4px" }}>
                    {incident.action_result.verification_result}
                  </div>
                </div>
                <div style={{ padding: "16px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Pre-Action Success</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "#F87171", marginTop: "4px" }}>
                    {(incident.action_result.success_rate_before * 100).toFixed(1)}%
                  </div>
                </div>
                <div style={{ padding: "16px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Post-Action Success</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "#34D399", marginTop: "4px" }}>
                    {(incident.action_result.success_rate_after * 100).toFixed(1)}%
                  </div>
                </div>
                <div style={{ padding: "16px", background: "var(--bg-surface-elevated)", borderRadius: "var(--radius-md)" }}>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>Absolute Improvement</div>
                  <div style={{ fontSize: "1.25rem", fontWeight: "700", color: "var(--accent-primary)", marginTop: "4px" }}>
                    +{(incident.action_result.absolute_improvement * 100).toFixed(1)}pp
                  </div>
                </div>
              </div>

              {/* Before vs After Chart */}
              <div style={{ height: "200px", width: "100%", marginTop: "10px" }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={[
                    { stage: "Before Action", rate: incident.action_result.success_rate_before },
                    { stage: "After Action", rate: incident.action_result.success_rate_after },
                  ]}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                    <XAxis dataKey="stage" stroke="var(--text-secondary)" />
                    <YAxis domain={[0, 1]} tickFormatter={(v) => `${(v*100).toFixed(0)}%`} stroke="var(--text-muted)" />
                    <Tooltip formatter={(v: any) => [`${(Number(v)*100).toFixed(1)}%`, "Success Rate"]} />
                    <Bar dataKey="rate" radius={[6, 6, 0, 0]}>
                      <Cell fill="#EF4444" />
                      <Cell fill="#10B981" />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "40px 20px", color: "var(--text-muted)" }}>
              No action executed yet. Approve the pending recommendation above to trigger the verification loop.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
