Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "          THEOGEN ELECTORAL - INICIO RÁPIDO LOCAL" -ForegroundColor Cyan
Write-Host "     Participación transparente y verificable (MVP Demo)" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$rootPath = $PSScriptRoot

Write-Host "[1/2] Iniciando Servidor Backend FastAPI en http://localhost:8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootPath\backend'; .\venv\Scripts\python.exe main.py"

Start-Sleep -Seconds 3

Write-Host "[2/2] Iniciando Frontend React + Vite en http://localhost:5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$rootPath\frontend'; npm run dev"

Write-Host ""
Write-Host "Plataforma TheoGen Electoral ejecutándose con éxito:" -ForegroundColor Yellow
Write-Host " - Frontend Web:    http://localhost:5173" -ForegroundColor White
Write-Host " - Sala de Votación: http://localhost:5173/votar" -ForegroundColor White
Write-Host " - Swagger API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host " - Usuario Admin:    admin@theogen.cl / admin123" -ForegroundColor White
Write-Host " - Comisión:         comision@theogen.cl / comision123" -ForegroundColor White
Write-Host ""
