@echo off
chcp 65001 >nul
setlocal

rem One-click local test: server + your Python bot (1001) + official demo (2002)
rem Usage: run_local_test.bat [port] [seed]
rem   set NO_UI=1          skip replay UI
rem   set ROUND_TIMEOUT_MS=200   faster rounds (default 500)

set "ROOT=%~dp0"
set "DEBUG_ROOT=%ROOT%..\official_latest\最新地图和调测包\调测包及赛题相关文档_V4\调测"
set "SERVER_DIR=%DEBUG_ROOT%\server"
set "DEMO_DIR=%DEBUG_ROOT%\demo"
set "PYTHON_CLIENT=%ROOT%start.bat"

set "PORT=30000"
if not "%~1"=="" set "PORT=%~1"

set "SEED=20260618"
if not "%~2"=="" set "SEED=%~2"

if "%ROUND_TIMEOUT_MS%"=="" set "ROUND_TIMEOUT_MS=500"
if "%WAIT_TIMEOUT_SEC%"=="" set "WAIT_TIMEOUT_SEC=900"

set "SERVER_EXE=%SERVER_DIR%\lychee-arena-server.exe"
set "MATCH_ID=local-debug-l1"

if not exist "%SERVER_EXE%" (
  echo [ERROR] Server not found: "%SERVER_EXE%"
  echo Make sure official_latest\最新地图和调测包 is extracted under the project root.
  exit /b 1
)

if not exist "%PYTHON_CLIENT%" (
  echo [ERROR] Python client not found: "%PYTHON_CLIENT%"
  exit /b 1
)

if not exist "%DEMO_DIR%\start.bat" (
  echo [ERROR] Demo not found: "%DEMO_DIR%\start.bat"
  exit /b 1
)

del /q "%SERVER_DIR%\replay.txt" "%SERVER_DIR%\debug_replay.txt" "%SERVER_DIR%\client_debug.txt" "%SERVER_DIR%\data.csv" "%SERVER_DIR%\log.txt" 2>nul

echo [1/3] Starting server on 127.0.0.1:%PORT% seed=%SEED%
start "lychee-server" /D "%SERVER_DIR%" cmd /c "chcp 65001>nul & lychee-arena-server.exe --mode client-debug --debug-visibility full --seed %SEED% --match-id %MATCH_ID% -p %PORT% -r . -a %ROUND_TIMEOUT_MS% -c 30000 -d 30000"

ping 127.0.0.1 -n 4 >nul

echo [2/3] Starting Python bot player 1001
start "python-bot-1001" /D "%ROOT%" cmd /k call "%PYTHON_CLIENT%" 1001 127.0.0.1 %PORT%

ping 127.0.0.1 -n 2 >nul

echo [3/3] Starting official demo player 2002
start "demo-2002" /D "%DEMO_DIR%" cmd /c call "%DEMO_DIR%\start.bat" 2002 127.0.0.1 %PORT% demo-l1

echo.
echo Waiting for match to finish ^(server\data.csv^)...
echo Watch the "python-bot-1001" window for MOVE / PROCESS / VERIFY / DELIVER logs.

set /a WAITED=0
:wait_loop
if exist "%SERVER_DIR%\data.csv" goto done
ping 127.0.0.1 -n 3 >nul
set /a WAITED+=2
set /a HB=WAITED %% 10
if %HB%==0 echo   elapsed %WAITED%s...
if %WAITED% GEQ %WAIT_TIMEOUT_SEC% goto timeout
goto wait_loop

:done
echo.
echo Match finished. Score:
type "%SERVER_DIR%\data.csv"
echo.
echo Debug outputs:
echo   %SERVER_DIR%\client_debug.txt
echo   %SERVER_DIR%\log.txt
echo   %SERVER_DIR%\replay.txt
if /i not "%NO_UI%"=="1" (
  if exist "%DEBUG_ROOT%\ui\start-ui.bat" (
    echo Launching replay UI...
    start "lychee-ui" /D "%DEBUG_ROOT%\ui" cmd /c start-ui.bat
  )
)
if /i not "%NO_PAUSE%"=="1" pause
exit /b 0

:timeout
echo [ERROR] Timed out. Check server log: %SERVER_DIR%\log.txt
if /i not "%NO_PAUSE%"=="1" pause
exit /b 1
