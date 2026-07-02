@echo off
chcp 65001 >nul
rem Usage: start.bat [playerId] [host] [port]
setlocal

set "PLAYER_ID=%~1"
if "%PLAYER_ID%"=="" set "PLAYER_ID=1001"

set "HOST=%~2"
if "%HOST%"=="" set "HOST=127.0.0.1"

set "PORT=%~3"
if "%PORT%"=="" set "PORT=30000"

cd /d "%~dp0"
where py >nul 2>&1 && (
  py -3 basic_client.py --player-id %PLAYER_ID% --host %HOST% --port %PORT% --player-name python-bot --version 1.0
) || (
  python basic_client.py --player-id %PLAYER_ID% --host %HOST% --port %PORT% --player-name python-bot --version 1.0
)
