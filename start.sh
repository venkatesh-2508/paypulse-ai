#!/usr/bin/env bash
set -e

echo "========================================================"
echo "Starting PayPulse AI (Backend + Frontend)"
echo "========================================================"

# Trap SIGINT to kill background processes on exit
trap 'kill $(jobs -p) 2>/dev/null' EXIT

# Start Backend
(
  cd backend
  if [ -d ".venv" ]; then
    source .venv/bin/activate
  fi
  uvicorn main:app --host 0.0.0.0 --port 8000
) &

# Start Frontend
(
  cd frontend
  npm run dev
) &

echo "PayPulse AI is running:"
echo "  Frontend:    http://localhost:3000"
echo "  Backend API: http://localhost:8000"
echo "  API Docs:    http://localhost:8000/docs"
echo "========================================================"

wait
