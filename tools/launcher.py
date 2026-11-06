"""
Lanzador ligero de Transcripta (se compila a Transcripta.exe con PyInstaller).

No empaqueta la app entera (que pesa GBs por torch/CUDA); simplemente abre la
aplicacion usando el interprete del entorno virtual (venv) que esta junto al
ejecutable. Asi el .exe es pequeno y rapido de generar.
"""
import os
import sys
import subprocess


def base_dir():
    # Si esta congelado (exe de PyInstaller), la carpeta es la del propio .exe.
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    base = base_dir()
    pythonw = os.path.join(base, "venv", "Scripts", "pythonw.exe")
    app = os.path.join(base, "src", "app.py")

    if not os.path.exists(pythonw):
        # Sin entorno: avisar de que hay que instalar dependencias primero.
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0,
            "No se encontro el entorno (venv).\n\n"
            "Ejecuta primero 'Instalar dependencias.bat'.",
            "Transcripta", 0x10)
        return

    env = os.environ.copy()
    env["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
    subprocess.Popen([pythonw, app], cwd=base, env=env)


if __name__ == "__main__":
    main()
