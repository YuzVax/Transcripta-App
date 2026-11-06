@echo off
chcp 65001 >nul
title Instalar dependencias - Transcripta
cd /d "%~dp0"

echo ============================================================
echo   Instalador de dependencias - Transcripta
echo ============================================================
echo.

REM --- 1) Comprobar que Python esta instalado --------------------------------
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] No se encontro Python en el sistema.
    echo Instala Python 3.11 desde https://www.python.org/downloads/
    echo y marca la casilla "Add Python to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)
echo [OK] Python detectado:
python --version
echo.

REM --- 2) Crear el entorno virtual si no existe ------------------------------
if not exist "%~dp0venv\Scripts\python.exe" (
    echo [..] Creando entorno virtual ^(venv^)...
    python -m venv "%~dp0venv"
    if errorlevel 1 (
        echo [ERROR] No se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
    echo [OK] Entorno virtual creado.
) else (
    echo [OK] Entorno virtual ya existente.
)
echo.

REM --- 3) Actualizar pip e instalar dependencias ----------------------------
echo [..] Actualizando pip...
"%~dp0venv\Scripts\python.exe" -m pip install --upgrade pip
echo.
echo [..] Instalando dependencias ^(esto puede tardar varios minutos^)...
"%~dp0venv\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
    echo.
    echo [ERROR] Fallo la instalacion de dependencias. Revisa tu conexion
    echo a internet y vuelve a ejecutar este archivo.
    pause
    exit /b 1
)
echo.
echo [OK] Dependencias instaladas correctamente.
echo.

REM --- 4) Comprobar FFmpeg (necesario para leer .opus y otros formatos) ------
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo [AVISO] FFmpeg no esta en el PATH. Es necesario para convertir audios
    echo         ^(incluido .opus de WhatsApp^).
    echo         Instalalo con:  winget install Gyan.FFmpeg
    echo         y reinicia el equipo ^(o cierra y abre la terminal^).
) else (
    echo [OK] FFmpeg detectado.
)
echo.

echo ============================================================
echo   Todo listo. Abre la app con "Transcripta.exe".
echo ============================================================
echo.
pause
