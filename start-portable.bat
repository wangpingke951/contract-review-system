@echo off
rem ============================================================
rem  Contract Review System - single-port mode (pure ASCII)
rem  Builds the frontend, then serves everything from :8000
rem  Requires SERVE_FRONTEND=true in backend\.env
rem ============================================================
setlocal
set "ROOT=%~dp0"

echo.
echo  [1/2] Building frontend...
echo.

if not exist "%ROOT%frontend\node_modules" (
  echo  [ERROR] frontend\node_modules not found.
  echo  Run: cd frontend ^&^& npm install
  pause
  exit /b 1
)

pushd "%ROOT%frontend"
node node_modules\vite\bin\vite.js build
if errorlevel 1 (
  echo.
  echo  [ERROR] frontend build failed.
  popd
  pause
  exit /b 1
)
popd

if not exist "%ROOT%backend\.venv\Scripts\python.exe" (
  echo.
  echo  [ERROR] backend\.venv not found.
  pause
  exit /b 1
)

echo.
echo  [2/2] Starting server on http://127.0.0.1:8000
echo.
pushd "%ROOT%backend"
start "contract-review" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
popd

echo  Done. Open http://localhost:8000
echo  Login: admin / admin123
echo.
echo  Note: SERVE_FRONTEND must be true in backend\.env
echo.
pause
