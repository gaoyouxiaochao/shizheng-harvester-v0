@echo off
cd /d "%~dp0"
python "%~dp0ensure_deps.py"
if errorlevel 1 py -3 "%~dp0ensure_deps.py"
pause
