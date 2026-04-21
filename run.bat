@echo off
REM Launches the Streamlit app using the project's .venv (one level up).
REM If you keep .venv elsewhere, edit the VENV_PY path below.

set "HERE=%~dp0"
set "VENV_PY=%HERE%..\.venv\Scripts\python.exe"

if exist "%VENV_PY%" (
    "%VENV_PY%" -m streamlit run "%HERE%app.py"
) else (
    echo .venv not found at %VENV_PY%
    echo Falling back to system python — make sure requirements are installed.
    python -m streamlit run "%HERE%app.py"
)
