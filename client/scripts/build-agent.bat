@echo off
REM Builds the Python agent into an onedir bundle via PyInstaller.
REM Output: client\resources\agent\  (rs-agent.exe + support files)
setlocal

set SCRIPT_DIR=%~dp0
set AGENT_DIR=%SCRIPT_DIR%..\agent
set RESOURCES_DIR=%SCRIPT_DIR%..\resources\agent

echo ==> Building rs-agent.exe (onedir) ...
cd /d "%AGENT_DIR%"

uv sync --no-dev
uv pip install pyinstaller
uv run pyinstaller rs_agent.spec --distpath dist --noconfirm

if exist "%RESOURCES_DIR%" rmdir /s /q "%RESOURCES_DIR%"
mkdir "%RESOURCES_DIR%"
xcopy /e /i /q dist\rs-agent "%RESOURCES_DIR%"

echo ==> Done: %RESOURCES_DIR%
