@echo off
cd /d "%~dp0"
python "%~dp0remap_identity.py"
if errorlevel 1 py -3 "%~dp0remap_identity.py"
if exist "%~dp0review\html\index.html" start "" "%~dp0review\html\index.html"
pause
