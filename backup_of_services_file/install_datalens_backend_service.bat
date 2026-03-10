@echo off
REM ============================================================================
REM DataLens Backend Service Installation (Windows / NSSM)
REM ============================================================================
REM Installs/updates the FastAPI backend as a Windows service.
REM MUST RUN AS ADMINISTRATOR
REM
REM Service name: Datalens
REM Runs using THIS PROJECT's venv: backend\venv\Scripts\python.exe
REM
REM NOTE on --reload:
REM - Recommended OFF for services (can spawn extra processes / file watchers).
REM - You can enable by setting USE_RELOAD=1 below.
REM ============================================================================

setlocal EnableExtensions EnableDelayedExpansion

REM ===== CONFIGURATION =====
set "SERVICE_NAME=Datalens"
set "USE_RELOAD=0"
set "HOST=0.0.0.0"
set "PORT=8005"

REM NSSM path (auto-detect using your Downloads folder)
set "NSSM_64=C:\Users\Mujtaba\Downloads\nssm-2.24\win64\nssm.exe"
set "NSSM_32=C:\Users\Mujtaba\Downloads\nssm-2.24\win32\nssm.exe"
set "NSSM_PATH="
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" if exist "%NSSM_64%" set "NSSM_PATH=%NSSM_64%"
if not defined NSSM_PATH if exist "%NSSM_32%" set "NSSM_PATH=%NSSM_32%"
if not defined NSSM_PATH if exist "%NSSM_64%" set "NSSM_PATH=%NSSM_64%"

REM ===== DERIVED PATHS (relative to this script) =====
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\") do set "PROJECT_ROOT=%%~fI"
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "PYTHON_EXE=%BACKEND_DIR%\venv\Scripts\python.exe"
set "STDOUT_LOG=%BACKEND_DIR%\service_stdout.log"
set "STDERR_LOG=%BACKEND_DIR%\service_stderr.log"

echo ============================================================================
echo DataLens Backend Service Installation
echo ============================================================================
echo.
echo Service Name : %SERVICE_NAME%
echo Backend Dir  : %BACKEND_DIR%
echo Python       : %PYTHON_EXE%
echo NSSM         : %NSSM_PATH%
echo Host:Port    : %HOST%:%PORT%
echo Reload       : %USE_RELOAD%
echo.

REM ===== VALIDATION =====
if not exist "%BACKEND_DIR%\" (
  echo [ERROR] Backend directory not found:
  echo         %BACKEND_DIR%
  echo.
  pause
  exit /b 1
)

if not exist "%PYTHON_EXE%" (
  echo [ERROR] Python venv executable not found:
  echo         %PYTHON_EXE%
  echo.
  echo Make sure you created the venv in backend\venv.
  pause
  exit /b 1
)

if not exist "%NSSM_PATH%" (
  echo [ERROR] NSSM not found:
  echo         %NSSM_PATH%
  echo.
  echo Please download NSSM from https://nssm.cc/download or update NSSM_64 / NSSM_32 in this script.
  pause
  exit /b 1
)

REM ===== BUILD UVICORN PARAMETERS =====
set "APP_PARAMS=-m uvicorn app.main:app --host %HOST% --port %PORT%"
if "%USE_RELOAD%"=="1" (
  set "APP_PARAMS=%APP_PARAMS% --reload"
)

echo [Step 1/4] Stopping and removing old service (if exists)...
"%NSSM_PATH%" stop "%SERVICE_NAME%" >nul 2>&1
timeout /t 2 >nul
"%NSSM_PATH%" remove "%SERVICE_NAME%" confirm >nul 2>&1
echo Done.
echo.

echo [Step 2/4] Installing service...
"%NSSM_PATH%" install "%SERVICE_NAME%" "%PYTHON_EXE%"
if errorlevel 1 (
  echo [ERROR] Failed to install service. Are you running as Administrator?
  pause
  exit /b 1
)
echo Service installed.
echo.

echo [Step 3/4] Configuring service...

REM Working directory
reg add "HKLM\SYSTEM\CurrentControlSet\Services\%SERVICE_NAME%\Parameters" ^
  /v AppDirectory /t REG_EXPAND_SZ /d "%BACKEND_DIR%" /f >nul

REM Command parameters
"%NSSM_PATH%" set "%SERVICE_NAME%" AppParameters "%APP_PARAMS%" >nul

REM Logs
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStdout "%STDOUT_LOG%" >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStderr "%STDERR_LOG%" >nul

REM Service behavior
"%NSSM_PATH%" set "%SERVICE_NAME%" Start SERVICE_AUTO_START >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" Description "Datalens Backend - FastAPI (uvicorn)" >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" ObjectName "LocalSystem" >nul

REM Restart behavior
"%NSSM_PATH%" set "%SERVICE_NAME%" AppThrottle 5000 >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" AppExit Default Restart >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" AppRestartDelay 3000 >nul

echo Configuration complete.
echo.

echo [Step 4/4] Starting service...
"%NSSM_PATH%" start "%SERVICE_NAME%"
timeout /t 3 >nul
echo.

echo ============================================================================
echo Status Check
echo ============================================================================
"%NSSM_PATH%" status "%SERVICE_NAME%"
echo.
echo Port %PORT%:
netstat -ano | findstr :%PORT%
echo.
echo Logs (last 20 lines):
echo --- STDOUT ---
powershell -NoProfile -Command "if (Test-Path '%STDOUT_LOG%') { Get-Content '%STDOUT_LOG%' -Tail 20 } else { Write-Host 'No output yet' }"
echo.
echo --- STDERR ---
powershell -NoProfile -Command "if (Test-Path '%STDERR_LOG%') { Get-Content '%STDERR_LOG%' -Tail 20 } else { Write-Host 'No errors' }"
echo.
echo ============================================================================
echo Done.
echo ============================================================================
echo.
echo Service Management:
echo   Status:  "%NSSM_PATH%" status "%SERVICE_NAME%"
echo   Start:   "%NSSM_PATH%" start "%SERVICE_NAME%"
echo   Stop:    "%NSSM_PATH%" stop "%SERVICE_NAME%"
echo   Restart: "%NSSM_PATH%" restart "%SERVICE_NAME%"
echo.
pause

