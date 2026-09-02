"use client";

import { Suspense, useEffect, useState, useRef } from "react";
import { useSearchParams } from "next/navigation";
import { 
  Bot, 
  Send, 
  Sparkles, 
  ShieldCheck, 
  AlertTriangle, 
  User, 
  HelpCircle,
  Clock,
  IndianRupee,
  Layers,
  Activity
} from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

interface IncidentOption {
  id: string;
  title: string;
  severity: string;
}

function InvestigatorContent() {
  const searchParams = useSearchParams();
  const initialIncidentId = searchParams.get("incident_id") || "";

  const [incidents, setIncidents] = useState<IncidentOption[]>([]);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(initialIncidentId);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const quickQuestions = [
    "Why did payment success drop?",
    "What is the most affected segment?",
    "What evidence supports the leading hypothesis?",
    "How much transaction value is exposed?",
    "Did the intervention work?",
  ];

  useEffect(() => {
    fetch("/api/incidents?limit=20")
      .then(res => res.json())
      .then(data => {
        const list = data.incidents || [];
        setIncidents(list);
        if (!selectedIncidentId && list.length > 0) {
          setSelectedIncidentId(list[0].id);
        }
      });
  }, []);

  useEffect(() => {
    if (selectedIncidentId) {
      setMessages([
        {
          role: "assistant",
          content: `Hello! I am PayPulse AI Investigator. I have loaded telemetry, baselines, and root cause evidence for Incident **${selectedIncidentId.slice(0, 8)}...**.\n\nAsk me anything about affected segments, temporal onset, statistical hypotheses, or business impact.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      ]);
    }
  }, [selectedIncidentId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (questionText?: string) => {
    const q = questionText || input;
    if (!q.trim() || !selectedIncidentId) return;

    const userMsg: Message = {
      role: "user",
      content: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages(prev => [...prev, userMsg]);
    if (!questionText) setInput("");
    setLoading(true);

    try {
      const res = await fetch(`/api/incidents/${selectedIncidentId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q, incident_id: selectedIncidentId }),
      });
      const data = await res.json();
      
      const assistantMsg: Message = {
        role: "assistant",
        content: data.answer || "I could not retrieve an answer for this incident.",
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e) {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: "Encountered an error while connecting to the investigation engine.",
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "20px", height: "calc(100vh - 120px)" }}>
      {/* Header & Incident Selector */}
      <div className="card" style={{ padding: "16px 20px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: "14px" }}>
          <div>
            <h1 style={{ fontSize: "1.25rem", fontWeight: "700", display: "flex", alignItems: "center", gap: "8px" }}>
              <Bot style={{ color: "var(--accent-primary)", width: "22px", height: "22px" }} />
              <span>Grounded AI Investigator</span>
            </h1>
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)", marginTop: "2px" }}>
              Answers are strictly grounded in application telemetry and statistical baselines (zero hallucination).
            </p>
          </div>

          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <span style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>Target Incident:</span>
            <select
              value={selectedIncidentId}
              onChange={(e) => setSelectedIncidentId(e.target.value)}
              style={{
                padding: "8px 14px",
                background: "var(--bg-surface-elevated)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-md)",
                color: "var(--text-primary)",
                fontSize: "0.8125rem",
                maxWidth: "340px",
                cursor: "pointer",
              }}
            >
              {incidents.map((inc) => (
                <option key={inc.id} value={inc.id}>
                  [{inc.severity}] {inc.title.slice(0, 45)}...
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Quick Prompts Bar */}
      <div style={{ display: "flex", gap: "8px", overflowX: "auto", paddingBottom: "4px" }}>
        {quickQuestions.map((q, idx) => (
          <button
            key={idx}
            onClick={() => handleSend(q)}
            disabled={loading}
            className="btn btn-secondary btn-sm"
            style={{ whiteSpace: "nowrap", fontSize: "0.75rem", padding: "6px 12px" }}
          >
            <Sparkles style={{ width: "12px", height: "12px", color: "var(--accent-primary)" }} />
            <span>{q}</span>
          </button>
        ))}
      </div>

      {/* Chat Messages Container */}
      <div className="card" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", padding: "20px" }}>
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "16px", paddingRight: "8px" }}>
          {messages.map((msg, idx) => {
            const isUser = msg.role === "user";
            return (
              <div
                key={idx}
                style={{
                  display: "flex",
                  gap: "12px",
                  alignSelf: isUser ? "flex-end" : "flex-start",
                  maxWidth: "85%",
                }}
              >
                {!isUser && (
                  <div style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    background: "var(--accent-gradient)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0
                  }}>
                    <Bot style={{ color: "#FFFFFF", width: "18px", height: "18px" }} />
                  </div>
                )}

                <div style={{
                  background: isUser ? "var(--accent-primary)" : "var(--bg-surface-elevated)",
                  color: isUser ? "#FFFFFF" : "var(--text-primary)",
                  padding: "12px 16px",
                  borderRadius: "var(--radius-md)",
                  border: isUser ? "none" : "1px solid var(--border-subtle)",
                  fontSize: "0.875rem",
                  lineHeight: "1.5",
                  whiteSpace: "pre-wrap",
                }}>
                  {msg.content}
                  <div style={{
                    fontSize: "0.65rem",
                    color: isUser ? "rgba(255, 255, 255, 0.7)" : "var(--text-muted)",
                    marginTop: "6px",
                    textAlign: "right"
                  }}>
                    {msg.timestamp}
                  </div>
                </div>

                {isUser && (
                  <div style={{
                    width: "32px",
                    height: "32px",
                    borderRadius: "8px",
                    background: "var(--bg-surface-elevated)",
                    border: "1px solid var(--border-subtle)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0
                  }}>
                    <User style={{ color: "var(--text-secondary)", width: "16px", height: "16px" }} />
                  </div>
                )}
              </div>
            );
          })}
          {loading && (
            <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--text-muted)", fontSize: "0.8125rem" }}>
              <Activity style={{ animation: "spin 1.5s infinite linear", width: "16px", height: "16px" }} />
              <span>Querying telemetry and building grounded response...</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          style={{ marginTop: "16px", display: "flex", gap: "10px" }}
        >
          <input
            type="text"
            placeholder="Ask a question about this incident (e.g. 'What is the top affected bank?')..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
            style={{
              flex: 1,
              padding: "12px 16px",
              background: "var(--bg-surface-elevated)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-md)",
              color: "var(--text-primary)",
              fontSize: "0.875rem",
              outline: "none",
            }}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="btn btn-primary"
            style={{ padding: "0 20px" }}
          >
            <Send style={{ width: "16px", height: "16px" }} />
            <span>Ask</span>
          </button>
        </form>
      </div>
    </div>
  );
}

export default function InvestigatorPage() {
  return (
    <Suspense fallback={<div style={{ padding: "40px", color: "var(--text-muted)" }}>Loading Investigator...</div>}>
      <InvestigatorContent />
    </Suspense>
  );
}

