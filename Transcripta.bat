@echo off
REM Lanzador desde el codigo (alternativa al Transcripta.exe).
REM Abre la app sin dejar ninguna ventana de consola abierta.
cd /d "%~dp0"
set HF_HUB_DISABLE_SYMLINKS_WARNING=1
start "" "%~dp0venv\Scripts\pythonw.exe" "%~dp0src\app.py"
exit
