"use client";

import { useState } from "react";
import { Play, Sparkles, RefreshCw, AlertCircle, CheckCircle } from "lucide-react";

export default function Header() {
  const [demoRunning, setDemoRunning] = useState(false);
  const [demoStatus, setDemoStatus] = useState<string | null>(null);
  const [isDetecting, setIsDetecting] = useState(false);

  const handleRunDemo = async () => {
    try {
      setDemoRunning(true);
      setDemoStatus("Demo scenario initializing...");
      const res = await fetch("/api/simulator/demo", { method: "POST" });
      const data = await res.json();
      setDemoStatus("Scenario running (UPI Degradation → AI Investigation → Auto Action)");
      setTimeout(() => {
        setDemoRunning(false);
        setDemoStatus(null);
        window.location.reload();
      }, 5000);
    } catch (e) {
      setDemoStatus("Demo trigger failed");
      setDemoRunning(false);
    }
  };

  const handleTriggerDetection = async () => {
    try {
      setIsDetecting(true);
      const res = await fetch("/api/simulator/detect", { method: "POST" });
      const data = await res.json();
      alert(data.message || "Detection complete");
      window.location.reload();
    } catch (e) {
      alert("Detection failed");
    } finally {
      setIsDetecting(false);
    }
  };

  return (
    <header className="header">
      {/* Merchant Title & Status */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontWeight: "700", fontSize: "0.9375rem" }}>DemoMart Online</span>
            <span className="badge badge-low" style={{ fontSize: "0.65rem", padding: "2px 8px" }}>E-Commerce</span>
          </div>
          <p style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "2px" }}>
            Merchant ID: <span style={{ fontFamily: "var(--font-mono)", color: "var(--text-secondary)" }}>demo_merchant_in</span>
          </p>
        </div>
      </div>

      {/* Action Controls: Detection & Demo Mode */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        {demoStatus && (
          <div style={{ fontSize: "0.75rem", color: "var(--status-warning)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span className="live-indicator danger" />
            <span>{demoStatus}</span>
          </div>
        )}

        <button
          onClick={handleTriggerDetection}
          disabled={isDetecting}
          className="btn btn-secondary btn-sm"
          title="Run statistical anomaly detection over last 30 minutes"
        >
          <RefreshCw style={{ width: "14px", height: "14px", animation: isDetecting ? "spin 1s infinite linear" : "none" }} />
          <span>{isDetecting ? "Scanning..." : "Scan Anomalies"}</span>
        </button>

        <button
          onClick={handleRunDemo}
          disabled={demoRunning}
          className="btn btn-primary btn-sm"
          style={{ background: "linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%)", boxShadow: "0 4px 14px rgba(139, 92, 246, 0.4)" }}
          title="One-click full incident resolution story for hackathon demo"
        >
          <Sparkles style={{ width: "14px", height: "14px" }} />
          <span>{demoRunning ? "Running Demo Story..." : "One-Click Demo"}</span>
        </button>
      </div>
    </header>
  );
}
