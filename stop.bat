@echo off
rem Stop backend (8000) and frontend (5173) listening processes
setlocal enabledelayedexpansion

echo Stopping services on ports 8000 / 5173 ...

for %%P in (8000 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo   killing PID %%A on port %%P
    taskkill /PID %%A /F >nul 2>&1
  )
)

echo Done.
pause
