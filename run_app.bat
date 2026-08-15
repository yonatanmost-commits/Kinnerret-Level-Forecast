@echo off
echo Stopping any process on port 8501...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8501 "') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 1 /nobreak >nul

echo Starting Kinneret Dashboard...
start "" python -m streamlit run "kinneret_app/app.py" --server.port 8501

timeout /t 3 /nobreak >nul
start "" http://localhost:8501
