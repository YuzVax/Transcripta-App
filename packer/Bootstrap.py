"""Entry point of the private, session-local Windows Python runtime."""
import ctypes
import os
from pathlib import Path
import runpy
import sys
import traceback

ROOT = Path(os.environ["TRANSCRIPTA_ROOT"]).resolve()
# ._pth deliberately ignores PYTHONPATH; use an explicit, private source path.
sys.path.insert(0, str(ROOT / "src"))
sys.dont_write_bytecode = True
_DLL_HANDLES = []
if os.name == "nt":
    # Retain directory cookies until process termination (Python 3.8+).
    for directory in (ROOT / "python", ROOT / "python/Lib/site-packages/torch/lib"):
        _DLL_HANDLES.append(os.add_dll_directory(str(directory)))


def main():
    # pythonw has no console streams; progress/logging libraries still need them.
    with (ROOT / "startup.log").open("w", encoding="utf-8", buffering=1) as log:
        sys.stdout = sys.stderr = log
        try:
            if "--self-test" in sys.argv:
                import tkinter
                import customtkinter
                import transcriber
                import translator
                import argostranslate.settings
                import argostranslate.translate
                import torch
                import subprocess
                import tempfile
                assert transcriber.pick_device() == ("cpu", "int8")
                assert not torch.cuda.is_available()
                for directory in (argostranslate.settings.data_dir,
                                  argostranslate.settings.cache_dir,
                                  argostranslate.settings.package_data_dir,
                                  Path(tempfile.gettempdir())):
                    assert directory.resolve().is_relative_to(ROOT), str(directory)
                import app
                window = app.App()
                window.withdraw()
                window.update()
                assert window._dnd_available, "TkDND no se pudo inicializar"
                assert window._last_dir is None
                print("TKDND OK:", window.TkdndVersion, flush=True)
                window.destroy()
                subprocess.run(["ffmpeg.exe", "-version"], check=True, stdout=log, stderr=log,
                               creationflags=subprocess.CREATE_NO_WINDOW)
                print("SELF-TEST OK", flush=True)
                return 0
            runpy.run_path(str(ROOT / "src/app.py"), run_name="__main__")
            return 0
        except BaseException as exc:
            if isinstance(exc, SystemExit) and not exc.code:
                return 0
            traceback.print_exc(file=log)
            log.flush()
            ctypes.windll.user32.MessageBoxW(
                None,
                "No se pudo abrir Transcripta.\n\n" + str(exc) +
                "\n\nLa sesión temporal se limpiará al cerrar este aviso.",
                "Transcripta", 0x10)
            return 1


if __name__ == "__main__":
    code = main()
    # Closing the window must also stop daemon model-download/inference workers.
    # No interpreter shutdown can then wait indefinitely for a native library.
    os._exit(code)
