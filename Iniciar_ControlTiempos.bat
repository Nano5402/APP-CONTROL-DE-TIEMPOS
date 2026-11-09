@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist "dist\ControlTiempos\ControlTiempos.exe" (
    start "" "dist\ControlTiempos\ControlTiempos.exe" %*
    exit /b 0
)

if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" "src\main.py" %*
    exit /b 0
)

if exist ".venv\Scripts\python.exe" (
    start "" ".venv\Scripts\python.exe" "src\main.py" %*
    exit /b 0
)

echo Configurando entorno virtual por primera vez...
python -m venv .venv
".venv\Scripts\python.exe" -m pip install -r requirements.txt
start "" ".venv\Scripts\pythonw.exe" "src\main.py" %*
