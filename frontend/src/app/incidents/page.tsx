"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  AlertTriangle, 
  Filter, 
  ArrowRight, 
  Search, 
  Calendar,
  Clock,
  IndianRupee,
  Activity,
  CheckCircle2,
  AlertCircle
} from "lucide-react";

interface Incident {
  id: string;
  merchant_name: string;
  severity: string;
  status: string;
  title: string;
  start_time: string;
  detected_at: string;
  resolved_at: string | null;
  current_success_rate: number;
  baseline_success_rate: number;
  affected_transaction_count: number;
  estimated_exposure: number;
  duration_minutes: number;
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState<string>("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const [searchTerm, setSearchTerm] = useState<string>("");

  const fetchIncidents = async () => {
    try {
      let url = "/api/incidents?limit=50";
      if (severityFilter) url += `&severity=${severityFilter}`;
      if (statusFilter) url += `&status=${statusFilter}`;

      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setIncidents(data.incidents || []);
      }
    } catch (e) {
      console.error("Failed to fetch incidents", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [severityFilter, statusFilter]);

  const filteredIncidents = incidents.filter(inc => 
    inc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    inc.id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Page Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <h1 style={{ fontSize: "1.5rem", fontWeight: "700", color: "#FFFFFF" }}>
            Payment Incident Monitor
          </h1>
          <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "4px" }}>
            Autonomous anomaly detection, dimensional analysis, and human-supervised mitigation.
          </p>
        </div>
      </div>

      {/* Filters Bar */}
      <div className="card" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: "14px", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "12px", flex: 1, minWidth: "260px" }}>
            <div style={{ position: "relative", width: "100%" }}>
              <Search style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", width: "16px", height: "16px", color: "var(--text-muted)" }} />
              <input
                type="text"
                placeholder="Search incidents by title or ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                style={{
                  width: "100%",
                  padding: "9px 12px 9px 38px",
                  background: "var(--bg-surface-elevated)",
                  border: "1px solid var(--border-subtle)",
                  borderRadius: "var(--radius-md)",
                  color: "var(--text-primary)",
                  fontSize: "0.875rem",
                  outline: "none",
                }}
              />
            </div>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            {/* Severity Filter */}
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              style={{
                padding: "8px 12px",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-primary)",
                fontSize: "0.8125rem",
                cursor: "pointer",
              }}
            >
              <option value="">All Severities</option>
              <option value="CRITICAL">Critical</option>
              <option value="HIGH">High</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                padding: "8px 12px",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-primary)",
                fontSize: "0.8125rem",
                cursor: "pointer",
              }}
            >
              <option value="">All Statuses</option>
              <option value="DETECTED">Detected</option>
              <option value="INVESTIGATING">Investigating</option>
              <option value="ACTION_REQUIRED">Action Required</option>
              <option value="MITIGATING">Mitigating</option>
              <option value="MONITORING">Monitoring</option>
              <option value="RESOLVED">Resolved</option>
              <option value="ESCALATED">Escalated</option>
            </select>
          </div>
        </div>
      </div>

      {/* Incidents Table Card */}
      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Incident Details</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Success Rate Drop</th>
                <th>Est. Revenue Exposure</th>
                <th>Timeline</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                    Loading incident repository...
                  </td>
                </tr>
              ) : filteredIncidents.length > 0 ? (
                filteredIncidents.map((inc) => {
                  const sevClass = `badge-${inc.severity.toLowerCase()}`;
                  const isResolved = inc.status === "RESOLVED";
                  const dropPp = ((inc.baseline_success_rate - inc.current_success_rate) * 100).toFixed(1);

                  return (
                    <tr key={inc.id}>
                      <td style={{ maxWidth: "340px" }}>
                        <div style={{ fontWeight: "600", color: "#FFFFFF", fontSize: "0.9375rem" }}>
                          {inc.title}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "4px", fontFamily: "var(--font-mono)" }}>
                          UUID: {inc.id}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${sevClass}`}>
                          <span className="badge-dot" />
                          {inc.severity}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${isResolved ? 'badge-success' : 'badge-warning'}`}>
                          {inc.status}
                        </span>
                      </td>
                      <td>
                        <div>
                          <span style={{ fontWeight: "700", color: "#F87171" }}>
                            {(inc.current_success_rate * 100).toFixed(1)}%
                          </span>
                          <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "4px" }}>
                            (base: {(inc.baseline_success_rate * 100).toFixed(1)}%)
                          </span>
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "#F87171", marginTop: "2px" }}>
                          ↓ {dropPp}% decline
                        </div>
                      </td>
                      <td>
                        <div style={{ fontWeight: "700", color: "#FBBF24", fontSize: "0.9375rem" }}>
                          ₹{Number(inc.estimated_exposure || 0).toLocaleString("en-IN")}
                        </div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
                          {inc.affected_transaction_count} failed txns
                        </div>
                      </td>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                          <Clock style={{ width: "13px", height: "13px", color: "var(--text-muted)" }} />
                          <span>{new Date(inc.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "2px" }}>
                          {new Date(inc.start_time).toLocaleDateString()}
                        </div>
                      </td>
                      <td>
                        <Link 
                          href={`/incidents/${inc.id}`}
                          className="btn btn-primary btn-sm"
                          style={{ whiteSpace: "nowrap" }}
                        >
                          <span>Open War Room</span>
                          <ArrowRight style={{ width: "13px", height: "13px" }} />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                    No matching incidents found. Click "One-Click Demo" or "Scan Anomalies" to trigger an incident.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
