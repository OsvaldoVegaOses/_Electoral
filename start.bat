@echo off
echo ============================================================
echo           THEOGEN ELECTORAL - INICIO RAPIDO LOCAL
echo     Participacion transparente y verificable (MVP Demo)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/2] Iniciando Servidor Backend FastAPI (Puerto 8000)...
start "TheoGen Backend API" cmd /k "cd backend && .\venv\Scripts\python.exe main.py"

timeout /t 3 /nobreak >nul

echo [2/2] Iniciando Frontend React + Vite (Puerto 5173)...
start "TheoGen Frontend React" cmd /k "cd frontend && npm run dev"

echo.
echo ============================================================
echo  Plataforma TheoGen Electoral ejecutandose:
echo  - Frontend Web:   http://localhost:5173
echo  - Sala Votacion:  http://localhost:5173/votar
echo  - Swagger API:    http://localhost:8000/docs
echo  - Credenciales:   admin@theogen.cl / admin123
echo ============================================================
echo.
pause
