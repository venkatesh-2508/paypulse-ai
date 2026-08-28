"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  History, 
  Search, 
  Clock, 
  ShieldCheck, 
  UserCheck, 
  CheckCircle, 
  AlertTriangle,
  ArrowRight,
  Filter
} from "lucide-react";

interface AuditEntry {
  id: string;
  incident_id: string | null;
  incident_title: string | null;
  actor: string;
  action: string;
  reason: string | null;
  approval_status: string | null;
  result: string | null;
  metadata: any;
  created_at: string;
}

export default function AuditPage() {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/audit-logs?limit=100");
      if (res.ok) {
        const data = await res.json();
        setLogs(data.audit_logs || []);
      }
    } catch (e) {
      console.error("Failed to fetch audit logs", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs = logs.filter(l => 
    l.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
    l.actor.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (l.reason && l.reason.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (l.result && l.result.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
      {/* Header */}
      <div>
        <h1 style={{ fontSize: "1.5rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "10px" }}>
          <History style={{ color: "var(--accent-primary)", width: "24px", height: "24px" }} />
          <span>System & Incident Audit Trail</span>
        </h1>
        <p style={{ fontSize: "0.875rem", color: "var(--text-secondary)", marginTop: "4px" }}>
          Immutable ledger of detections, AI investigations, human approvals, and simulated executions.
        </p>
      </div>

      {/* Search Bar */}
      <div className="card" style={{ padding: "16px 20px" }}>
        <div style={{ position: "relative", maxWidth: "480px" }}>
          <Search style={{ position: "absolute", left: "12px", top: "50%", transform: "translateY(-50%)", width: "16px", height: "16px", color: "var(--text-muted)" }} />
          <input
            type="text"
            placeholder="Search audit trail by actor, action, or reason..."
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

      {/* Audit Log Table */}
      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Reason / Trigger</th>
                <th>Result & Details</th>
                <th>Linked Incident</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                    Loading audit trail...
                  </td>
                </tr>
              ) : filteredLogs.length > 0 ? (
                filteredLogs.map((log) => {
                  const isHuman = log.actor.includes("@") || log.actor === "USER";
                  return (
                    <tr key={log.id}>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", whiteSpace: "nowrap" }}>
                        <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>
                          {new Date(log.created_at).toLocaleTimeString()}
                        </div>
                        <div style={{ fontSize: "0.7rem", color: "var(--text-muted)" }}>
                          {new Date(log.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${isHuman ? 'badge-warning' : 'badge-low'}`} style={{ fontSize: "0.7rem" }}>
                          {log.actor}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: "600", color: "#60A5FA", fontSize: "0.875rem" }}>
                          {log.action}
                        </span>
                      </td>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", maxWidth: "260px" }}>
                        {log.reason || "—"}
                      </td>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-primary)", maxWidth: "280px" }}>
                        {log.result || "—"}
                      </td>
                      <td>
                        {log.incident_id ? (
                          <Link 
                            href={`/incidents/${log.incident_id}`}
                            style={{ 
                              fontSize: "0.75rem", 
                              color: "var(--accent-primary)", 
                              display: "inline-flex", 
                              alignItems: "center", 
                              gap: "4px",
                              fontFamily: "var(--font-mono)" 
                            }}
                          >
                            <span>{log.incident_id.slice(0, 8)}...</span>
                            <ArrowRight style={{ width: "12px", height: "12px" }} />
                          </Link>
                        ) : (
                          <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>Global</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: "40px", color: "var(--text-muted)" }}>
                    No audit records match your query.
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
