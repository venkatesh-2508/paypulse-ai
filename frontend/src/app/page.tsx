"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  CheckCircle2, 
  IndianRupee, 
  CreditCard,
  ArrowRight,
  ShieldAlert,
  Zap,
  Activity
} from "lucide-react";
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  Tooltip, 
  ResponsiveContainer, 
  BarChart, 
  Bar, 
  Cell,
  CartesianGrid
} from "recharts";

interface DashboardData {
  current_success_rate: number;
  current_failure_rate: number;
  baseline_success_rate: number;
  transactions_last_30m: number;
  transactions_last_24h: number;
  active_incidents: number;
  resolved_incidents: number;
  estimated_revenue_exposure: number;
  is_degraded: boolean;
  success_rate_trend: Array<{
    timestamp: string;
    success_rate: number;
    failure_rate: number;
    total: number;
  }>;
  payment_method_breakdown: Array<{
    method: string;
    total: number;
    success_rate: number;
    failure_rate: number;
  }>;
  timestamp: string;
}

interface IncidentItem {
  id: string;
  severity: string;
  status: string;
  title: string;
  start_time: string;
  current_success_rate: number;
  baseline_success_rate: number;
  estimated_exposure: number;
}

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [incidents, setIncidents] = useState<IncidentItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = async () => {
    try {
      const [dashRes, incRes] = await Promise.all([
        fetch("/api/dashboard"),
        fetch("/api/incidents?limit=5")
      ]);
      if (dashRes.ok) {
        const d = await dashRes.json();
        setData(d);
      }
      if (incRes.ok) {
        const i = await incRes.json();
        setIncidents(i.incidents || []);
      }
    } catch (e) {
      console.error("Dashboard fetch error", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
    const interval = setInterval(fetchDashboard, 8000); // 8s live polling
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-muted)" }}>
        <Activity style={{ animation: "spin 2s infinite linear", margin: "0 auto 12px" }} />
        <p>Loading real-time payment telemetry...</p>
      </div>
    );
  }

  const successPct = data ? (data.current_success_rate * 100).toFixed(1) : "94.2";
  const baselinePct = data ? (data.baseline_success_rate * 100).toFixed(1) : "94.5";
  const failurePct = data ? (data.current_failure_rate * 100).toFixed(1) : "5.8";
  const isHealthy = data ? !data.is_degraded : true;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "28px" }}>
      {/* Alert Banner if Degraded */}
      {!isHealthy && (
        <div style={{
          background: "linear-gradient(90deg, rgba(239, 68, 68, 0.15) 0%, rgba(239, 68, 68, 0.05) 100%)",
          border: "1px solid rgba(239, 68, 68, 0.4)",
          borderRadius: "var(--radius-md)",
          padding: "16px 20px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          boxShadow: "0 0 20px rgba(239, 68, 68, 0.15)"
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
            <span className="live-indicator danger" />
            <div>
              <div style={{ fontWeight: "700", color: "#F87171", fontSize: "0.9375rem" }}>
                Payment Incident in Progress — Performance Degraded
              </div>
              <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "2px" }}>
                Success rate dropped to {successPct}% (Expected baseline: {baselinePct}%). AI investigation and mitigation ready.
              </p>
            </div>
          </div>
          <Link href="/incidents" className="btn btn-danger btn-sm">
            <span>View Incident & Take Action</span>
            <ArrowRight style={{ width: "14px", height: "14px" }} />
          </Link>
        </div>
      )}

      {/* KPI Cards Grid */}
      <div style={{ 
        display: "grid", 
        gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", 
        gap: "18px" 
      }}>
        {/* Success Rate */}
        <div className="card">
          <div className="metric-box">
            <div className="metric-label">
              <Activity style={{ width: "16px", height: "16px", color: isHealthy ? "var(--status-success)" : "var(--status-danger)" }} />
              <span>Payment Success Rate</span>
            </div>
            <div className="metric-value" style={{ color: isHealthy ? "var(--status-success)" : "#F87171" }}>
              {successPct}%
            </div>
            <div className="metric-subtext">
              {isHealthy ? (
                <span style={{ color: "var(--status-success)", display: "flex", alignItems: "center", gap: "3px" }}>
                  <TrendingUp style={{ width: "13px", height: "13px" }} /> In line with baseline ({baselinePct}%)
                </span>
              ) : (
                <span style={{ color: "var(--status-danger)", display: "flex", alignItems: "center", gap: "3px" }}>
                  <TrendingDown style={{ width: "13px", height: "13px" }} /> -{(Number(baselinePct) - Number(successPct)).toFixed(1)}% vs baseline
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Failure Rate */}
        <div className="card">
          <div className="metric-box">
            <div className="metric-label">
              <AlertTriangle style={{ width: "16px", height: "16px", color: "var(--status-warning)" }} />
              <span>Current Failure Rate</span>
            </div>
            <div className="metric-value">
              {failurePct}%
            </div>
            <div className="metric-subtext">
              <span>Past 30 minutes window</span>
            </div>
          </div>
        </div>

        {/* Estimated Revenue Exposure */}
        <div className="card">
          <div className="metric-box">
            <div className="metric-label">
              <IndianRupee style={{ width: "16px", height: "16px", color: "var(--status-warning)" }} />
              <span>Est. Revenue Exposure</span>
            </div>
            <div className="metric-value" style={{ color: data?.estimated_revenue_exposure ? "#FBBF24" : "var(--text-primary)" }}>
              ₹{data?.estimated_revenue_exposure ? data.estimated_revenue_exposure.toLocaleString("en-IN") : "0"}
            </div>
            <div className="metric-subtext">
              <span>Unrecovered failed volume</span>
            </div>
          </div>
        </div>

        {/* Active Incidents */}
        <div className="card">
          <div className="metric-box">
            <div className="metric-label">
              <ShieldAlert style={{ width: "16px", height: "16px", color: data?.active_incidents ? "var(--status-danger)" : "var(--status-success)" }} />
              <span>Active Incidents</span>
            </div>
            <div className="metric-value">
              {data?.active_incidents || 0}
            </div>
            <div className="metric-subtext">
              <span style={{ color: "var(--status-success)" }}>{data?.resolved_incidents || 0} resolved today</span>
            </div>
          </div>
        </div>

        {/* Transactions (24h) */}
        <div className="card">
          <div className="metric-box">
            <div className="metric-label">
              <CreditCard style={{ width: "16px", height: "16px", color: "var(--accent-primary)" }} />
              <span>Transactions (24h)</span>
            </div>
            <div className="metric-value">
              {data?.transactions_last_24h ? data.transactions_last_24h.toLocaleString("en-IN") : "0"}
            </div>
            <div className="metric-subtext">
              <span>{data?.transactions_last_30m || 0} in last 30m</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Charts Row */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "20px" }}>
        {/* Payment Success Trend Line Chart */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <Activity style={{ width: "18px", height: "18px", color: "var(--accent-primary)" }} />
                <span>Payment Performance Telemetry</span>
              </h2>
              <p className="card-subtitle">Real-time rolling success rate (10-minute buckets)</p>
            </div>
            <span className="badge badge-low">
              <span className="live-indicator" /> Live
            </span>
          </div>

          <div style={{ height: "260px", width: "100%", marginTop: "10px" }}>
            {data?.success_rate_trend && data.success_rate_trend.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.success_rate_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" vertical={false} />
                  <XAxis 
                    dataKey="timestamp" 
                    tickFormatter={(val) => {
                      try {
                        return new Date(val).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                      } catch {
                        return "";
                      }
                    }}
                    stroke="var(--text-muted)"
                    fontSize={11}
                  />
                  <YAxis 
                    domain={[0.4, 1.0]} 
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    stroke="var(--text-muted)"
                    fontSize={11}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "var(--bg-surface-elevated)", 
                      borderColor: "var(--border-medium)", 
                      borderRadius: "8px", 
                      color: "var(--text-primary)" 
                    }}
                    formatter={(value: any) => [`${(Number(value) * 100).toFixed(1)}%`, "Success Rate"]}
                    labelFormatter={(label) => new Date(label).toLocaleTimeString()}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="success_rate" 
                    stroke="#3B82F6" 
                    strokeWidth={2.5}
                    dot={{ fill: '#3B82F6', r: 3 }}
                    activeDot={{ r: 6, fill: '#60A5FA' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
                Telemetry data calculating...
              </div>
            )}
          </div>
        </div>

        {/* Payment Method Breakdown Bar Chart */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">
                <CreditCard style={{ width: "18px", height: "18px", color: "var(--status-purple)" }} />
                <span>Payment Methods</span>
              </h2>
              <p className="card-subtitle">Success rate by method</p>
            </div>
          </div>

          <div style={{ height: "260px", width: "100%", marginTop: "10px" }}>
            {data?.payment_method_breakdown && data.payment_method_breakdown.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart 
                  layout="vertical" 
                  data={data.payment_method_breakdown}
                  margin={{ left: 10, right: 20 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border-subtle)" horizontal={false} />
                  <XAxis 
                    type="number" 
                    domain={[0, 1]} 
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    stroke="var(--text-muted)"
                    fontSize={10}
                  />
                  <YAxis 
                    type="category" 
                    dataKey="method" 
                    stroke="var(--text-secondary)"
                    fontSize={11}
                    width={75}
                  />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "var(--bg-surface-elevated)", 
                      borderColor: "var(--border-medium)", 
                      borderRadius: "8px" 
                    }}
                    formatter={(v: any) => [`${(Number(v) * 100).toFixed(1)}%`, "Success Rate"]}
                  />
                  <Bar dataKey="success_rate" radius={[0, 4, 4, 0]}>
                    {data.payment_method_breakdown.map((entry, index) => (
                      <Cell 
                        key={`cell-${index}`} 
                        fill={entry.success_rate < 0.8 ? "#EF4444" : entry.success_rate < 0.9 ? "#F59E0B" : "#10B981"} 
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-muted)" }}>
                Loading methods...
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Incidents Table View */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <AlertTriangle style={{ width: "18px", height: "18px", color: "var(--status-warning)" }} />
              <span>Recent Payment Incidents</span>
            </h2>
            <p className="card-subtitle">Automated detections and human-in-the-loop approvals</p>
          </div>
          <Link href="/incidents" style={{ fontSize: "0.8125rem", color: "var(--accent-primary)", display: "flex", alignItems: "center", gap: "4px" }}>
            <span>View All Incidents</span>
            <ArrowRight style={{ width: "14px", height: "14px" }} />
          </Link>
        </div>

        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Incident</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Success Rate</th>
                <th>Est. Exposure</th>
                <th>Detected At</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {incidents.length > 0 ? (
                incidents.map((inc) => {
                  const sevClass = `badge-${inc.severity.toLowerCase()}`;
                  return (
                    <tr key={inc.id}>
                      <td>
                        <div style={{ fontWeight: "600", color: "var(--text-primary)" }}>{inc.title}</div>
                        <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
                          ID: {inc.id.slice(0, 8)}...
                        </div>
                      </td>
                      <td>
                        <span className={`badge ${sevClass}`}>
                          <span className="badge-dot" />
                          {inc.severity}
                        </span>
                      </td>
                      <td>
                        <span className={`badge ${inc.status === 'RESOLVED' ? 'badge-success' : 'badge-warning'}`}>
                          {inc.status}
                        </span>
                      </td>
                      <td>
                        <span style={{ fontWeight: "600", color: inc.current_success_rate < 0.85 ? "#F87171" : "inherit" }}>
                          {(inc.current_success_rate * 100).toFixed(1)}%
                        </span>
                        <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginLeft: "4px" }}>
                          (base: {(inc.baseline_success_rate * 100).toFixed(1)}%)
                        </span>
                      </td>
                      <td style={{ fontWeight: "600", color: "#FBBF24" }}>
                        ₹{Number(inc.estimated_exposure || 0).toLocaleString("en-IN")}
                      </td>
                      <td style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
                        {new Date(inc.start_time).toLocaleTimeString()}
                      </td>
                      <td>
                        <Link href={`/incidents/${inc.id}`} className="btn btn-secondary btn-sm">
                          <span>Investigate</span>
                          <ArrowRight style={{ width: "12px", height: "12px" }} />
                        </Link>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={7} style={{ textAlign: "center", color: "var(--text-muted)", padding: "32px" }}>
                    No incidents recorded. System running normally.
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
