@echo off
cd /d "%~dp0"
python "%~dp0ensure_deps.py"
if errorlevel 1 py -3 "%~dp0ensure_deps.py"
if errorlevel 1 (
  echo pip install failed
  pause
  exit /b 1
)
cd /d "%~dp0project"
set PYTHONPATH=src
python -m harvest.pipeline
if errorlevel 1 (
  echo harvest failed
  pause
  exit /b 1
)
cd /d "%~dp0"
python "%~dp0generate_index.py"
if exist "%~dp0review\html\index.html" start "" "%~dp0review\html\index.html"
