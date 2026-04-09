@echo off
echo ========================================
echo Starting All Services
echo ========================================
echo.

echo [1/2] Starting Ollama Service...
start "Ollama Service" powershell -NoExit -Command "cd '%cd%'; Write-Host 'Ollama Service Running...' -ForegroundColor Green; ollama serve"

timeout /t 3 /nobreak >nul

echo [2/2] Starting FastAPI Server...
start "FastAPI Server" powershell -NoExit -Command "cd '%cd%'; Write-Host 'FastAPI Server Running...' -ForegroundColor Cyan; python api_server.py"

timeout /t 5 /nobreak >nul

echo.
echo ========================================
echo Services Started!
echo ========================================
echo.
echo Ollama: http://localhost:11434
echo FastAPI: http://localhost:8000
echo API Docs: http://localhost:8000/docs
echo.
echo Press any key to exit...
pause >nul

