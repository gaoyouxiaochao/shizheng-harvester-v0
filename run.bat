@echo off
cd /d "%~dp0project"
set PYTHONPATH=src
python -m harvest
if errorlevel 1 py -3 -m harvest
if errorlevel 1 pause
