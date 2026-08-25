@echo off
setlocal EnableExtensions

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

rem Python selection:
rem   1) set PHOTOGRAPHER_PYTHON to override it for this machine;
rem   2) prefer the working vision interpreter used by the native image search;
rem   3) fall back to the legacy project venv for machines that still use it.
set "PYTHON="
if defined PHOTOGRAPHER_PYTHON if exist "%PHOTOGRAPHER_PYTHON%" set "PYTHON=%PHOTOGRAPHER_PYTHON%"
if not defined PYTHON if exist "G:\Python310-embed\python.exe" set "PYTHON=G:\Python310-embed\python.exe"
if not defined PYTHON if exist "%ROOT%\venv-vision\Scripts\python.exe" set "PYTHON=%ROOT%\venv-vision\Scripts\python.exe"
if not defined PYTHON if exist "%ROOT%\venv\Scripts\python.exe" set "PYTHON=%ROOT%\venv\Scripts\python.exe"
set "NPM_CMD="
set "HAS_ERROR="

for /f "delims=" %%I in ('where npm.cmd 2^>nul') do (
  if not defined NPM_CMD set "NPM_CMD=%%I"
)
if not defined NPM_CMD if exist "G:\Pycharm\Nodejs\npm.cmd" set "NPM_CMD=G:\Pycharm\Nodejs\npm.cmd"

if not exist "%PYTHON%" (
  echo [error] Cannot find Python virtual environment:
  echo         Set PHOTOGRAPHER_PYTHON to a working interpreter, for example:
  echo         set PHOTOGRAPHER_PYTHON=G:\Python310-embed\python.exe
  set "HAS_ERROR=1"
)

if not defined NPM_CMD (
  echo [error] Cannot find npm.cmd in PATH.
  set "HAS_ERROR=1"
)

if not exist "%ROOT%\backend\app\main.py" (
  echo [error] Cannot find backend entry: backend\app\main.py
  set "HAS_ERROR=1"
)

if not exist "%ROOT%\frontend\node_modules" (
  echo [error] Cannot find frontend\node_modules. Run npm install in frontend first.
  set "HAS_ERROR=1"
)

if not exist "%ROOT%\admin-frontend\node_modules" (
  echo [error] Cannot find admin-frontend\node_modules. Run npm install in admin-frontend first.
  set "HAS_ERROR=1"
)

if not exist "%ROOT%\mobile-app\node_modules" (
  echo [error] Cannot find mobile-app\node_modules. Run npm install in mobile-app first.
  set "HAS_ERROR=1"
)

if defined HAS_ERROR (
  echo.
  pause
  exit /b 1
)

set "BACKEND_PORT=%PHOTOGRAPHER_BACKEND_PORT%"
if not defined BACKEND_PORT set "BACKEND_PORT=8000"

if not defined PHOTOGRAPHER_BACKEND_PORT if "%BACKEND_PORT%"=="8000" (
  call :port_in_use 8000
  if not errorlevel 1 (
    call :backend_is_healthy 8000
    if errorlevel 1 (
      set "BACKEND_PORT=8001"
      set "BACKEND_PORT_FALLBACK=1"
    )
  )
)
set "PHOTOGRAPHER_BACKEND_PORT=%BACKEND_PORT%"

set "BACKEND_CMD=^"%PYTHON%^" -m uvicorn backend.app.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"
set "FRONTEND_CMD=^"%NPM_CMD%^" run dev -- --host 127.0.0.1 --port 5173 --strictPort"
set "ADMIN_CMD=^"%NPM_CMD%^" run dev -- --host 127.0.0.1 --port 5174 --strictPort"
set "MOBILE_CMD=^"%NPM_CMD%^" run dev -- --host 127.0.0.1 --port 5175 --strictPort"

if /I "%~1"=="--dry-run" (
  echo Project root: %ROOT%
  echo Python: %PYTHON%
  echo Backend port: %BACKEND_PORT%
  echo npm.cmd: %NPM_CMD%
  echo.
  echo Backend:
  echo   %BACKEND_CMD%
  echo Frontend:
  echo   %FRONTEND_CMD%
  echo Admin frontend:
  echo   %ADMIN_CMD%
  echo Mobile app:
  echo   %MOBILE_CMD%
  echo.
  exit /b 0
)

echo Starting photographer-booking development services...
echo.
if defined BACKEND_PORT_FALLBACK echo [info] Port 8000 belongs to another application; using port %BACKEND_PORT% for this project.
echo Backend API:     http://127.0.0.1:%BACKEND_PORT%
echo Backend health:  http://127.0.0.1:%BACKEND_PORT%/health
echo Frontend:        http://127.0.0.1:5173/
echo Admin frontend:  http://127.0.0.1:5174/
echo Mobile app:      http://127.0.0.1:5175/
echo.
echo Service windows will open for any port that is not already listening.
echo Close those windows to stop the services started by this launcher.
echo.

set "STARTED_ANY="

call :port_in_use %BACKEND_PORT%
if not errorlevel 1 (
  call :backend_is_healthy %BACKEND_PORT%
  if not errorlevel 1 (
    echo [skip] Photographer backend is already healthy on port %BACKEND_PORT%.
  ) else (
    echo [error] Port %BACKEND_PORT% is occupied by another service.
    echo         Its /health endpoint did not return the photographer backend response.
    call :show_listening_pid %BACKEND_PORT%
    echo         Stop that process or set PHOTOGRAPHER_BACKEND_PORT to another port.
    set "STARTUP_ERROR=1"
  )
) else (
  echo [start] Backend API on port %BACKEND_PORT%.
  start "Photographer API :%BACKEND_PORT%" /D "%ROOT%" "%ComSpec%" /k "%BACKEND_CMD%"
  set "STARTED_ANY=1"
)

call :port_in_use 5173
if not errorlevel 1 (
  echo [skip] Frontend is already listening on port 5173.
) else (
  echo [start] Frontend on port 5173.
  start "Photographer Web :5173" /D "%ROOT%\frontend" "%ComSpec%" /k "%FRONTEND_CMD%"
  set "STARTED_ANY=1"
)

call :port_in_use 5174
if not errorlevel 1 (
  echo [skip] Admin frontend is already listening on port 5174.
) else (
  echo [start] Admin frontend on port 5174.
  start "Photographer Admin :5174" /D "%ROOT%\admin-frontend" "%ComSpec%" /k "%ADMIN_CMD%"
  set "STARTED_ANY=1"
)

call :port_in_use 5175
if not errorlevel 1 (
  echo [skip] Mobile app is already listening on port 5175.
) else (
  echo [start] Mobile app on port 5175.
  start "Photographer Mobile :5175" /D "%ROOT%\mobile-app" "%ComSpec%" /k "%MOBILE_CMD%"
  set "STARTED_ANY=1"
)

if not defined STARTED_ANY if not defined STARTUP_ERROR (
  echo.
  echo All target ports are already listening.
)

if defined STARTUP_ERROR (
  echo.
  echo One or more services could not be started. See the error above.
  echo.
  pause
  exit /b 1
)

echo Done. You can close this launcher window.
echo.
pause
exit /b 0

:port_in_use
netstat -ano -p tcp | findstr /R /C:":%~1 .*LISTENING" >nul
exit /b %ERRORLEVEL%

:backend_is_healthy
curl.exe -fsS --max-time 3 http://127.0.0.1:%~1/health 2>nul | findstr /C:"\"status\":\"ok\"" >nul
exit /b %ERRORLEVEL%

:show_listening_pid
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /R /C:":%~1 .*LISTENING"') do (
  echo         Listening PID: %%P
  exit /b 0
)
exit /b 1
