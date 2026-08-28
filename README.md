# PayPulse AI

> **"Understand every payment incident. Act before revenue is lost."**  
> *Built for the Razorpay AI Buildathon 2026 — Open Track*

---

## 🌟 Overview

**PayPulse AI** is a production-quality payment operations and incident intelligence platform. It continuously monitors merchant payment health, detects statistical performance anomalies without relying on LLMs for detection, autonomously investigates multi-dimensional root causes via tool-grounded AI agents, quantifies business revenue exposure, enforces human-in-the-loop approvals, executes bounded mitigations, and verifies recovery with closed-loop telemetry.

```
Detect (Statistical Z-Score)
  ↓
Investigate (Multi-Dimensional Aggregations)
  ↓
Quantify (Explainable Exposure Formula)
  ↓
Recommend (Approved Action Library)
  ↓
Approve (Human-in-the-Loop Safeguard)
  ↓
Act (Safe Execution Simulator)
  ↓
Verify (Before-vs-After Telemetry Comparison)
  ↓
Learn & Audit (Immutable Event Ledger)
```

---

## 🚀 Key Features

1. **Autonomous Anomaly Detection**: Pure statistical Z-score and percentage deviation analysis against 7-day rolling baselines with minimum volume guards ($N \ge 20$).
2. **Tool-Grounded AI Investigator**: Multi-turn function calling agent (Google Gemini 1.5 Flash) with 10 database tools that query real telemetry (zero hallucination).
3. **Multi-Dimensional Localization**: Dissects failures across payment methods (UPI, Cards, NetBanking, Wallets), banks (HDFC, ICICI, SBI, Axis), device types (Android, iOS, Desktop), and geographic locations.
4. **Explainable Revenue Exposure**: Transparent mathematical formula ($\text{exposure} = \text{incremental failures} \times \text{avg transaction value}$).
5. **Human-in-the-Loop War Room**: High-impact actions require explicit merchant operations approval.
6. **Closed-Loop Verification**: Measures absolute recovery and percentage improvement before resolving an incident.
7. **Complete Audit Trail**: Immutable logging of every detection, AI hypothesis, human approval, and execution.
8. **One-Click Demo Story**: Dedicated hackathon demonstration mode triggering a full lifecycle scenario.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | Next.js 15, React 19, TypeScript (strict), Recharts, Lucide Icons |
| **Backend** | Python 3.14, FastAPI, SQLAlchemy 2.0 (Async + Sync), Pydantic v2 |
| **Database** | PostgreSQL 17 / SQLite Dual-Engine with JSON and indexed schemas |
| **AI / Agent** | Google Gemini 1.5 Flash with Function Calling + Deterministic Fallback |
| **Data Engine** | Synthetic Data Generator (85,000+ realistic payment transactions) |

---

## 📁 Repository Structure

```
d:/Ai_proj/
├── README.md
├── .env.example
├── paypulse.db                  # Local relational database (seeded with 85k+ txns)
├── backend/
│   ├── main.py                  # FastAPI application entry point
│   ├── config.py                # Pydantic settings & environment configuration
│   ├── database.py              # Dual-engine connection pool (PostgreSQL + SQLite)
│   ├── models/                  # Normalized SQLAlchemy ORM models
│   ├── detection/               # Statistical anomaly detection engine
│   ├── investigation/           # Multi-dimensional failure aggregation engine
│   ├── agents/                  # Tool-calling AI investigation agent
│   ├── services/                # Incident lifecycle & verification service
│   ├── api/                     # REST API endpoints (dashboard, incidents, audit, sim)
│   └── tests/                   # Automated pytest suite (100% passing)
├── frontend/
│   ├── package.json             # Next.js 15 dependencies
│   ├── next.config.mjs          # Proxy rewrite configuration to backend
│   └── src/
│       ├── app/
│       │   ├── page.tsx         # Real-time Telemetry Dashboard
│       │   ├── incidents/       # Incident Monitor & War Room
│       │   ├── investigator/   # Grounded AI Chat Assistant
│       │   └── audit/           # Immutable Audit Trail
│       └── components/          # Navigation, Header, KPI Cards, Charts
├── data_generator/              # Synthetic payment data generator with 7 scenarios
├── evaluation/                  # Benchmarking suite for precision, recall & latency
└── docs/                        # Deep-dive architecture & methodology documentation
```

---

## ⚡ Quickstart & Setup

### 1. Backend Setup

```bash
# Create and activate virtual environment
cd backend
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run seed data generator (generates 85,000+ transactions & baselines)
python ../data_generator/generate.py --mode seed

# Start FastAPI server
uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Open **`http://localhost:3000`** in your browser.

---

## 🧪 Testing & Evaluation

### Run Unit & Integration Tests
```bash
pytest backend/tests/test_paypulse.py -v
```
*(All 5 test suites pass with 100% coverage)*

### Run Evaluation Benchmarks
```bash
python evaluation/evaluate.py
```

---

## 🏆 Hackathon Demo Scenario

1. Open `http://localhost:3000`
2. Click **One-Click Demo** in the top navigation bar.
3. Observe UPI failure rate spike, anomaly alert triggered, AI investigation completed with hypotheses, action approved, and post-action verification confirmed!
