@echo off
setlocal
cd /d "%~dp0"
set PYTHONPATH=src
python -m project_invest launch --host 127.0.0.1 --port 8000
endlocal
