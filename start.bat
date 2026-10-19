@echo off
rem ============================================================
rem  Contract Review System - local dev launcher (pure ASCII)
rem  Backend : FastAPI  http://127.0.0.1:8000
rem  Frontend: Vite     http://localhost:5173
rem ============================================================
setlocal
set "ROOT=%~dp0"

echo.
echo  Contract Review System - starting services...
echo.

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo  [ERROR] backend\.venv not found.
  echo  Create it first: python -m venv backend\.venv
  echo  Then install:    backend\.venv\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)

if not exist "%ROOT%frontend\node_modules" (
  echo  [ERROR] frontend\node_modules not found.
  echo  Run: cd frontend ^&^& npm install
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] node.exe not found in PATH.
  pause
  exit /b 1
)

echo  [1/2] Backend  -^> http://127.0.0.1:8000
pushd "%ROOT%backend"
start "contract-review-backend" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000"
popd

echo  [2/2] Frontend -^> http://localhost:5173
pushd "%ROOT%frontend"
start "contract-review-frontend" cmd /k "node node_modules\vite\bin\vite.js"
popd

echo.
echo  Done. Open http://localhost:5173 in your browser.
echo  Login: admin / admin123   (admin can access knowledge base)
echo         user  / user123
echo.
echo  Note: first backend start may take 5-10 seconds.
echo.
pause
