@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
) else if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

python backend\manage.py runserver 127.0.0.1:8000

endlocal