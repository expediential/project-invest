@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
set "PROJECT_INVEST_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%PROJECT_INVEST_PYTHON%" (
  echo Project Invest could not find .venv\Scripts\python.exe.
  echo Create the environment once with: python -m venv .venv
  echo Then install dependencies with: .venv\Scripts\python -m pip install -e .[dev]
  exit /b 1
)

"%PROJECT_INVEST_PYTHON%" -m project_invest launch --host 127.0.0.1 --port 8000
set "PROJECT_INVEST_EXIT_CODE=%ERRORLEVEL%"
endlocal & exit /b %PROJECT_INVEST_EXIT_CODE%
