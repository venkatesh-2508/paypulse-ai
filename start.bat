@echo off
echo ========================================================
echo Starting PayPulse AI (Backend + Frontend)
echo ========================================================

start "PayPulse AI Backend" cmd /k "cd backend && .venv\Scripts\activate && uvicorn main:app --reload --port 8000"
start "PayPulse AI Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo PayPulse AI is starting!
echo Frontend: http://localhost:3000
echo Backend API: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo ========================================================
