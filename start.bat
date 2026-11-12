@echo off
cd /d "%~dp0"
echo Starting DCode backend...
start "DCode" cmd /k "cd backend && python -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
timeout /t 5 >nul
start http://127.0.0.1:8000/
echo Dashboard: http://127.0.0.1:8000/
