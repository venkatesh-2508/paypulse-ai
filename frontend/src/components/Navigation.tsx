"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { 
  LayoutDashboard, 
  AlertTriangle, 
  Bot, 
  History, 
  Activity, 
  Zap,
  ShieldCheck,
  CreditCard
} from "lucide-react";

export default function Navigation() {
  const pathname = usePathname();

  const navItems = [
    { name: "Dashboard", href: "/", icon: LayoutDashboard },
    { name: "Incidents", href: "/incidents", icon: AlertTriangle },
    { name: "AI Investigator", href: "/investigator", icon: Bot },
    { name: "Audit Trail", href: "/audit", icon: History },
  ];

  return (
    <aside className="sidebar">
      {/* Brand Header */}
      <div style={{ padding: "8px 12px 24px", borderBottom: "1px solid var(--border-subtle)", marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div style={{ 
            width: "36px", 
            height: "36px", 
            borderRadius: "10px", 
            background: "var(--accent-gradient)", 
            display: "flex", 
            alignItems: "center", 
            justifyContent: "center",
            boxShadow: "0 0 16px rgba(59, 130, 246, 0.5)"
          }}>
            <Activity style={{ color: "#FFFFFF", width: "20px", height: "20px" }} />
          </div>
          <div>
            <h1 style={{ fontSize: "1.125rem", fontWeight: "700", letterSpacing: "-0.02em", color: "#FFFFFF" }}>
              PayPulse <span style={{ color: "var(--accent-primary)", fontSize: "0.85em" }}>AI</span>
            </h1>
            <p style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "-2px" }}>
              Fintech Ops Intelligence
            </p>
          </div>
        </div>
      </div>

      {/* Navigation Links */}
      <nav style={{ display: "flex", flexDirection: "column", gap: "4px", flex: 1 }}>
        <div style={{ fontSize: "0.6875rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--text-muted)", padding: "4px 14px", fontWeight: "600" }}>
          Platform
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-link ${isActive ? "active" : ""}`}
            >
              <Icon style={{ width: "18px", height: "18px" }} />
              <span>{item.name}</span>
            </Link>
          );
        })}
      </nav>

      {/* Razorpay Hackathon Badge */}
      <div style={{ 
        background: "var(--bg-surface-elevated)", 
        padding: "14px", 
        borderRadius: "var(--radius-md)", 
        border: "1px solid var(--border-subtle)",
        display: "flex",
        flexDirection: "column",
        gap: "6px"
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "0.75rem", fontWeight: "600", color: "var(--accent-primary)" }}>
          <ShieldCheck style={{ width: "14px", height: "14px" }} />
          <span>Razorpay AI Buildathon</span>
        </div>
        <p style={{ fontSize: "0.7rem", color: "var(--text-secondary)", lineHeight: "1.3" }}>
          Open Track: Autonomous Payment Incident Resolution
        </p>
      </div>
    </aside>
  );
}
