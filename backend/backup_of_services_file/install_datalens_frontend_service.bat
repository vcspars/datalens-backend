@echo off
REM ============================================================================
REM DataLens Frontend Service Installation (Windows / NSSM)
REM ============================================================================
REM Installs/updates the Vite preview server as a Windows service.
REM MUST RUN AS ADMINISTRATOR
REM
REM Service name: Datalens-Frontend
REM Command: npm run preview (in the frontend folder)
REM
REM NOTE:
REM - Vite preview is for serving the built dist output.
REM - Make sure you've run `npm run build` in frontend before installing.
REM ============================================================================

setlocal EnableExtensions EnableDelayedExpansion

REM ===== CONFIGURATION =====
set "SERVICE_NAME=Datalens-Frontend"
set "HOST=0.0.0.0"
set "PORT=4173"

REM NSSM path (auto-detect using your Downloads folder)
set "NSSM_64=C:\Users\Mujtaba\Downloads\nssm-2.24\win64\nssm.exe"
set "NSSM_32=C:\Users\Mujtaba\Downloads\nssm-2.24\win32\nssm.exe"
set "NSSM_PATH="
if /i "%PROCESSOR_ARCHITECTURE%"=="AMD64" if exist "%NSSM_64%" set "NSSM_PATH=%NSSM_64%"
if not defined NSSM_PATH if exist "%NSSM_32%" set "NSSM_PATH=%NSSM_32%"
if not defined NSSM_PATH if exist "%NSSM_64%" set "NSSM_PATH=%NSSM_64%"

REM If npm is not on PATH for services, set an absolute path to npm.cmd here, e.g.:
REM set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"
set "NPM_CMD=npm"

REM ===== DERIVED PATHS (relative to this script) =====
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\") do set "PROJECT_ROOT=%%~fI"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
set "STDOUT_LOG=%FRONTEND_DIR%\service_stdout.log"
set "STDERR_LOG=%FRONTEND_DIR%\service_stderr.log"

echo ============================================================================
echo DataLens Frontend Service Installation
echo ============================================================================
echo.
echo Service Name : %SERVICE_NAME%
echo Frontend Dir : %FRONTEND_DIR%
echo NSSM         : %NSSM_PATH%
echo npm          : %NPM_CMD%
echo Host:Port    : %HOST%:%PORT%
echo.

REM ===== VALIDATION =====
if not exist "%FRONTEND_DIR%\" (
  echo [ERROR] Frontend directory not found:
  echo         %FRONTEND_DIR%
  echo.
  pause
  exit /b 1
)

if not exist "%FRONTEND_DIR%\package.json" (
  echo [ERROR] package.json not found in:
  echo         %FRONTEND_DIR%
  echo.
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

REM Use cmd.exe to run npm reliably under a service account
set "APP_EXE=%COMSPEC%"
set "APP_PARAMS=/c ""%NPM_CMD%"" run preview -- --host %HOST% --port %PORT%"

echo [Step 1/4] Stopping and removing old service (if exists)...
"%NSSM_PATH%" stop "%SERVICE_NAME%" >nul 2>&1
timeout /t 2 >nul
"%NSSM_PATH%" remove "%SERVICE_NAME%" confirm >nul 2>&1
echo Done.
echo.

echo [Step 2/4] Installing service...
"%NSSM_PATH%" install "%SERVICE_NAME%" "%APP_EXE%"
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
  /v AppDirectory /t REG_EXPAND_SZ /d "%FRONTEND_DIR%" /f >nul

REM Command parameters
"%NSSM_PATH%" set "%SERVICE_NAME%" AppParameters "%APP_PARAMS%" >nul

REM Logs
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStdout "%STDOUT_LOG%" >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" AppStderr "%STDERR_LOG%" >nul

REM Service behavior
"%NSSM_PATH%" set "%SERVICE_NAME%" Start SERVICE_AUTO_START >nul
"%NSSM_PATH%" set "%SERVICE_NAME%" Description "Datalens Frontend - Vite preview server" >nul
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

