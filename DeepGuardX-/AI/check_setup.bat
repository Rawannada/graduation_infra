@echo off
echo ========================================
echo Checking Setup
echo ========================================
echo.

echo [1] Checking Ollama...
ollama --version
if %errorlevel% neq 0 (
    echo ERROR: Ollama is not installed!
    pause
    exit /b 1
)

echo.
echo [2] Checking Ollama Service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: Ollama service is not running!
    echo Starting Ollama service...
    start /B ollama serve
    timeout /t 3 /nobreak >nul
)

echo.
echo [3] Checking Required Models...
ollama list | findstr "llama3" >nul
if %errorlevel% neq 0 (
    echo WARNING: llama3 model not found!
    echo Run: ollama pull llama3
)

ollama list | findstr "llama3.2:1b" >nul
if %errorlevel% neq 0 (
    echo WARNING: llama3.2:1b model not found!
    echo Run: ollama pull llama3.2:1b
)

ollama list | findstr "nomic-embed-text" >nul
if %errorlevel% neq 0 (
    echo WARNING: nomic-embed-text model not found!
    echo Run: ollama pull nomic-embed-text
)

echo.
echo [4] Checking FastAPI Server...
curl -s http://localhost:8000/ >nul 2>&1
if %errorlevel% neq 0 (
    echo WARNING: FastAPI server is not running!
    echo Start it with: python api_server.py
) else (
    echo ✅ FastAPI server is running!
)

echo.
echo ========================================
echo Setup Check Complete
echo ========================================
pause

