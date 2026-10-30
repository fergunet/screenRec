@echo off
rem Lanza ScreenRec en Windows creando el entorno virtual la primera vez.
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Creando entorno virtual e instalando dependencias...
    py -3 -m venv .venv || python -m venv .venv || (echo No se encuentra Python 3. Instalalo desde python.org & pause & exit /b 1)
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt || (pause & exit /b 1)
)
start "" ".venv\Scripts\pythonw.exe" screenrec.py
