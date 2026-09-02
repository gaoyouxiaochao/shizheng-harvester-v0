@echo off
cd /d "%~dp0"
python "%~dp0generate_index.py"
if errorlevel 1 py -3 "%~dp0generate_index.py"
if exist "%~dp0review\html\index.html" start "" "%~dp0review\html\index.html"
if not exist "%~dp0review\html\index.html" pause
